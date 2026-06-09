# GitLab CI Integration (Phase 4)

> Status (review 2026-06-09): the components below (template, scripts,
> webhook) work individually, but the loop does **not** yet close
> end-to-end — the resume pipeline cannot see the paused session's state,
> among other gaps. See `docs/mvp-plan.md` Phase 5 before deploying.

Step-by-step guide to enable TestBoost on a GitLab project so that
merge requests trigger automatic test generation, pausing in the MR
comments when the developer's input is needed.

## Architecture (5-minute mental model)

```
  ┌──────────────┐    push    ┌──────────────┐   exit 78    ┌────────────────┐
  │  Developer   │──────────▶│  GitLab CI   │─────────────▶│   MR comment   │
  │              │            │  tb:generate │              │  (question)    │
  └──────────────┘            └──────────────┘              └────────────────┘
         ▲                                                         │ reply
         │                                                         ▼
         │  pipeline                                       ┌────────────────┐
         │  succeeds                                       │  Comment with  │
         │                                                 │  YAML answer   │
         │                                                 └────────────────┘
         │                                                         │
         │  resume pipeline                                        ▼
  ┌──────────────┐ ◀──────────  ┌──────────────┐ ◀────  ┌──────────────────┐
  │  tb:generate │              │   Webhook    │        │  GitLab Note     │
  │  (resumed)   │              │  (you host)  │        │     Hook         │
  └──────────────┘              └──────────────┘        └──────────────────┘
```

Three moving parts to set up:

1. **The `.gitlab-ci.yml` template** (provided)
2. **Shell scripts** (provided) — `post_question_to_mr.sh`, `fetch_answer_from_mr.sh`
3. **A webhook service** (provided as `tools/gitlab-webhook/`) — you deploy this
   somewhere reachable from GitLab (a small FastAPI app)

## Step 1 — Configure CI/CD variables

In your project → Settings → CI/CD → Variables, add:

| Variable | Type | Notes |
|----------|------|-------|
| `GITLAB_TOKEN` | masked, protected | Project Access Token with `api` scope. Used to read MRs and post notes. |
| `TESTBOOST_TB_SECRET` | masked, protected | A random 64-char hex value. Seeds `.tb_secret` so HMAC is stable across pipelines. Generate with `openssl rand -hex 32`. |
| `ANTHROPIC_API_KEY` (or equivalent) | masked | Your LLM provider's API key. |
| `TESTBOOST_TECH` | (optional) | `java-spring`, `python-pytest`, etc. Default `java-spring`. |

> ⚠️ **Protected variables and MR pipelines**: GitLab only injects
> *protected* variables into pipelines running on protected branches or
> tags. MR pipelines on feature branches will see them **empty** — with
> the current code, `.tb_secret` is then seeded empty and HMAC runs with
> an empty key. Either protect your branch naming pattern, or leave
> `TESTBOOST_TB_SECRET` unprotected (masked only) and rely on masking +
> repository access control.

## Step 2 — Include the template in your `.gitlab-ci.yml`

```yaml
include:
  - project: 'axtion-io/testboost'
    ref: 'main'
    file: 'templates/gitlab/testboost.yml'

stages: [test]
```

> ℹ️ `include: project:` resolves on **your GitLab instance**: since the
> TestBoost source of truth lives on GitHub, this requires a GitLab
> mirror of the repo reachable by your project (adjust the `project:`
> path to wherever your mirror lives). Note also that `include:` only
> imports the YAML — the shell scripts referenced by the jobs are *not*
> distributed this way (fix planned: `testboost gitlab …` subcommands,
> mvp-plan Phase 5.4; in the meantime, vendor `scripts/gitlab/` into
> your repo).

Three jobs are now defined:

- **`testboost:analyze`** — runs `init` + `analyze` + `gaps` on MR events
- **`testboost:generate`** — runs `generate --fail-on-uncertainty`; on exit 78, posts the question to the MR via `scripts/gitlab/post_question_to_mr.sh` and exits 0 (job green, MR not blocked)
- **`testboost:cleanup`** — runs on scheduled pipelines only; marks abandoned sessions

## Step 3 — Deploy the webhook

The webhook is a small FastAPI app (~100 lines) that:

1. Listens for GitLab **Note Hook** events
2. Validates the secret token + author identity (only the MR author can answer)
3. Triggers a new pipeline on the MR's branch with `TESTBOOST_RESUME=true`

```bash
cd tools/gitlab-webhook
pip install -r requirements.txt
GITLAB_WEBHOOK_TOKEN=<random-secret> \
GITLAB_TOKEN=<same-as-CI> \
GITLAB_API_URL=https://gitlab.com/api/v4 \
uvicorn webhook:app --host 0.0.0.0 --port 8080
```

In a real deployment, run it behind a reverse proxy with TLS. For
development, ngrok or cloudflared tunnel works.

## Step 4 — Configure GitLab webhook

In your project → Settings → Webhooks → Add new webhook:

- URL: `https://your-webhook-host/gitlab/note`
- Secret token: same value as `GITLAB_WEBHOOK_TOKEN` in the webhook env
- Trigger: **Comments** only
- SSL verification: on

