# GitLab CI Integration (Phases 4-6)

> Status (2026-06-09): the loop closes end-to-end — pause state is
> committed to the MR branch, the resume pipeline is part of the
> template, and the MR helpers ship as `testboost gitlab …` subcommands.
> Real-world validation (P4-USR) is still pending: see "User test" below.

Step-by-step guide to enable TestBoost on a GitLab project so that
merge requests trigger automatic test generation, pausing in the MR
comments when the developer's input is needed.

## Architecture (5-minute mental model)

```
  ┌──────────────┐    push    ┌──────────────────┐  exit 78   ┌────────────────┐
  │  Developer   │──────────▶│    GitLab CI      │──────────▶│   MR comment   │
  │              │            │ testboost:generate│  (orange)  │ (ONE question, │
  └──────────────┘            │   ⤷ commits state │            │  all items)    │
         ▲                    └──────────────────┘            └────────────────┘
         │                                                           │ reply
         │  pipeline                                                 ▼
         │  succeeds                                         ┌────────────────┐
         │                                                   │  Comment with  │
         │                                                   │  JSON answer   │
         │                                                   └────────────────┘
         │  resume pipeline                                          │
  ┌──────────────────┐ ◀──────  ┌──────────────┐ ◀──────  ┌──────────────────┐
  │ testboost:resume │          │   Webhook    │          │  GitLab Note     │
  │ (state from git) │          │  (you host)  │          │     Hook         │
  └──────────────────┘          └──────────────┘          └──────────────────┘
```

Key mechanics:

- A run that needs human input **exits 78** and shows as an **orange
  "warning" job** (`allow_failure: exit_codes`), not a green one: the MR
  is not blocked, but the state is honest.
- All uncertainties of a run are **batched into one question** (one MR
  comment), instead of one round-trip per file.
- On pause, the job **commits `.testboost/` to the MR branch**
  (`[skip ci]`, secret excluded via `.testboost/.gitignore`) — that is
  how the resume pipeline, which starts from a fresh checkout, finds the
  session again. No cross-pipeline artifact plumbing.

Two moving parts to set up:

1. **The `.gitlab-ci.yml` template** (provided) — includes the resume job
2. **A webhook service** (provided as `tools/gitlab-webhook/`) — you
   deploy this somewhere reachable from GitLab (a small FastAPI app)

The former `scripts/gitlab/*.sh` are gone: posting the question and
fetching the answer are now `testboost gitlab post-question` and
`testboost gitlab fetch-answer`, shipped with `pip install testboost`.

## Step 1 — Configure CI/CD variables

In your project → Settings → CI/CD → Variables, add:

| Variable | Type | Notes |
|----------|------|-------|
| `GITLAB_TOKEN` | masked | Project Access Token with `api` + `write_repository` scopes. Reads MRs, posts notes, pushes the pause-state commit. |
| `TESTBOOST_TB_SECRET` | masked | A random 64-char hex value. Seeds `.tb_secret` so HMAC is stable across pipelines. Generate with `openssl rand -hex 32`. |
| `ANTHROPIC_API_KEY` (or equivalent) | masked | Your LLM provider's API key. |
| `TESTBOOST_TECH` | (optional) | `java-spring`, `python-pytest`, etc. Default `java-spring`. |
| `TESTBOOST_PACKAGE` | (optional) | pip requirement for TestBoost. Defaults to the GitHub repo at `main`; pin a tag in production. |
| `TESTBOOST_BOT_USERNAME` | (optional) | Username of the `GITLAB_TOKEN` identity — used by the webhook as a loop guard. |

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
> path to wherever your mirror lives). The template is self-contained:
> jobs `pip install` TestBoost (`TESTBOOST_PACKAGE`), so nothing else
> needs to be vendored into your repo.

Four jobs are now defined:

- **`testboost:analyze`** — runs `init` + `analyze` + `gaps` on MR events
- **`testboost:generate`** — runs `generate --fail-on-uncertainty`; on
  exit 78 the job goes orange, commits the session state to the MR
  branch, and posts the question via `testboost gitlab post-question`
- **`testboost:resume`** — runs when the webhook triggers a pipeline with
  `TESTBOOST_RESUME=true`; fetches + signs the answer from the MR notes
  (`testboost gitlab fetch-answer`) and resumes the paused step
- **`testboost:cleanup`** — runs on scheduled pipelines only; marks
  abandoned sessions

