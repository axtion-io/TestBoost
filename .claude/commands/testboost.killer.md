---
description: Generate killer tests to eliminate surviving mutants
---

# /testboost.killer

Generate tests specifically designed to kill surviving mutants identified by mutation testing.

## Prerequisites

The mutation testing step must be completed first. If not, suggest running `/testboost.mutate`.

## What you will do

1. Determine the project path from `$ARGUMENTS` or the current session
2. Run killer test generation:

```bash
bash testboost_lite/scripts/tb-killer.sh <project_path> --verbose
```

   To limit the number of killer tests:

```bash
bash testboost_lite/scripts/tb-killer.sh <project_path> --max-tests 15 --verbose
```

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the results at `<project_path>/.testboost/sessions/<current_session>/killer-tests.md`
5. **Present results** to the user:
   - Number of killer test classes generated
   - Number of mutants targeted
   - File paths of generated killer tests
6. **Suggest next steps**:
   - Run `/testboost.validate` to compile and execute the killer tests
   - Run `/testboost.mutate` again to verify the mutation score improved

## How killer test generation works

- Reads surviving mutants from the mutation testing step
- Groups mutants by class
- When source code is available, uses LLM with a specialized prompt to generate targeted tests
- Falls back to template-based generation with mutation-specific strategies:
  - Boundary mutants → boundary value tests
  - Negated conditionals → both-branches tests
  - Return value mutants → exact value assertions
  - Void method mutants → side-effect verification
- Generated files are named `*KillerTest.java`

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

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **STOP IMMEDIATELY** — do NOT attempt to generate killer tests yourself
2. **Report the error** to the user exactly as printed by TestBoost
3. **Do NOT write** Java test files or any test code manually
4. **Suggest** checking LLM provider configuration and retry

**You are NOT TestBoost. You are the assistant that calls TestBoost.**

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
bash testboost_lite/scripts/tb-verify.sh <project_path> '<full_token_line>'
```

4. The verify command must print `[TESTBOOST_VERIFY:OK]` — if it prints `[TESTBOOST_VERIFY:FAILED]` or exits non-zero, STOP and report the failure to the user
