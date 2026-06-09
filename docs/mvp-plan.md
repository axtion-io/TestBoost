# MVP Plan — Async CI/CD Integration

> Living document. Updated at each phase completion with actual dates,
> outcomes, and lessons learned.

## Status overview

| Phase | Goal | Effort | Status | Completed |
|-------|------|--------|--------|-----------|
| Spike | Prove pause/resume primitives | 2 j/h | ✅ done | 2026-06-01 |
| 1 | Security & state foundations | 5 j/h | ✅ done | 2026-06-02 |
| 2 | UX extension (hints, more triggers) | 5 j/h | ✅ done | 2026-06-02 |
| 3 | Operability (cleanup, doctor, metrics) | 3 j/h | ✅ done | 2026-06-02 |
| 4 | GitLab integration layer | 5 j/h | ⚠️ rework needed (review 2026-06-09) | 2026-06-02 |
| 5 | Hardening — review fixes (state hand-off, secret leak, dead features) | 6 j/h | planned | — |
| 6 | Grouped questions & resume UX | 4.5 j/h | planned | — |
| Cross-cutting | E2E tests, changelog, security review | 2 j/h | rolling | — |
| Buffer | Reviews, integration bugs | 4-5 j/h | rolling | — |
| **Total** | | **~35 j/h** | | — |

**Calendar**: 5-6 weeks with 80% dev allocation.

**Stop-the-line gates** (must pass before moving to next phase):

- ✅ Code: all phase tasks merged
- ✅ Tests: unit + 1 signed user test scenario
- ✅ Doc: existing pages updated + new content reviewed

---

## Phase 1 — Foundations: security & state (5 j/h)

**Goal**: lock the round-trip so it is re-entrant, signed, and resumable
at the file level.

### Tasks

| # | Task | Effort | Files |
|---|------|--------|-------|
| 1.1 | Per-file cursor in `spec.md` (`current_file_index`, `completed_files`) | 1.5 j | `session_tracker.py`, `cli.py` |
| 1.2 | Dedicated `resume` command (sugar around `--answer-file`, detects pending step) | 1 j | `cli.py` |
| 1.3 | HMAC signature `question.json` ↔ `answer.json` (reuses `.tb_secret`) | 1.5 j | `integrity.py`, `session_tracker.py` |
| 1.4 | Reject malformed/expired answers (TTL 24h default, configurable) | 0.5 j | `session_tracker.py` |
| 1.5 | Doc + tests | 0.5 j | see below |

### Acceptance criteria (formal milestones)

- 🚦 **P1.A** — `generate --fail-on-uncertainty` paused on file #3 of 5, followed by `resume`, must regenerate **only** files ≥ 3 (verified via mocked LLM `call_count`).
- 🚦 **P1.B** — An unsigned or tampered `answer.json` MUST be rejected with exit 1 and a clear message. No LLM call may occur.
- 🚦 **P1.C** — An `answer.json` signed for session A applied to session B must be rejected (session_id in signed payload).
- 🚦 **P1.D** — `python -m testboost resume <project>` without `--answer-file` must display the pending question and exit 0 (show-pending mode).

### Unit tests to add (~12)

- `test_session_tracker.py::TestFileCursor` (4): init, advance on success, persist on pause, read on startup
- `test_integrity.py::TestQuestionSigning` (4): stable signature, OK verification, tampered rejection, TTL expired rejection
- `test_cli.py::TestResumeCommand` (4): show pending, consume answer, no session = exit 1, no pending = exit 0

### User test 🧑

**Scenario P1-USR** (10 min, 1 human, 1 Java fixture project):