## Step 3 — Deploy the webhook

The webhook is a small FastAPI app (~120 lines) that:

1. Listens for GitLab **Note Hook** events
2. Validates the secret token (constant-time) + author identity (only
   the MR author can answer); ignores the bot's own comments
3. Triggers a new pipeline on the MR's source branch with
   `TESTBOOST_RESUME=true` and `TESTBOOST_MR_IID=<iid>`

```bash
cd tools/gitlab-webhook
pip install -r requirements.txt
GITLAB_WEBHOOK_TOKEN=<random-secret> \
GITLAB_TOKEN=<same-as-CI> \
GITLAB_API_URL=https://gitlab.com/api/v4 \
TESTBOOST_BOT_USERNAME=<bot-username> \
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

That's it — the resume job is part of the template (Step 2), no extra
`.gitlab-ci.yml` work needed.

## How a developer experiences this

1. They push to a branch and open an MR
2. The pipeline runs; `testboost:generate` finishes everything it can,
   and goes **orange** if one or more files need input
3. ONE comment appears on the MR listing every open item (the
   `markdown_preview` from `question.json`):

   ````markdown
   ### 🤖 TestBoost needs input — 2 item(s)

   **Summary**: 2 file(s) need your input to finish this generation run
   (3 other file(s) were generated successfully).

   #### 1. missing_business_context — `OrderService`
   **Question**: No edge cases were derived for `OrderService`…

   #### 2. compilation_fix_exhausted — `UserController`
   **Question**: Could not fix compilation of `UserController`…

   **Reply with ONE fenced JSON block combining your answers**:
   ```json
   {
     "test_requirements": {"OrderService": [{"scenario": "…", "expected": "…"}]},
     "compile_fixes": {"UserController": {"fixed_code": "…", "hints": ["…"]}}
   }
   ```
   _Question ID: `…`_
   ````

4. The developer replies in the same thread with their JSON block + the
   `<!-- testboost:question_id=… -->` marker (copy-paste from the bot's
   comment)
5. The webhook fires → branch pipeline with `TESTBOOST_RESUME=true` →
   `testboost:resume` finds the session state in its checkout (committed
   when the run paused), extracts + signs the answer, and continues
   exactly where the previous pipeline stopped — completed files are
   skipped, and a `fixed_code` answer is applied without regenerating.

## Security notes

Be clear about what protects what in the CI flow:

- **The actual access control is the author check**: the webhook and
  `testboost gitlab fetch-answer` only accept comments from the **MR
  author** (other identities, including maintainers, are rejected by
  default — extend the check in `webhook.py` for a broader allow-list),
  combined with the scoping of the Project Access Token.
- **The HMAC signature is NOT an authentication of the commenter** in
  this flow: the CI itself signs whatever JSON the accepted comment
  contains. It guarantees integrity between signing and consumption,
  binds the answer to one specific `question_id` (an answer cannot be
  replayed against a different question), and protects the *local*
  workflow where a developer signs answers on their own machine.
- **The TTL** (24h default) bounds how long a pending question stays
  answerable. Replay of an old answer on a *new* question is prevented
  by the `question_id` binding, not by the TTL.
- `.tb_secret` is provisioned from a masked CI variable and is never
  logged. The template **excludes it from artifacts**
  (`artifacts:exclude`) and `.testboost/.gitignore` keeps it out of the
  pause-state commit.
- The state commit is pushed with `-o ci.skip` so it cannot trigger
  recursive pipelines.

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

> **Open call**: the loop is now implemented end-to-end (Phases 5-6).
> We need a volunteer dev with a real GitLab project to run P4-USR.
> See `docs/mvp-plan.md` Phase 4 for the exact protocol.

## Known limitations

- The pause-state commit adds `.testboost/` session markdown to the MR
  diff. This is by design (it's the audit trail); mark it
  `linguist-generated` in `.gitattributes` if it bothers reviewers.
- `testboost gitlab fetch-answer` takes the *first* matching JSON block
  from the *newest* matching note. Multiple-answer flows aren't
  supported.
- The webhook triggers one pipeline per comment, with no debouncing. If
  the dev edits their comment, multiple pipelines may run. (Tolerable
  for the MVP; add a 30s debouncer in production.)
- Self-managed GitLab instances older than 14.x have not been tested
  (`allow_failure: exit_codes` requires GitLab 13.8+).
