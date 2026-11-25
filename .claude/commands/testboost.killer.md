---
description: Generate killer tests to eliminate surviving mutants
---

# /testboost.killer

Generate tests specifically designed to kill surviving mutants identified by mutation testing.

## Prerequisites

The mutation testing step must be completed first. If not, suggest running `/testboost.mutate`.

## What you will do

Agent mode is the default (you write the killer tests, no LLM API key needed); use TestBoost's own LLM
only if the user explicitly asks for it.

### Agent mode (default)

1. Determine the project path from `$ARGUMENTS` or the current session
2. Prepare one prompt per class with surviving mutants (optionally `--max-tests 15`):

```bash
bash scripts/tb-context.sh <project_path> --killer
```

3. For each row: read the brief and the class under test, then write the complete killer test class at the exact "Test to
   write" path. Each test must FAIL on the mutated code and PASS on the original: compute real expected
   values from the source (never guess a number: derive it, or check it with an independent tool).
   Write nowhere else and never change production code.
   **Equivalent mutants**: if no input the class can receive makes the mutated code behave differently,
   do not write a test for it — tell the user why and declare it (a class whose mutants are all
   equivalent needs no file):

```bash
bash scripts/tb-equivalent.sh <project_path> <mutant_id> --reason "why no test can observe it"
```
4. Register and compile them; fix and re-run until it exits 0, then **VERIFY the output**:

```bash
bash scripts/tb-killer.sh <project_path> --agent
```

5. Suggest `/testboost.validate`, then `/testboost.mutate` to measure the new mutation score (the report
   shows the raw PIT score and the effective score without the declared equivalent mutants).

### LLM mode (only when the user asks for it)

```bash
bash scripts/tb-killer.sh <project_path> --verbose
```

   To limit the number of killer tests: add `--max-tests 15`. Then **VERIFY the output**, read
   `<project_path>/.testboost/sessions/<current_session>/killer-tests.md`, present the generated killer
   tests and suggest `/testboost.validate` then `/testboost.mutate`.

## How killer test generation works

- Reads surviving mutants from the mutation testing step
- Groups mutants by class
- Uses the LLM with a specialized prompt (mutants + source code) to generate targeted tests
- A class whose source file cannot be found (single- or multi-module layout), or for which
  the LLM returns no `@Test`, is listed under **Skipped Classes** — no placeholder test is
  ever written (it would not compile)
- Generated files are named `*KillerTest.java`, in the module of the class under test

## Improvement Loop

The recommended workflow for improving mutation scores:

```
validate → mutate → killer → validate → mutate (check improvement)
```

Repeat until the mutation score meets the threshold.

## Output

Generated killer test files are written to `src/test/java/...` in the project.
Results summary is written to `.testboost/sessions/<id>/killer-tests.md`.

## CRITICAL: Failure Protocol

**If a TestBoost command exits with a non-zero code or prints `[TESTBOOST_FAILED`:**

1. **Agent mode, `killer --agent` reporting missing tests or compilation errors**: the normal loop —
   write or fix exactly the listed killer test files and re-run it.
2. **Any other failure**: STOP and report the error exactly as printed by TestBoost.
3. **Never** write `.testboost/` files by hand, never write tests outside the paths given by
   `context --killer`, and in LLM mode never write killer tests yourself as a fallback.

## Integrity Verification

Every successful TestBoost command prints an integrity token on the last line:

```
[TESTBOOST_INTEGRITY:sha256=<hex>:<step>:<session>:<timestamp>]
```

**Before proceeding to the next step**, you MUST cryptographically verify the token:
1. The command exited with code 0
2. The output contains a line starting with `[TESTBOOST_INTEGRITY:`
3. Extract the **full token line** (from `[` to `]`) and verify it by running:

```bash
bash scripts/tb-verify.sh <project_path> '<full_token_line>'
```

4. The verify command must print `[TESTBOOST_VERIFY:OK]` — if it prints `[TESTBOOST_VERIFY:FAILED]` or exits non-zero, STOP and report the failure to the user