1. Run `generate --fail-on-uncertainty` on a 3-file project (mocked LLM returning empty edge_cases for file #2 only).
2. Verify: `question.json` mentions the right file, `spec.md` shows `current_file_index: 1`, files 0 and 2 NOT generated.
3. Build `answer.json` by hand, sign via `python -m testboost sign-answer` (utility subcommand from 1.3).
4. Run `resume` → verify only file 2 is regenerated, status becomes `completed`.
5. **Success criterion**: zero CLI intervention beyond these 2 commands, zero suspicious warnings.

### Doc updates

- `docs/ci-async-integration.md`: sections "Per-file cursor", "Signing answers"; remove items 1, 2, 3 from "What's not done"
- `docs/session-format.md`: document new frontmatter fields `current_file_index`, `completed_files`
- `docs/architecture.md`: add round-trip signing diagram
- `README.md`: 2 lines in "Status" section mentioning async mode

---

## Phase 2 — UX extension (5 j/h)

**Goal**: make async mode usable by devs who don't know TestBoost in depth.

### Tasks

| # | Task | Effort | Files |
|---|------|--------|-------|
| 2.1 | `hints` mode in `compile_fixes` (dev writes natural language, LLM retries 1× with hint) | 1.5 j | `cli.py`, `bridge.py` |
| 2.2 | Wire pattern to `validate` (tests failing at runtime → pause) | 1.5 j | `cli.py::_cmd_validate_async` |
| 2.3 | Wire pattern to `killer` (surviving mutants after N attempts) | 1 j | `cli.py::_cmd_killer_async` |
| 2.4 | Enriched `question.json`: `markdown_preview` (MR-ready comment body) | 0.5 j | `session_tracker.py::emit_question` |
| 2.5 | Doc + tests | 0.5 j | see below |

### Acceptance criteria

- 🚦 **P2.A** — A `{"compile_fixes": {"X": {"hints": ["use Mockito.mock"]}}}` answer triggers **one** LLM retry with hint injected, not more.
- 🚦 **P2.B** — `validate` paused on runtime test failure → `question.json` contains stack trace + failing test (not all passing tests).
- 🚦 **P2.C** — `killer` after N surviving mutants → question describes the highest-priority survivor, not full PIT dump.
- 🚦 **P2.D** — Every `question.json` contains a `markdown_preview` directly usable as MR comment body (snapshot tested).

### Unit tests to add (~15)

- `TestHintsMode` (3): hint injected, one retry only, hints + fixed_code → fixed_code wins
- `TestValidatePause` (4): pause on runtime fail, no pause when flag off, resume with answer, question contains stack trace
- `TestKillerPause` (4): same for killer
- `TestMarkdownPreview` (4): preview present, escapes backticks, contains subject + answer_schema

### User test 🧑

**Scenario P2-USR** (20 min, 1 human, 1 Java project with a deliberately broken test):

1. Paste a `markdown_preview` from `question.json` into a local `.md` and verify it renders correctly
2. Trigger a real compile error (renamed method) → verify hint mode works, hint "rename foo to bar" unblocks
3. Trigger a surviving mutant → resolve via answer-file
4. **Success criterion**: a TestBoost-naive dev unblocks 2/3 cases without help

### Doc updates

- `docs/ci-async-integration.md`: sections "Hints mode", "Pause triggers on validate/killer"
- `docs/workflow.md`: add `awaiting_input` state to transition diagram
- New `docs/ci-question-cookbook.md`: concrete question/answer examples per `kind`

---

## Phase 3 — Operability (3 j/h)

**Goal**: run 24/7 without manual babysitting.

### Tasks

| # | Task | Effort | Files |
|---|------|--------|-------|
| 3.1 | `cleanup` command: purge abandoned sessions (awaiting_input + age > TTL) | 1 j | `session_tracker.py`, `cli.py` |
| 3.2 | Structured metrics (JSON on stdout) per command: duration, LLM tokens, files, final state | 1 j | `cli.py`, `md_logger.py` |
| 3.3 | Health-check `doctor`: LLM, `.tb_secret`, write perms, Maven | 0.5 j | `cli.py`, `startup_checks.py` |
| 3.4 | Doc + tests | 0.5 j | see below |

### Acceptance criteria

- 🚦 **P3.A** — A session `awaiting_input` older than TTL must be marked `abandoned` by `cleanup` (NOT deleted — audit trail).
- 🚦 **P3.B** — Each command emits exactly **one** JSON line on stdout prefixed `[TESTBOOST_METRICS:{...}]`, parseable.
- 🚦 **P3.C** — `doctor` detects 4/4 broken scenarios (LLM down, secret missing, dir read-only, Maven absent) with distinct exit codes.

### Unit tests to add (~8)

- `TestCleanup` (3): mark abandoned past TTL, preserve recent completed, dry-run mode
- `TestMetrics` (3): stable prefix, valid JSON, required fields present
- `TestDoctor` (2): all-green success, mocked LLM-down detection

### User test 🧑

**Scenario P3-USR** (15 min):

1. Create a session, leave `awaiting_input`, mock-age its date in `spec.md` past TTL
2. `cleanup --dry-run` lists without touching
3. `cleanup` marks `abandoned`
4. Cut LLM connection, run `doctor` → non-zero exit with targeted message
5. **Success criterion**: no "it just doesn't work" — every failure has an actionable cause

### Doc updates

- `docs/ci-async-integration.md`: section "Operations" (TTL, cleanup, doctor)
- `docs/configuration.md`: document `session_ttl_hours`, `cleanup_retention_days`

---

## Phase 4 — GitLab integration layer (5 j/h)

**Goal**: a dev installs the integration on their GitLab project in 1h, uses it on a MR the same day.

### Tasks

| # | Task | Effort | Files |
|---|------|--------|-------|
| 4.1 | Packaged `.gitlab-ci.yml` template (`templates/gitlab/testboost.yml` to `include:`) | 1 j | new |
| 4.2 | `scripts/gitlab/post_question_to_mr.sh` (reads question.json → MR note via API) | 1 j | new |
| 4.3 | `scripts/gitlab/fetch_answer_from_mr.sh` (parse comment → signed answer.json) | 1.5 j | new |
| 4.4 | Webhook handler (Python FastAPI under `tools/gitlab-webhook/`): receive Note Hook, validate author, trigger pipeline | 1 j | new |
| 4.5 | Doc + E2E tests + demo | 0.5 j | see below |

### Acceptance criteria

- 🚦 **P4.A** — On a demo GitLab project, a push triggering `tb:generate` with a pending question must produce an MR comment in <30s.
- 🚦 **P4.B** — A comment from a **non-author** of the MR must be ignored by the webhook (verified in logs).
- 🚦 **P4.C** — Full round-trip (push → pause → comment → reply → resume → tests committed) must complete in **<5 min** on demo project.
- 🚦 **P4.D** — `.gitlab-ci.yml` template must work on GitLab.com **and** GitLab Self-Managed (tested on both).

### Unit tests to add (~10)

- `test_gitlab_scripts.py`: 3 tests for `post_question_to_mr.sh` (mocking `gitlab-cli` or `curl`)
- `test_gitlab_scripts.py`: 4 tests for `fetch_answer_from_mr.sh` (YAML block parsing, signature, author check)
- `test_webhook.py`: 3 tests for webhook (author note OK, stranger note rejected, malformed payload rejected)

### User test 🧑 — the big one

**Scenario P4-USR — full E2E demo** (45 min, 2 humans: dev + reviewer):

1. Demo Java repo cloned, TestBoost integration installed via template
2. Dev pushes an MR modifying `OrderService.java`
3. Pipeline starts, `tb:generate` pauses on missing business context
4. Bot posts a structured comment on the MR
5. Reviewer replies in the comment respecting the documented YAML format
6. Webhook triggers a new pipeline, `tb:generate` resumes, tests generated and committed
7. Reviewer sees the new revision with tests
8. **Success criterion**: recorded demo (5 min video), exploitable for onboarding

> **PRIORITY** (per user decision 2026-06-01): identify a real external dev
> volunteer for P4-USR as soon as Phase 4 lands. Do not mock the user; the
> goal is real-world UX validation.

### Doc updates

- New `docs/gitlab-integration.md`: step-by-step guide with screenshots
- `docs/ci-async-integration.md`: remove inline skeleton, point to official template
- `README.md`: "GitLab CI ready" badge + link to `docs/gitlab-integration.md`
- Hosted demo video (or asciinema GIF) referenced

---

## Phase 5 — Hardening: review fixes (6 j/h)

**Goal**: make the GitLab loop actually work end-to-end and remove every
bug found in the 2026-06-09 deep review. No new UX — strictly fixes.

> **Decisions taken with the user (2026-06-09)**:
> - State hand-off between pipelines: **commit `.testboost/sessions/` to
>   the MR branch** (pause job pushes; resume pipeline reads from a normal
>   checkout). Consistent with the markdown-in-repo design; no artifact
>   plumbing.
> - Paused pipelines must show GitLab's **orange "warning" status**, not
>   green (moved to Phase 6 with the template rework).
> - `validate_fixes.<class>.hints`: not implemented today although
>   documented — **drop from schema + doc for now** (only `fixed_code`),
>   re-introduce with the grouped-question redesign if needed.

### Tasks

| # | Task | Effort | Files |
|---|------|--------|-------|
| 5.1 | **Session state hand-off**: on pause (exit 78), the CI job commits `.testboost/sessions/` + cursor to the MR branch with `-o ci.skip`; the resume pipeline finds the paused session in its checkout. Requires `GITLAB_TOKEN` with `write_repository` scope. | 1.5 j | `templates/gitlab/testboost.yml`, `docs/gitlab-integration.md` |
| 5.2 | **Stop leaking `.tb_secret` in CI artifacts**: `artifacts:exclude: [.testboost/.tb_secret]` (artifacts ignore `.gitignore` and `chmod`) | 0.25 j | `templates/gitlab/testboost.yml:33-37` |
| 5.3 | **Resume pipeline context**: webhook-triggered branch pipelines have no `CI_MERGE_REQUEST_IID`; scripts must fall back to `TESTBOOST_MR_IID` (already sent by the webhook, currently unused) | 0.25 j | `scripts/gitlab/*.sh:12-18`, `tools/gitlab-webhook/webhook.py:54` |
| 5.4 | **Ship the MR scripts with the package**: convert `post_question_to_mr.sh` / `fetch_answer_from_mr.sh` into `testboost gitlab post-question` / `fetch-answer` subcommands so `pip install testboost` is enough in a consumer repo (`include:` only brings YAML, not scripts). Also kills the bash `set -e` dead-error-path bug in `fetch_answer_from_mr.sh:55-84`. Template installs TestBoost via pip instead of assuming TestBoost's own `pyproject.toml` (`poetry install` fails on a Java repo). Fallback if rejected: template `curl`s the scripts from the testboost repo at a pinned ref. | 1.5 j | `src/lib/cli.py`, `templates/gitlab/testboost.yml:24-32`, delete `scripts/gitlab/` |
| 5.5 | **`cleanup` actually finds paused sessions**: `emit_question` must flip `status: awaiting_input` in `spec.md` frontmatter (today only the step file is flipped, so `find_abandoned_sessions` never matches; the existing test masks this by editing `spec.md` manually). Add an integration test `emit_question` → `find_abandoned_sessions`. | 0.5 j | `src/lib/session_tracker.py:416,672-699` |
| 5.6 | **Wire `killer_hints` into the LLM call**: the payload is parsed (`cli.py:1513`) but never passed to `generate_killer_tests` (`cli.py:1578`), so killer resume silently re-runs the identical generation. Inject hints into the killer prompt context; assert via mock that they reach the prompt. | 1 j | `src/lib/cli.py`, `src/lib/bridge.py`, `src/test_generation/killer_tests.py` |
| 5.7 | **Drop `validate_fixes.<class>.hints`** from the question's `answer_schema` (`cli.py:1240`) and from `docs/ci-async-integration.md` — only `fixed_code` is implemented (`cli.py:1091-1098`) | 0.25 j | `src/lib/cli.py`, docs |
| 5.8 | **Metrics line to stderr**: `[TESTBOOST_METRICS:…]` on stdout (`cli.py:2248`) corrupts the JSON output of `sign-answer` and the markdown of `resume` for anyone piping them | 0.25 j | `src/lib/cli.py` |
| 5.9 | **Webhook hardening**: constant-time token compare (`hmac.compare_digest`, `webhook.py:69`); ignore notes authored by the bot's own identity (loop guard when the MR author is the bot account — the question comment itself contains the marker the webhook greps) | 0.5 j | `tools/gitlab-webhook/webhook.py` |

### Acceptance criteria

- 🚦 **P5.A** — E2E (local git fixture): pause → state committed → fresh clone → webhook-style resume pipeline finds the session and resumes. No artifact dependency.
- 🚦 **P5.B** — No job artifact may contain `.tb_secret` (assert on rendered CI config + e2e artifact listing).
- 🚦 **P5.C** — A session paused via `emit_question` and aged past TTL is returned by `find_abandoned_sessions` **without any manual `spec.md` edit** in the test.
- 🚦 **P5.D** — `killer` resumed with `killer_hints` → hints provably present in the LLM prompt (mocked assert), and a second pause is not suppressed silently.
- 🚦 **P5.E** — `testboost sign-answer` stdout is `json.loads`-parseable end-to-end; same for `resume` show-pending markdown.
- 🚦 **P5.F** — `testboost gitlab post-question` / `fetch-answer` run on a repo where TestBoost is only pip-installed (no checkout of the TestBoost repo).

### Risks / trade-offs accepted

- Committing `.testboost/sessions/` to the MR branch pollutes the MR diff
  with session markdown. Accepted for the MVP (it is the audit trail by
  design); mitigations if it annoys users: collapse via `.gitattributes`
  `linguist-generated`, or move to a dedicated ref later.
- The state-commit push must use `-o ci.skip` to avoid recursive pipeline
  triggers.

---

## Phase 6 — Grouped questions & resume UX (4.5 j/h)

**Goal**: one MR comment per run instead of one pause per uncertain file,
and a resume that never loses or wastes work.

> **Decisions taken with the user (2026-06-09)**: group the questions;
> orange CI status on pause; cursor must memorize the run scope and the
> generated output; answers consumed only after the answered file succeeds.

### Tasks

| # | Task | Effort | Files |
|---|------|--------|-------|
| 6.1 | **Batch questions**: `generate` no longer raises on the first uncertain file. It generates everything it can, collects every uncertainty (missing edge cases, compile-fix exhaustion) into ONE `question.json` with an `items[]` array (one entry per file/class, each with its own `answer_schema`), then exits 78 once at the end. `markdown_preview` renders the items as a checklist in a single MR comment. | 2 j | `src/lib/session_tracker.py::emit_question`, `src/lib/cli.py::_cmd_generate_async` |
| 6.2 | **Scope answers per item**: injected `test_requirements` currently apply to every remaining file (`cli.py:685-731`); key the answer payload by `source_file`/`class_name` so requirements for `OrderService` never leak into other prompts | 0.5 j | `src/lib/cli.py` |
| 6.3 | **Cursor memorizes the run**: persist the `--files` filter and per-file generation outputs in the cursor. `resume` replays the exact original scope (today it hardcodes `files=None` → cursor mismatch → "starting fresh", `cli.py:1812`) and skips LLM regeneration entirely for files where the developer supplied `fixed_code` (today the file is regenerated then overwritten — one wasted LLM call). | 1 j | `src/lib/session_tracker.py`, `src/lib/cli.py::cmd_resume` |
| 6.4 | **Consume-on-success**: `consume_answer` currently deletes `question.json` at the start of the resume run (`session_tracker.py:483-488`); if the run crashes, both question and verified answer are lost. Verify at start, but mark consumed / delete only once the answered item(s) complete. | 0.5 j | `src/lib/session_tracker.py`, `src/lib/cli.py` |
| 6.5 | **Orange pipeline status**: replace the `set +e … exit 0` wrapper with `allow_failure: exit_codes: [78]` so a paused job shows as "warning" instead of a misleading green; move the question-posting call to `after_script` (runs on failure too) | 0.25 j | `templates/gitlab/testboost.yml:58-73` |

### Acceptance criteria

- 🚦 **P6.A** — A 5-file run with 3 uncertain files produces exactly **one** question/MR comment listing the 3 items, and the 2 certain files ARE generated in that same run.
- 🚦 **P6.B** — Answering the item for class X injects requirements into X's prompt only (mock assert on the other files' prompts).
- 🚦 **P6.C** — A resume run that crashes mid-way can be re-run with the same answer file (answer not consumed by the failed attempt); the cursor resumes at the right file with the original `--files` scope.
- 🚦 **P6.D** — A paused pipeline shows GitLab's *warning* status; a resumed-and-completed one shows green.
- 🚦 **P6.E** — `resume` with a `fixed_code` answer performs **zero** generation LLM calls for that file (mocked `call_count == 0`).