Click "Test → Comments" to verify connectivity.

## Step 5 — Add a "resume" job to `.gitlab-ci.yml`

The webhook triggers a pipeline with `TESTBOOST_RESUME=true`. Wire that
to a job that fetches the developer's answer and calls `resume`:

```yaml
testboost:resume:
  extends: .testboost:base
  stage: test
  rules:
    - if: $TESTBOOST_RESUME == "true"
  script:
    - bash scripts/gitlab/fetch_answer_from_mr.sh
    - poetry run python -m testboost resume "$CI_PROJECT_DIR" --answer-file ./answer.json
```

## How a developer experiences this

1. They push to a branch and open an MR
2. The pipeline runs; `testboost:generate` pauses on a missing edge case
3. A comment appears on the MR (the `markdown_preview` from `question.json`):

   ```markdown
   ### 🤖 TestBoost needs input (missing_business_context)

   **Question**: No edge cases were derived for `OrderService`...

   **Subject**: { class_name: "OrderService", ... }

   **Reply with this shape** (paste a fenced JSON block below):
   ```json
   { "test_requirements": [ { "scenario": "...", "expected": "..." } ] }
   ```
   ```

4. The developer replies in the same thread with their JSON block + the
   `<!-- testboost:question_id=… -->` marker (copy-paste from the bot's
   comment)
5. The webhook fires → new pipeline → `fetch_answer_from_mr.sh` extracts
   the JSON, signs it with the project secret, and the resume job
   continues where the previous pipeline paused.

## Security notes

Be clear about what protects what in the CI flow:

- **The actual access control is the author check**: the webhook and
  `fetch_answer_from_mr.sh` only accept comments from the **MR author**
  (other identities, including maintainers, are rejected by default —
  extend the check in `webhook.py` for a broader allow-list), combined
  with the scoping of the Project Access Token.
- **The HMAC signature is NOT an authentication of the commenter** in
  this flow: the CI itself signs whatever JSON the accepted comment
  contains (`sign-answer` runs in the pipeline with the project secret).
  It guarantees integrity between signing and consumption, binds the
  answer to one specific `question_id` (an answer cannot be replayed
  against a different question), and protects the *local* workflow where
  a developer signs answers on their own machine.
- **The TTL** (24h default) bounds how long a pending question stays
  answerable. Replay of an old answer on a *new* question is prevented
  by the `question_id` binding, not by the TTL.
- `.tb_secret` is provisioned from a masked CI variable and is never
  logged. ⚠️ Until mvp-plan Phase 5.2 lands, the template's artifacts
  include `.testboost/` **with the secret inside** — anyone who can
  download job artifacts can read it. Add
  `artifacts:exclude: [.testboost/.tb_secret]` if you deploy before that
  fix.

## User test ("P4-USR" from the MVP plan)

For the real-world demo, you need:

1. A demo Java repo with a "broken" service (e.g., `OrderService.java`
   with no obvious test scenarios)
2. The webhook deployed and accessible
3. Two humans: one playing the dev, one the reviewer

Run through the flow once on a private MR. Record a 5-minute screencast.
Iterate on UX issues:

- Is the question's markdown_preview clear?
- Are the answer instructions obvious?
- Does the resume pipeline succeed without further help?
- How long does the round-trip take? (Acceptance target: < 5 min)

> **Open call**: P4-USR is on hold until mvp-plan Phase 5 closes the
> loop end-to-end (see Known limitations below). Once Phase 5 lands, we
> need a volunteer dev with a real GitLab project to run P4-USR. See
> `docs/mvp-plan.md` Phase 4 for the exact protocol.

## Known limitations

**Blocking — the loop does not close yet** (fixes planned, see
`docs/mvp-plan.md` Phase 5):

- **No session state hand-off**: the paused session
  (`.testboost/sessions/`, `question.json`, cursor) lives in the paused
  job's workspace; the webhook-triggered resume pipeline starts from a
  fresh checkout and finds no session. Decision: the pause job will
  commit the session state to the MR branch (Phase 5.1).
- **Resume pipeline context**: API-triggered branch pipelines have no
  `CI_MERGE_REQUEST_IID`; the scripts don't yet fall back to the
  `TESTBOOST_MR_IID` variable the webhook sends (Phase 5.3).
- **Script distribution**: `include:` only imports YAML; the
  `scripts/gitlab/*.sh` files and a TestBoost installation must be
  present in the consumer repo (Phase 5.4).

**Non-blocking**:

- The `fetch_answer_from_mr.sh` script parses the *first* matching JSON
  block from the *first* matching note. Multiple-answer flows aren't
  supported.
- The webhook triggers one pipeline per comment, with no debouncing. If
  the dev edits their comment, multiple pipelines may run. (Tolerable
  for the MVP; add a 30s debouncer in production.)
- A paused `testboost:generate` job currently exits 0 (green). It will
  switch to GitLab's orange "warning" status via
  `allow_failure: exit_codes: [78]` (Phase 6.5).
- Self-managed GitLab instances older than 14.x have not been tested.
