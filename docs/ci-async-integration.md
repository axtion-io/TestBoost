# Asynchronous CI Integration (Human-in-the-loop)

> Status: **implemented** (Phases 1-6) — primitives, batched questions and
> the full GitLab orchestration (template + webhook + `testboost gitlab …`
> subcommands) are merged. Real-world validation (P4-USR) pending; GitHub
> support is not started. See "What's not done" below.

TestBoost ships a small mechanism that lets a CI pipeline pause when it
needs information from a human (e.g. business rules, manual compile fix)
and resume on a later run with the answer attached as a file. This makes
it possible to drive TestBoost from a Merge Request comment loop instead
of a synchronous tunnel.

## TL;DR

```bash
# 1st run — fails-soft when more info is needed
python -m testboost generate ./my-project --fail-on-uncertainty
# → writes .testboost/sessions/NNN-…/question.json
# → step status: awaiting_input
# → stdout marker: [TESTBOOST_AWAITING_INPUT:step=generation:question=…]
# → exit code 78 (sysexits EX_CONFIG, reused as "human action required")

# Your CI script posts question.json to the MR; the developer replies;
# a webhook (your code) builds answer.json and relaunches the pipeline.

# 2nd run — resumes with the answer
python -m testboost generate ./my-project --answer-file ./answer.json
# → answer verified at startup, but only marked consumed
#   (answer.json.consumed + question.json cleared) once the answered work
#   SUCCEEDS — a crashed resume can be retried with the same answer file
# → answer payload injected into the step (see schema below)
# → exit 0 on success, or another exit-78 cycle if more info is needed
```

## Triggers (when does TestBoost pause?)

Two `generate` triggers are wired today; both require `--fail-on-uncertainty`.
**Uncertainties are batched**: the run generates everything it can, collects
every uncertainty, and emits ONE question at the end. With a single open
item the payload is flat (below); with several items it becomes a batch
payload (see "Batched questions").

### 1. Missing business context

When `analyze_edge_cases` returns no scenarios for a source file AND no
answer payload provides `test_requirements` for that class, the file is
deferred and this item is queued:

```json
{
  "kind": "missing_business_context",
  "step": "generation",
  "subject": {
    "source_file": "src/main/java/.../OrderService.java",
    "class_name": "OrderService",
    "class_type": "service"
  },
  "question": "No edge cases were derived for `OrderService`. …",
  "answer_schema": {
    "test_requirements": {
      "OrderService": [{"scenario": "string", "expected": "string"}]
    }
  }
}
```

### 2. Compilation fix exhausted

After `_MAX_COMPILE_FIX_ATTEMPTS` (3) LLM-driven repair attempts on a test
file still fail to compile, the file is deferred (its test path is kept in
the cursor so a `fixed_code` answer is applied **without regenerating**):

```json
{
  "kind": "compilation_fix_exhausted",
  "step": "generation",
  "subject": {
    "class_name": "OrderService",
    "test_file": "/.../OrderServiceTest.java",
    "attempts": 3
  },
  "question": "Could not fix compilation of `OrderService` after 3 LLM attempts. …",
  "compile_errors": "[ERROR] OrderServiceTest.java:[5,12] cannot find symbol …",
  "current_test_code": "<truncated to 8000 chars>",
  "answer_schema": {
    "compile_fixes": {
      "OrderService": {
        "fixed_code": "string (full test file content)",
        "hints": ["natural-language hint for the LLM"]
      }
    }
  }
}
```

### Batched questions (Phase 6)

When several files need input in the same run, `question.json` carries an
`items` array plus a combined `answer_schema`; the `markdown_preview`
renders everything as ONE MR comment:

```json
{
  "kind": "batch",
  "step": "generation",
  "question": "2 file(s) need your input to finish this generation run (3 other file(s) were generated successfully).",
  "items": [ { "kind": "missing_business_context", "...": "…" },
             { "kind": "compilation_fix_exhausted", "...": "…" } ],
  "answer_schema": {
    "test_requirements": { "OrderService": [ … ] },
    "compile_fixes": { "UserController": { … } }
  }
}
```

One signed answer file addresses all items at once. Items left
unanswered are re-deferred: the next run emits a new (smaller) question.

## `answer.json` schema

A single file, JSON object at the top level. Recognised keys:

| Key | Type | Effect |
|-----|------|--------|
| `test_requirements` | `{ "<ClassName>": [{scenario, expected}, …] }` | Injected into the LLM context **of that class only** (substitutes for missing edge cases). A bare list (legacy form) applies to every file in the run. |
| `compile_fixes` | `{ "<ClassName>": {"fixed_code": "…"} or {"hints": […]} }` | `fixed_code` replaces the test file on disk — without re-running generation when the file was deferred. `hints` grant ONE more LLM fix retry. If the supplied code still fails to compile, the question is re-emitted. |
| `killer_hints` | `{ "<ClassName.methodName>": "hint" }` | Appended to the killer-test LLM prompt for the matching class. |

Unknown keys are ignored — forward-compatible.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Step completed |
| 1 | Hard failure (LLM down, bad config, exception) |
| 78 | Step paused — `question.json` written, status = `awaiting_input` |

CI runners should treat **78 as neutral**: do not mark the pipeline red,
do not block the MR. On GitLab, use:

```yaml
allow_failure:
  exit_codes: [78]
```

so a paused job shows as an orange "warning" — honest, without blocking
the pipeline. This is what the official template does.

## Markers (for parsing)

- Success (stdout): `[TESTBOOST_INTEGRITY:sha256=<hex>:<step>:<session_id>:<timestamp>]`
- Pause (stdout):   `[TESTBOOST_AWAITING_INPUT:step=<step>:question=<path>]`
- Metrics (stderr): `[TESTBOOST_METRICS:{...}]`

## GitLab CI

Use the official template — see `docs/gitlab-integration.md`. It wires
the whole loop: orange pause status, session state committed to the MR
branch, question posted via `testboost gitlab post-question`, resume job
fetching the answer via `testboost gitlab fetch-answer`.

## Per-file cursor (Phase 1, extended in Phase 6)

The `generate` command persists its progress through the gap list in
`.testboost/sessions/<id>/generation_cursor.json`:

```json
{
  "target_files": ["A.java", "B.java", "C.java"],
  "current_index": 2,
  "completed_files": ["A.java", "C.java"],
  "files_filter": ["service/"],
  "deferred": [
    {"source_file": "B.java", "class_name": "B",
     "test_path": "src/test/java/BTest.java",
     "reason": "compilation_fix_exhausted"}
  ],
  "updated_at": "2026-06-02T10:00:00Z"
}
```

On a resume, files listed in `completed_files` are **skipped** entirely
(no LLM call, no compile-fix). `files_filter` records the original
`--files` patterns so `resume` replays the exact same scope. `deferred`
lists the files awaiting input; for a `compilation_fix_exhausted` entry,
a `fixed_code` answer is written straight to `test_path` — **no
regeneration LLM call**. The cursor is **cleared on full completion**.

If you change the gap list between runs (e.g. by re-running `analyze` →
`gaps`), the cursor is invalidated and the loop restarts from scratch.

## Signing answers (Phase 1)

Every question is HMAC-signed with the project's `.tb_secret`. An answer
is rejected unless it:

1. Carries the same `question_id` as the pending question,
2. Has a valid signature over its content (`signature` field at the top),
3. Was generated before the question's TTL elapsed (default 24h).

### Producing a signed answer

```bash
# Capture the pending question
cp .testboost/sessions/001-xxx/question.json /tmp/q.json

# Author your raw answer (just the payload, no signature)
cat > /tmp/raw_answer.json <<'EOF'
{
  "test_requirements": {
    "OrderService": [
      {"scenario": "negative price must throw", "expected": "IllegalArgumentException"}
    ]
  }
}
EOF

# Sign it
python -m testboost sign-answer ./my-project \
  --question-file /tmp/q.json \
  --answer-file /tmp/raw_answer.json \
  --output /tmp/signed_answer.json
```

### Resuming with a signed answer

```bash
# Show pending question (markdown_preview, ready to paste into a MR comment)
python -m testboost resume ./my-project

# Apply the answer
python -m testboost resume ./my-project --answer-file /tmp/signed_answer.json
```

`resume` exits 0 if the answer is accepted, 1 on signature/TTL failure,
or 2 if no question is pending.

## Pause triggers — supported steps (Phase 2)

The HITL pattern is now wired to three steps:

| Step | `--fail-on-uncertainty` triggers a pause when… | Answer key |
|------|-----------------------------------------------|-----------|
| `generate` | edge_case analysis yields nothing for a source file | `test_requirements` (keyed per class) |
| `generate` | compile-fix exhausts its retry budget | `compile_fixes` (`fixed_code` or `hints`) |
| `validate` | tests fail at runtime | `validate_fixes` (`fixed_code` only) |
| `killer` | killer-test LLM call yields 0 tests | `killer_hints` (injected into the killer prompt) |