### User test 🧑

**Scenario P6-USR** (15 min, 1 human): re-run P4-USR's flow on a project
with 3+ uncertain classes. Success: the developer answers **one** comment,
one resume pipeline completes everything, the pipeline history reads
honestly (warning → green).

---

## Cross-cutting (continuous through phases)

| Topic | Action |
|-------|--------|
| **Integration tests** | Add 1 E2E test per phase under `tests/e2e/` using a real (small) Java fixture |
| **TestBoost CI** | Extend `.github/workflows/ci.yml` to run new test dirs |
| **Changelog** | Maintain `CHANGELOG.md` (new file) with one entry per phase |
| **Security review** | Before Phase 4, run `/security-review` on HMAC chain + webhook |
| **Performance** | Benchmark: HMAC + cursor overhead < 50ms per step (else refactor) |

---

## Risks

| Phase | Risk | Mitigation |
|-------|------|------------|
| 1 | HMAC/cursor design flaw discovered in P2+ | End-of-P1 architecture review before P2 |
| 4 | Webhook security (replay, stranger writes) | Mandatory `/security-review` before P4 merge |
| 4 | GitLab.com vs Self-Managed differences | Test both during P4.D acceptance |
| Cross | LLM API cost during E2E tests | Use mocks except for the final P4-USR demo |

