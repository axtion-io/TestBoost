# Asynchronous CI Integration (Human-in-the-loop)

> Status: **spike** — primitives are merged but the full GitLab/GitHub bot
> orchestration layer is left to the integrator. See "What's not done" below.

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
# → answer.json renamed to answer.json.consumed inside the session
# → answer payload injected into the step (see schema below)
# → exit 0 on success, or another exit-78 cycle if more info is needed
```

## Triggers (when does TestBoost pause?)

Two `generate` triggers are wired today; both require `--fail-on-uncertainty`:

### 1. Missing business context

When `analyze_edge_cases` returns no scenarios for a source file AND no
answer payload provides `test_requirements`, TestBoost emits:

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
    "test_requirements": [
      {"scenario": "string", "expected": "string"}
    ]
  }
}
```

### 2. Compilation fix exhausted

After `_MAX_COMPILE_FIX_ATTEMPTS` (3) LLM-driven repair attempts on a test
file still fail to compile, TestBoost emits:

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
      "OrderService": {"fixed_code": "string (full test file content)"}
    }
  }
}
```

## `answer.json` schema

A single file, JSON object at the top level. Recognised keys:

| Key | Type | Effect |
|-----|------|--------|
| `test_requirements` | `[{scenario, expected}, …]` | Appended to LLM context for every file in the run (substitutes for missing edge cases). |
| `compile_fixes` | `{ "<ClassName>": {"fixed_code": "…"} }` | Overrides the LLM-generated test file on disk for that class before the compile-fix retry loop. If the supplied code still fails to compile, the retry loop runs against it (and may pause again). |

Unknown keys are ignored — forward-compatible.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Step completed |
| 1 | Hard failure (LLM down, bad config, exception) |
| 78 | Step paused — `question.json` written, status = `awaiting_input` |

CI runners should treat **78 as neutral**: do not mark the pipeline red,
do not block the MR. Configure `allow_failure: false` only on exit ≠ 78.
A GitLab `rules:` clause can branch on the job's exit code via
`when: on_failure` combined with a parsed marker, or you can mirror the
exit code into an `artifacts:reports:dotenv` variable.

## Stdout markers (for parsing)

- Success: `[TESTBOOST_INTEGRITY:sha256=<hex>:<step>:<session_id>:<timestamp>]`
- Pause:   `[TESTBOOST_AWAITING_INPUT:step=<step>:question=<path>]`
- Hard fail: `[TESTBOOST_FAILED:exit_code=<n>:step=<step>]`

## Suggested GitLab CI skeleton

```yaml
stages: [analyze, generate, await-human, resume]

.tb: &tb
  image: python:3.11-slim
  before_script:
    - pip install poetry && poetry install --no-root
  artifacts:
    when: always
    paths: [.testboost/]
    expire_in: 1 week

tb:generate:
  <<: *tb
  stage: generate
  script:
    - |
      set +e
      python -m testboost generate "$CI_PROJECT_DIR" --fail-on-uncertainty
      code=$?
      if [ $code -eq 78 ]; then
        scripts/post_question_to_mr.sh   # POST .testboost/sessions/*/question.json
        exit 0                            # job vert, MR non bloquée
      fi
      exit $code
```

A `resume` job (manual or webhook-triggered) downloads the previous
artifact, builds `answer.json` from the MR reply, and runs
`generate --answer-file answer.json`.

## Per-file cursor (Phase 1)

The `generate` command persists its progress through the gap list in
`.testboost/sessions/<id>/generation_cursor.json`:

```json
{
  "target_files": ["A.java", "B.java", "C.java"],
  "current_index": 1,
  "completed_files": ["A.java"],
  "updated_at": "2026-06-02T10:00:00Z"
}
```

On a resume, files with index < `current_index` are **skipped** entirely
(no LLM call, no compile-fix). The cursor advances after each per-file
success and is **cleared on full completion**. A pause re-saves the
cursor pointing at the file that needs human input.

If you change the gap list between runs (e.g. by re-running `analyze` →
`gaps`), the cursor is invalidated and the loop restarts from index 0.

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
  "test_requirements": [
    {"scenario": "negative price must throw", "expected": "IllegalArgumentException"}
  ]
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
| `generate` | edge_case analysis yields nothing for a source file | `test_requirements` |
| `generate` | compile-fix exhausts its retry budget | `compile_fixes` |
| `validate` | tests fail at runtime | `validate_fixes` |
| `killer` | killer-test LLM call yields 0 tests | `killer_hints` |

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

The same pattern applies to `validate_fixes.<class>.hints` and to
`killer_hints` (natural-language per surviving mutant).

## Operations (Phase 3)

### Session cleanup

```bash
python -m testboost cleanup ./my-project --ttl-hours 24 --dry-run
python -m testboost cleanup ./my-project --ttl-hours 24
```

Sessions in `awaiting_input` older than the TTL are flipped to status
`abandoned`. The files are **preserved** (audit trail). Run periodically
from a scheduled CI job, or manually.

### Health check

```bash
python -m testboost doctor ./my-project
```

Verifies: `.tb_secret` present, project dir writable, `mvn` on PATH, LLM
reachable. Exit 0 if all green, 1 if any issue.

### Metrics

Every command emits a single JSON line to stdout on exit:

```
[TESTBOOST_METRICS:{"command":"generate","exit_code":0,"duration_ms":12345,"project_path":"/..."}]
```

Parseable by CI dashboards (Datadog, Prometheus push-gateway, etc.).

## What's *not* done (still open)

- **GitLab automation layer.** Scripts to post questions and harvest
  answers from MR comments. (Phase 4)

## Primitives reference

In `src/lib/session_tracker.py`:

- `STATUS_AWAITING_INPUT = "awaiting_input"` — distinct from `failed`
- `EXIT_AWAITING_INPUT = 78`
- `QUESTION_FILENAME`, `ANSWER_FILENAME`, `ANSWER_CONSUMED_FILENAME`, `GENERATION_CURSOR_FILENAME`
- `class AwaitingInputError(Exception)` — raise from a step to trigger pause
- `emit_question(session_dir, step_name, payload, project_path=None, session_id=None) -> Path`
- `consume_answer(session_dir, answer_file, project_path=None, ttl_hours=None) -> dict`
- `save_generation_cursor / load_generation_cursor / clear_generation_cursor`

In `src/lib/integrity.py`:

- `class SignatureError(Exception)` / `class ExpiredQuestionError(Exception)`
- `sign_question(payload, project_path) -> dict`
- `verify_question(payload, project_path) -> bool`
- `sign_answer(payload, question, project_path) -> dict`
- `verify_answer(answer, question, project_path, ttl_hours=24)` — raises on any failure
