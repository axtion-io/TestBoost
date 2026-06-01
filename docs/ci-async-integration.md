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

## What's *not* done (out of spike scope)

These remain on the roadmap before this is a production-grade MVP:

1. **Per-file cursor.** Today, a resume re-runs `generate` over the
   *entire* gap list. Tests that already compiled get regenerated (LLM
   cost). Persist `current_file_index` in `spec.md` to skip the rest.
2. **Dedicated `resume` command.** `generate --answer-file` works but a
   thin `python -m testboost resume <project> --answer-file …` would be
   clearer for operators.
3. **HMAC on `question.json` ↔ `answer.json`.** A malicious comment
   could inject arbitrary `fixed_code`. Sign the question with `.tb_secret`,
   require the signature to be echoed back in the answer.
4. **Hints (vs full fixed_code) for compile-fix.** Developers will more
   often write a natural-language hint than paste 200 lines of Java in a
   comment. Add `compile_fixes.<class>.hints: [string]` and feed it to
   `fix_compilation_errors` as additional context for one more retry.
5. **`unsubscribe` semantics.** What happens if a paused session is
   abandoned (MR closed)? Add TTL-based cleanup via
   `session_retention_days`.
6. **Wire the same pattern to other steps.** Currently only `generate`
   pauses. The same primitives (`emit_question`, `consume_answer`,
   `STATUS_AWAITING_INPUT`, exit 78) apply trivially to `validate`,
   `mutate`, and `killer`.

## Primitives reference

All in `src/lib/session_tracker.py`:

- `STATUS_AWAITING_INPUT = "awaiting_input"` — distinct from `failed`
- `EXIT_AWAITING_INPUT = 78`
- `QUESTION_FILENAME`, `ANSWER_FILENAME`, `ANSWER_CONSUMED_FILENAME`
- `class AwaitingInputError(Exception)` — raise from a step to trigger pause
- `emit_question(session_dir, step_name, payload) -> Path`
- `consume_answer(session_dir, answer_file) -> dict`