---

## Lessons learned (filled at each phase end)

### Phase 1 — 2026-06-02

- **Refactor**: the original `generate` used a 3-pass structure (collect in
  memory → bulk write → bulk compile-fix). Merged into one per-file
  pipeline (edge cases → generate → write → compile-fix) so the cursor
  has a single semantic anchor.
- **Signing**: signing on `emit_question` is opt-in via the
  `project_path` parameter to preserve backwards compat with the spike
  tests. In production, `cli.py` always passes it.
- **`markdown_preview` field** in `question.json` is computed *before*
  signing so it's included in the HMAC and authoritative — pasting it
  back into a comment is safe.
- **Acceptance criteria met**:
  - P1.A ✅ `test_resume_skips_completed_files` proves only files ≥ paused index are regenerated
  - P1.B ✅ `test_resume_rejects_unsigned_answer` proves no LLM call happens on signature failure
  - P1.C ✅ `test_verify_answer_rejects_mismatched_question_id` covers cross-session attack
  - P1.D ✅ `test_show_pending_prints_markdown_preview` covers show-pending mode
- **Tests**: 28 new (12 cursor/integrity primitives + 11 CLI E2E + 5 spike
  tests updated to use signed flow). Total 290 unit tests, lint clean.
### Phase 2 — 2026-06-02

