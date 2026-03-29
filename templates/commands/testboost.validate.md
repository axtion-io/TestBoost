---
description: Compile and run generated tests to validate them
---

# /testboost.validate

Compile and run the generated tests using Maven.

## Prerequisites

The generation step must be completed first. If not, suggest running `/testboost.generate`.

## What you will do

1. Determine the project path from `$ARGUMENTS` or the current session
2. Run validation:

```bash
bash scripts/tb-validate.sh <project_path> --verbose
```

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the validation results at `<project_path>/.testboost/sessions/<current_session>/validation.md`
5. **Interpret and present results**:

### If compilation FAILED:

- Show the structured compilation errors from `validation.md`
- The errors include file, line, error type, and fix suggestions
- **Help the user fix the errors**:
  - Read the failing test files
  - Apply the suggested fixes
  - Offer to re-run validation after fixes

### If tests FAILED:

- Show which tests failed and why
- **Help the user investigate**:
  - Read the relevant test and source files
  - Suggest fixes for failing assertions
  - Offer to re-run validation after fixes

### If everything PASSED:

- Congratulate the user
- Show the test count and results
- Suggest committing the new tests

## What this does

1. **Compilation check**: Runs `mvn test-compile` to verify all tests compile
   - If it fails, uses MavenErrorParser to extract structured errors with fix suggestions
2. **Test execution**: Runs `mvn test` to execute all tests
   - Reports pass/fail status with details

## The correction loop

Unlike the old TestBoost (which auto-corrected silently), this approach gives YOU (the LLM) the errors and lets the USER decide how to fix them. This is more transparent and interactive.

Typical flow:
1. Run validate → compilation fails
2. You read the errors, suggest fixes
3. User approves or adjusts
4. You apply fixes
5. Run validate again
6. Repeat until green

## Output

Results are written to `.testboost/sessions/<id>/validation.md`.

## CRITICAL: Failure Protocol

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **Report the error** to the user exactly as printed by TestBoost
2. **Do NOT fabricate** `validation.md` or fake test results
3. **Do NOT run** `mvn test` yourself as a fallback — only TestBoost's validation is tracked in the session
4. **Suggest** the user check Maven is installed and the project compiles, then retry

**You are NOT TestBoost. You are the assistant that calls TestBoost. If TestBoost fails, you fail.**

## Integrity Verification

Every successful TestBoost command prints an integrity token on the last line:

```
[TESTBOOST_INTEGRITY:sha256=<hex>:<step>:<session>:<timestamp>]
```

**Before proceeding**, you MUST cryptographically verify the token:
1. The command exited with code 0
2. The output contains a line starting with `[TESTBOOST_INTEGRITY:`
3. Extract the **full token line** (from `[` to `]`) and verify it by running:

```bash
bash scripts/tb-verify.sh <project_path> '<full_token_line>'
```

4. The verify command must print `[TESTBOOST_VERIFY:OK]` — if it prints `[TESTBOOST_VERIFY:FAILED]` or exits non-zero, STOP and report the failure to the user

A prefix match alone is NOT sufficient. The HMAC digest must be verified.