`killer` pauses again if the provided hints still yield 0 tests — the new
question echoes the previously-tried hints (`subject.previous_hints`)
instead of silently succeeding with nothing.

## Hints mode (Phase 2.1)

For `compile_fixes`, the developer can choose between:

- **`fixed_code`** — paste the full corrected test file
- **`hints`** — write natural-language guidance (the LLM gets exactly **one**
  more retry with the hints appended to the error context)

If both are provided, `fixed_code` wins.

```json
{
  "compile_fixes": {
    "OrderServiceTest": {
      "hints": [
        "use Mockito.mock(...) instead of @Mock",
        "the constructor expects an OrderRepository, not a UserRepository"
      ]
    }
  }
}
```

Scope of hints per step:

- `compile_fixes.<class>.hints` — implemented (one extra LLM fix retry).
- `killer_hints` — implemented: matching hints are appended to the
  killer-test LLM prompt (keys `ClassName` or `ClassName.methodName`,
  simple or fully-qualified).
- `validate_fixes` accepts **`fixed_code` only** — runtime-failure repair
  has no LLM retry loop, so hints would be silently ignored; the schema
  doesn't advertise them.

## Operations (Phase 3)

### Session cleanup

```bash
python -m testboost cleanup ./my-project --ttl-hours 24 --dry-run
python -m testboost cleanup ./my-project --ttl-hours 24
```

Sessions in `awaiting_input` older than the TTL are flipped to status
`abandoned`. The files are **preserved** (audit trail). Run periodically
from a scheduled CI job, or manually. `emit_question` flips the
session-level status in `spec.md` (and a resumed step flips it back), so
cleanup detects real pauses without any manual bookkeeping.

### Health check

```bash
python -m testboost doctor ./my-project
```

Verifies: `.tb_secret` present, project dir writable, `mvn` on PATH, LLM
reachable. Exit 0 if all green, 1 if any issue.

### Metrics

Every command emits a single JSON line to **stderr** on exit (stderr, so
piping the stdout of `sign-answer` or `resume` stays clean):

```
[TESTBOOST_METRICS:{"command":"generate","exit_code":0,"duration_ms":12345,"project_path":"/..."}]
```

Parseable by CI dashboards (Datadog, Prometheus push-gateway, etc.).

## What's *not* done (still open)

- **Real-world validation** — the loop is implemented and unit-tested
  end-to-end, but P4-USR (a real GitLab project, two humans, < 5 min
  round-trip) has not been run yet. See `docs/gitlab-integration.md`.
- **Hints for `validate`** — runtime-failure repair accepts `fixed_code`
  only; an LLM retry loop with hints could be added later if the demand
  shows up.

## Primitives reference

In `src/lib/session_tracker.py`:

- `STATUS_AWAITING_INPUT = "awaiting_input"` — distinct from `failed`
- `EXIT_AWAITING_INPUT = 78`
- `QUESTION_FILENAME`, `ANSWER_CONSUMED_FILENAME`, `GENERATION_CURSOR_FILENAME`
- `class AwaitingInputError(Exception)` — raise from a step to trigger pause
- `emit_question(session_dir, step_name, payload, project_path=None, session_id=None) -> Path`
  — payloads with an `items` list render as a batch question
- `load_and_verify_answer(session_dir, answer_file, project_path=None, ttl_hours=None) -> dict`
  — verify without consuming (crash-safe resume)
- `finalize_answer(session_dir, payload)` — mark consumed + clear the question
- `consume_answer(...)` — one-shot load_and_verify + finalize
- `save_generation_cursor / load_generation_cursor / clear_generation_cursor`
  — the cursor also persists `files_filter` (original `--files` scope,
  replayed by `resume`) and `deferred` (files awaiting input, with their
  test path for no-regeneration fixed_code application)

In `src/lib/integrity.py`:

- `class SignatureError(Exception)` / `class ExpiredQuestionError(Exception)`
- `sign_question(payload, project_path) -> dict`
- `verify_question(payload, project_path) -> bool`
- `sign_answer(payload, question, project_path) -> dict`
- `verify_answer(answer, question, project_path, ttl_hours=24)` — raises on any failure