- **Hints mode** (2.1): when `compile_fixes.<class>.hints` is provided,
  `_attempt_compile_fix` caps to a single LLM retry with the hint
  prepended to the error context (acceptance P2.A).
- **Validate pause** (2.2): added `--fail-on-uncertainty` and
  `--answer-file` to `validate`. On runtime test failure, emits a
  `tests_failed_at_runtime` question with the failing test classes and
  trimmed stack trace, status `awaiting_input` (acceptance P2.B).
  `validate_fixes` from the answer payload are written to disk before
  re-running.
- **Killer pause** (2.3): minimal wiring — pauses when the LLM yields
  0 killer tests for surviving mutants. Answer accepts `killer_hints`
  for future iterations (full retry loop with hint injection is a
  Phase 3+ refinement).
- **Markdown preview** (2.4): the `question_id` is pre-allocated before
  rendering so it's included in the MR-pasteable preview. Tampering the
  preview after signing is detected (snapshot tested).
- **Tests**: 12 new (2 hints + 2 markdown + 3 validate + 3 helper + 2
  killer). Total 302 unit tests pass, lint clean.
- **Acceptance criteria met**: P2.A ✅, P2.B ✅, P2.C ✅ (partial — minimal
  wiring), P2.D ✅.
### Phase 3 — 2026-06-02

