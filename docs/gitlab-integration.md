# GitLab CI Integration

Step-by-step guide to enable TestBoost on a GitLab project so that
merge requests trigger automatic test generation, pausing in the MR
comments when the developer's input is needed.

> ⚠️ **Maturity**: every component is implemented and unit-tested, but
> the full loop has not yet been validated on a real GitLab project.
> Expect rough edges; please report them.

## Architecture (5-minute mental model)

```
  ┌──────────────┐    push    ┌──────────────────┐  exit 78   ┌────────────────┐
  │  Developer   │──────────▶│    GitLab CI      │──────────▶│   MR comment   │
  │              │            │ testboost:generate│  (orange)  │ (ONE question, │
  └──────────────┘            │   ⤷ commits state │            │  all items)    │
         ▲                    │     + tests so far│            └────────────────┘
         │  green job:        └──────────────────┘                   │ reply
         │  generated tests                                          ▼
         │  committed to the                                 ┌────────────────┐
         │  MR branch                                        │  Comment with  │
         │                                                   │  JSON answer   │
         │  resume pipeline                                  └────────────────┘
  ┌──────────────────┐ ◀──────  ┌──────────────┐ ◀──────  ┌──────────────────┐
  │ testboost:resume │          │   Webhook    │          │  GitLab Note     │
  │ (state from git) │          │  (you host)  │          │     Hook         │
  └──────────────────┘          └──────────────┘          └──────────────────┘
```

Key mechanics:

- A run that needs human input **exits 78** and shows as an **orange
  "warning" job** (`allow_failure: exit_codes`): the MR is not blocked,
  but the state is honest.
- All uncertainties of a run are **batched into one question** (one MR
  comment) — and the comment itself explains exactly how to reply.
- Generated tests and the session state (`.testboost/`, minus the
  secret) are **committed to the MR branch** (`[skip ci]`) — on success
  as the deliverable, on pause so the resume pipeline finds both the
  paused session and the already-generated tests in its checkout. On a
  hard failure (red job) nothing is committed.

Two moving parts to set up:

1. **The `.gitlab-ci.yml` template** (provided) — includes the resume job
2. **A webhook service** (provided as `tools/gitlab-webhook/`) — a small
   FastAPI app you deploy somewhere reachable from your GitLab

## Prerequisites

Work through these BEFORE step 1 — they are where self-managed setups
actually stall:

**A GitLab mirror of TestBoost.** `include: project:` resolves on *your*
GitLab instance, and the TestBoost source of truth lives on GitHub. Create
a project on your instance (e.g. `your-group/testboost`) and set up [pull
mirroring](https://docs.gitlab.com/ee/user/project/repository/mirror/pull.html)
from `https://github.com/axtion-io/TestBoost.git` (or push a clone
manually). Requirements: the mirror must contain
`templates/gitlab/testboost.yml` at the `ref:` you include (use `main`,
or a tag for reproducibility), and every developer whose pipelines use
the template needs at least Reporter access to the mirror project.

**A job image with your build toolchain.** The template defaults to
`python:3.11-slim`, which has **no JDK and no Maven**: TestBoost will
still generate tests, but cannot compile-check or auto-fix them, and the
`validate` job cannot run. For a Java project, set the `TESTBOOST_IMAGE`
CI variable to an image containing **JDK + Maven + Python 3.11+ with
venv support**. This Dockerfile works (Ubuntu noble base → Python 3.12;
the template installs TestBoost into a venv, so PEP 668 and the
`python` vs `python3` alias question are non-issues):

```dockerfile
FROM maven:3.9-eclipse-temurin-17-noble
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 python3-pip python3-venv git \
 && rm -rf /var/lib/apt/lists/*
```

Push it to your registry and set `TESTBOOST_IMAGE` to its path. Avoid
jammy-based tags (Python 3.10 < TestBoost's required 3.11).

**Runners.** Docker or Kubernetes executor, able to pull the image
(from Docker Hub or your registry) and to run `apt-get` as root when the
default image is used. Shell executors are not supported as-is.

**Network egress for pip.** Jobs install TestBoost with
`pip install $TESTBOOST_PACKAGE`, defaulting to
`git+https://github.com/axtion-io/TestBoost.git@main`. If your runners
cannot reach GitHub, point `TESTBOOST_PACKAGE` at your mirror:
`git+https://<your-gitlab>/your-group/testboost.git@<tag>`.

**A Project Access Token.** Created under your project → Settings →
**Access Tokens** (not the Variables page — that's where you'll *store*
it): role **Developer** (Maintainer if your project restricts pushes or
pipeline triggering), scopes **`api` + `write_repository`**. It posts MR
notes, pushes the state/tests commits, and triggers resume pipelines.
Note the bot user it creates (e.g. `project_42_bot_abc123`, visible in
Members or via `curl -H "PRIVATE-TOKEN: $TOKEN" https://<your-gitlab>/api/v4/user`)
— you'll need that username for the webhook's loop guard (Step 3).

> ⚠️ On GitLab 17.7+ check Settings → CI/CD → Variables → **"Minimum
> role to use pipeline variables"**: the resume webhook triggers
> pipelines *with variables* (`TESTBOOST_RESUME`, `TESTBOOST_MR_IID`),
> so the token's role must meet that threshold or the trigger returns
> `403 Insufficient permissions to set pipeline variables`.

**Check your `workflow: rules`.** If your `.gitlab-ci.yml` restricts
pipelines to `merge_request_event` (the common duplicate-pipeline
recipe), the webhook-triggered **branch** pipeline carrying
`TESTBOOST_RESUME=true` will be filtered out before any job runs. Add an
allow rule, e.g.:

```yaml
workflow:
  rules:
    - if: $CI_PIPELINE_SOURCE == "merge_request_event"
    - if: $TESTBOOST_RESUME == "true"
```

Conversely, if you have **no** workflow rules, your other jobs will also
run in resume pipelines — gate them as needed.

**Merged-results MR pipelines are not supported.** The pause commit
pushes `HEAD` to the source branch; with "merged results" enabled, HEAD
is a transient merge commit. Use standard (detached) MR pipelines.

## Step 1 — Configure CI/CD variables

In your project (or group) → Settings → CI/CD → Variables. Enable the
**Masked** flag on every secret:

| Variable | Notes |
|----------|-------|
| `GITLAB_TOKEN` | The Project Access Token from Prerequisites (masked). |
| `TESTBOOST_TB_SECRET` | `openssl rand -hex 32` (masked). Seeds the per-project HMAC key (`.testboost/.tb_secret`) used to sign questions/answers, so signatures stay verifiable across pipelines. |
| `ANTHROPIC_API_KEY` (or `GOOGLE_API_KEY` / `OPENAI_API_KEY`) | Your LLM provider's key (masked). |
| `LLM_PROVIDER`, `MODEL` | Only if you don't use the defaults (`anthropic`, `claude-sonnet-4-6`) — e.g. `google-genai` + `gemini-2.5-flash`. |
| `TESTBOOST_IMAGE` | Job image with your build toolchain (see Prerequisites). |
| `TESTBOOST_PACKAGE` | (optional) pip source override — pin a tag in production. |
| `TESTBOOST_COMMIT_PATHS` | (optional) paths committed back to the MR branch; default `src/test` (Maven). Use `tests` for Python projects. |
| `TESTBOOST_TECH` | (optional) `java-spring` (default), `python-pytest`, … |

> ⚠️ **Don't mark these variables "protected"** unless your MR source
> branches are protected: GitLab only injects protected variables into
> pipelines on protected refs, so MR pipelines on feature branches would
> see them **empty**. The template fails fast with an explicit error when
> `TESTBOOST_TB_SECRET` or `GITLAB_TOKEN` come up empty.

## Step 2 — Include the template in your `.gitlab-ci.yml`

```yaml
include:
  - project: 'your-group/testboost'   # ← your mirror (see Prerequisites)
    ref: 'main'                       # ← or a pinned tag
    file: 'templates/gitlab/testboost.yml'

stages: [test]   # if you already define stages, ADD test to your list — don't replace it
```

The template is self-contained: jobs `pip install` TestBoost (into a
venv), nothing needs to be vendored into your repo. Four jobs are
defined:

- **`testboost:analyze`** — `init` + `analyze` + `gaps` on MR events
- **`testboost:generate`** — `generate --fail-on-uncertainty`; on exit 78
  the job goes orange, commits session state + tests generated so far to
  the MR branch, and posts the question comment
- **`testboost:validate`** — compiles and runs the generated tests;
  opt-in via `TESTBOOST_RUN_VALIDATE=true` (requires a `TESTBOOST_IMAGE`
  with your build toolchain)
- **`testboost:resume`** — runs in webhook-triggered pipelines
  (`TESTBOOST_RESUME=true`); fetches + signs the answer from the MR
  notes and resumes the paused step

## Step 3 — Deploy the webhook

The webhook is a small FastAPI app (~120 lines) that listens for GitLab
**Note Hook** events, validates the secret token (constant-time) and the
commenter identity (only the MR author may answer; the bot's own
comments are ignored), and triggers a branch pipeline with
`TESTBOOST_RESUME=true` + `TESTBOOST_MR_IID=<iid>`.

Deployment host requirements: Python 3.10+, network route to your
GitLab, and a clone of the TestBoost repo for `tools/gitlab-webhook/`.

```bash
cd tools/gitlab-webhook
pip install -r requirements.txt
GITLAB_WEBHOOK_TOKEN=<random secret you choose> \
GITLAB_TOKEN=<same Project Access Token as the CI> \
GITLAB_API_URL=https://<your-gitlab>/api/v4 \
TESTBOOST_BOT_USERNAME=<the token's bot username> \
uvicorn webhook:app --host 0.0.0.0 --port 8080
```

> ⚠️ `GITLAB_API_URL` **defaults to gitlab.com** when unset — on a
> self-managed instance, forgetting it produces confusing 401/404s
> against the wrong GitLab.

In a real deployment, run it behind a reverse proxy with TLS. For
development, ngrok or cloudflared tunnel works.

## Step 4 — Register the webhook in GitLab

In your project → Settings → Webhooks → Add new webhook:

- URL: `https://your-webhook-host/gitlab/note`
- Secret token: same value as `GITLAB_WEBHOOK_TOKEN` in the webhook env
- Trigger: **Comments** only
- SSL verification: on

Click "Test → Comments" to verify connectivity (the project needs at
least one existing comment for GitLab to send a sample). Any HTTP 200 —
typically `{"ignored": "not a MR note"}`, since the sample is usually a
commit note — proves the webhook is reachable and the secret token
matches; a 401 means the secret token doesn't.

> **No cleanup schedule needed**: paused sessions live on MR source
> branches, which die when the MR merges. (`testboost cleanup` exists
> for local, long-lived checkouts.)

## How a developer experiences this

1. They push a branch and open an MR.
2. The pipeline runs; `testboost:generate` finishes everything it can.
   Generated tests are **committed to the MR branch** (`[skip ci]`,
   author "TestBoost Bot"). If one or more files need input, the job
   goes **orange** and ONE comment appears:

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

   **How to reply** (as the MR author, in a new comment):

   1. Paste your answer as ONE fenced ```json block (raw JSON — do NOT
      sign it, the CI signs accepted answers itself);
   2. Include this exact line anywhere in the same comment:
      `testboost:question_id=3f2a…`

   _Question ID: `3f2a…`_
   ````

3. The developer replies following those two instructions — raw JSON
   block + the `testboost:question_id=…` line copied from the comment.
4. The webhook fires → branch pipeline with `TESTBOOST_RESUME=true` →
   `testboost:resume` finds the session state AND the already-generated
   tests in its checkout (committed at step 2), extracts + signs the
   answer, and continues exactly where the previous run stopped —
   completed files are skipped, a `fixed_code` answer is applied without
   regenerating.
5. On completion, the remaining tests are committed to the MR branch:
   the MR now contains all generated tests, ready for review.

### When the resume pipeline fails red

The webhook triggers on any comment carrying a `testboost:question_id=`
marker — validation happens in the `testboost:resume` job, which fails
**red** (exit 2 is not in `allow_failure`) when the answer can't be
used. Causes, in rough order of likelihood:

- **JSON typo** in the fenced block (the block is then skipped, and
  `fetch-answer` reports "no matching answer note found");
- **stale `question_id`** — the marker references a question that was
  superseded (e.g. a new push re-ran generate) or already consumed;
- **answered after the 24h TTL** (fixed, not configurable from CI) —
  clear signature/TTL error in the job log.

Recovery is always the same: post a **new** comment (don't rely on
editing the old one — whether edits re-fire the webhook depends on the
GitLab version), or re-run the MR pipeline to get a fresh question.

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
  logged. It is kept out of **artifacts** (`artifacts:exclude`), out of
  the **state commit** (ensured in `.testboost/.gitignore` even when CI
  seeds the secret before init, plus an explicit `:!` pathspec on
  `git add`), and the push goes through the **credential store** so a
  failing push cannot print the token into CI logs.
- The state/tests commits are pushed with `-o ci.skip` so they cannot
  trigger recursive pipelines.

## User test ("P4-USR")

For the real-world validation, you need a demo Java repo with an
"unclear" service, the webhook deployed, and two humans (dev +
reviewer). Run the flow once on a private MR, record a 5-minute
screencast, and check: is the question comment clear? does the reply
resume the pipeline? do the generated tests land on the MR? is the
round-trip under 5 minutes?

> **Open call**: we need a volunteer dev with a real GitLab project to
> run this end-to-end.

## Known limitations

- The pause/delivery commits add content to the MR diff. This is by
  design (the tests ARE the deliverable; `.testboost/` is the audit
  trail); mark `.testboost/` as `linguist-generated` in `.gitattributes`
  if it bothers reviewers.
- `testboost gitlab fetch-answer` takes the *first* matching JSON block
  from the *newest* matching note. Multiple-answer flows aren't
  supported.
- The webhook triggers one pipeline per comment, with no debouncing. If
  the dev edits their comment, multiple pipelines may run. (Tolerable
  for the MVP; add a 30s debouncer in production.)
- Requires GitLab **14.2+** (same-stage `needs:`; `allow_failure:
  exit_codes` needs 13.8+). Older self-managed instances fail YAML
  validation on the template.
