# GitLab CI Integration (Phase 4)

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

## Step 2 — Include the template in your `.gitlab-ci.yml`

```yaml
include:
  - project: 'axtion-io/testboost'
    ref: 'main'
    file: 'templates/gitlab/testboost.yml'

stages: [test]
```

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

- The webhook only triggers if the comment is from the **MR author**.
  Other identities (project maintainers, etc.) are rejected by default.
  Extend the author check in `webhook.py` if you want a broader allow-list.
- All answers go through `verify_answer()` before being applied. An
  attacker who can post comments but doesn't have the `.tb_secret`
  **cannot** forge a valid `answer.json`.
- The TTL (24h default) prevents replay attacks where an old answer is
  re-submitted on a new question.
- `.tb_secret` is provisioned from a masked, protected CI variable. It
  is **never** logged.

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

> **Open call**: this is the next thing to validate. The MVP code +
> infrastructure are ready. We need a volunteer dev with a real GitLab
> project to run P4-USR end-to-end. See `docs/mvp-plan.md` Phase 4 for
> the exact protocol.

## Known limitations

- The `fetch_answer_from_mr.sh` script parses the *first* matching JSON
  block from the *first* matching note. Multiple-answer flows aren't
  supported.
- The webhook triggers one pipeline per comment, with no debouncing. If
  the dev edits their comment, multiple pipelines may run. (Tolerable
  for the MVP; add a 30s debouncer in production.)
- Self-managed GitLab instances older than 14.x have not been tested.