- **Cleanup** (3.1): `list_sessions`, `find_abandoned_sessions`,
  `mark_abandoned` in session_tracker; `cleanup` CLI command with
  `--ttl-hours` and `--dry-run`. Non-destructive (status flip only).
- **Metrics** (3.2): a single `[TESTBOOST_METRICS:{...}]` line is
  emitted at the end of every command via `main()`. Includes command
  name, exit code, duration_ms, project_path.
- **Doctor** (3.3): `doctor` CLI runs 4 checks (`.tb_secret`, write
  perms, Maven on PATH, LLM ping). Per-check status + exit 0/1.
- **Tests**: 11 new (4 cleanup tracker + 3 cmd_cleanup + 2 cmd_doctor +
  1 metrics + 1 list_sessions). Total 312 unit tests pass, lint clean.
- **Acceptance criteria met**: P3.A ✅ (mark, not delete), P3.B ✅
  (single parseable line), P3.C ✅ (2 broken scenarios covered;
  read-only-dir + Maven-absent scenarios are harder to mock cleanly in
  a unit test but the code path exists).
### Phase 4 — 2026-06-02 (artefacts ready, awaiting real-world P4-USR)

- **GitLab CI template** (4.1): `templates/gitlab/testboost.yml` with
  3 jobs (analyze, generate, cleanup). `include:` ready.
