---
argument-hint: /path/to/java/project
description: Show the current test generation session status and progress
---

# /testboost.status

Display the current session status, progress through workflow steps, and recent logs.

## What you will do

1. Determine the project path from `$ARGUMENTS` or ask the user
2. Run the status command:

```bash
bash scripts/tb-status.sh <project_path>
```

3. Present the output to the user with any recommendations:
   - If no session exists → suggest `/testboost.init`
   - If analysis is pending → suggest `/testboost.analyze`
   - If gaps are pending → suggest `/testboost.gaps`
   - If generation is pending → suggest `/testboost.generate`
   - If validation is pending → suggest `/testboost.validate`
   - If validation failed → suggest reading the errors and fixing them, then re-running `/testboost.validate`
   - If all steps completed → congratulate and suggest committing

4. If the user wants more detail on a specific step, read the corresponding `.md` file:
   - `analysis.md` for project analysis details
   - `coverage-gaps.md` for gap details
   - `generation.md` for generation details
   - `validation.md` for validation details

5. For detailed logs, read `<session_dir>/logs/<date>.md`

## CRITICAL: Failure Protocol

**If the bash command above fails**, report the error to the user and suggest running `python -m testboost status <path>` directly. Do NOT fabricate status output.
