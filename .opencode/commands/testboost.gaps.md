---
description: Identify test coverage gaps in the Java project
argument-hint: /path/to/java/project
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

3. Read the coverage gaps file at `<project_path>/.testboost/sessions/<current_session>/coverage-gaps.md`
4. **Present the gaps** to the user:
   - Show the coverage percentage
   - List the files that need tests, with priority (high for services/controllers)
   - List files that already have tests
5. **Ask the user which files to generate tests for**:
   - All gaps? (default)
   - A specific subset? (let them pick from the list)
   - Only high priority files?
6. Suggest running `/testboost.generate` next

## How gaps are identified

- Compares testable source files (from analysis) against existing `*Test.java` / `*Tests.java` files
- A source file like `UserService.java` is "covered" if `UserServiceTest.java` exists
- Priority is assigned based on class type (services and controllers are high priority)

## Output

Results are written to `.testboost/sessions/<id>/coverage-gaps.md` with a prioritized table.
