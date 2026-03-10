---
description: Identify test coverage gaps in the Java project
---

# /testboost.gaps

Identify which source files are missing test coverage.

## Prerequisites

The analysis step must be completed first. If not, suggest running `/testboost.analyze`.

## What you will do

1. Determine the project path from `$ARGUMENTS` or the current session
2. Run the gap analysis:

```bash
bash testboost_lite/scripts/tb-gaps.sh <project_path> --verbose
```

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the coverage gaps file at `<project_path>/.testboost/sessions/<current_session>/coverage-gaps.md`
5. **Present the gaps** to the user:
   - Show the coverage percentage
   - List the files that need tests, with priority (high for services/controllers)
   - List files that already have tests
6. **Ask the user which files to generate tests for**:
   - All gaps? (default)
   - A specific subset? (let them pick from the list)
   - Only high priority files?
7. Suggest running `/testboost.generate` next

## How gaps are identified

- Compares testable source files (from analysis) against existing `*Test.java` / `*Tests.java` files
- A source file like `UserService.java` is "covered" if `UserServiceTest.java` exists
- Priority is assigned based on class type (services and controllers are high priority)

## Output

Results are written to `.testboost/sessions/<id>/coverage-gaps.md` with a prioritized table.

## CRITICAL: Failure Protocol

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **STOP IMMEDIATELY** — do NOT attempt to identify coverage gaps yourself
2. **Report the error** to the user exactly as printed by TestBoost
3. **Do NOT create** `coverage-gaps.md` or write any gap analysis manually
4. **Do NOT scan** the project's test directory and fabricate a gap analysis
5. **Suggest** the user check the error and retry

**You are NOT TestBoost. You are the assistant that calls TestBoost. If TestBoost fails, you fail.**

## Integrity Verification

Every successful TestBoost command prints an integrity token on the last line:

```
[TESTBOOST_INTEGRITY:sha256=<hex>:<step>:<session>:<timestamp>]
```

**Before proceeding to the next step**, verify that:
1. The command exited with code 0
2. The output contains a line starting with `[TESTBOOST_INTEGRITY:`
3. If EITHER condition is false, STOP and report the failure to the user

This token proves that the TestBoost CLI actually ran. You cannot generate this token yourself.