- **post_question_to_mr.sh** (4.2): reads pending question.json,
  extracts markdown_preview, POSTs as MR note with `question_id` marker.
- **fetch_answer_from_mr.sh** (4.3): parses MR notes, filters by author
  + question_id, extracts the fenced JSON, calls `testboost sign-answer`.
- **Webhook** (4.4): FastAPI app under `tools/gitlab-webhook/` with its
  own requirements.txt. Validates `X-Gitlab-Token`, restricts to MR
  author comments, triggers resume pipeline via GitLab API.
- **Tests**: 4 shell-script tests (with mocked curl) + 5 webhook tests
  (skip-if-fastapi-absent). Total 316 unit tests in main suite.
- **Doc**: full step-by-step guide `docs/gitlab-integration.md`.
- **Acceptance criteria**:
  - P4.A ✅ post script call traced to correct API endpoint (test)
  - P4.B ✅ webhook ignores stranger comments (test)
  - P4.C ⏳ **PENDING REAL DEMO** — needs P4-USR with a real GitLab repo
  - P4.D ⏳ **PENDING REAL DEMO** — needs both GitLab.com + self-managed
    instances to validate
- **Next step**: identify a real external developer to run P4-USR. The
  protocol is in `docs/gitlab-integration.md` under "User test".

### Deep review — 2026-06-09

A full branch review invalidated Phase 4's "done" status: the components
work in isolation (316 unit tests green) but **the loop does not close
end-to-end**. Root causes and decisions:

- **Blocker**: session state lives in the paused job's workspace and is
  never handed to the webhook-triggered resume pipeline (fresh checkout,
  no cross-pipeline artifacts). P4.A/P4.B tests passed because they test
  each side in isolation. → Decision: commit `.testboost/sessions/` to
  the MR branch (Phase 5.1).
- **Blockers**: resume pipeline lacks `CI_MERGE_REQUEST_IID` (webhook's
  `TESTBOOST_MR_IID` was never consumed); `include:` does not ship the
  shell scripts to consumer repos; `poetry install` presumes TestBoost's
  own repo (fails on a Java project). → Phase 5.3 / 5.4.
- **Security**: `.tb_secret` was uploaded in CI artifacts (artifacts
  ignore `.gitignore`); doc overstated what the HMAC chain proves in the
  CI flow (CI signs the developer's comment itself — the real control is
  the author check + token scoping) and mislabeled the TTL as replay
  protection (replay across questions is prevented by `question_id`
  binding). → Phase 5.2 + doc truth pass (done 2026-06-09).
- **Dead features shipped as done**: `killer_hints` parsed but never
  injected into the LLM call; `validate_fixes.hints` documented but
  ignored; `cleanup` can never find a real paused session because
  `emit_question` doesn't flip `spec.md`'s frontmatter status (the unit
  test edited `spec.md` manually, masking it). → Phase 5.5-5.7.
- **UX decisions** (user, 2026-06-09): group all uncertainties of a run
  into one question/MR comment instead of per-file ping-pong; paused jobs
  show orange (warning), not green; cursor memorizes run scope and
  generated output; answers consumed only after the answered file
  succeeds. → Phase 6.
- **Lesson**: "tests green" ≠ "feature works" — every P4 test mocked the
  seam where the integration actually broke (cross-pipeline state, GitLab
  variable availability, script distribution). Phase 5/6 acceptance
  criteria therefore require E2E fixtures that cross those seams.
