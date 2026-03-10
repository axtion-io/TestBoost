---
argument-hint: /path/to/java/project
description: Initialize TestBoost Lite for a Java project and create a test generation session
---

# /testboost.init

Initialize a test generation session for a Java project.

## What you will do

1. Ask the user for the **path to their Java project** if not provided as argument: `$ARGUMENTS`
2. Run the initialization script:

```bash
bash testboost_lite/scripts/tb-init.sh <project_path>
```

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the generated `<project_path>/.testboost/sessions/<session_id>/spec.md` file
5. Present the session information to the user
6. Ask the user if they want to **proceed with analysis** (suggest running `/testboost.analyze`)

## Important notes

- The project must contain a `pom.xml` (Maven) or `build.gradle` (Gradle) file
- This creates a `.testboost/` directory in the target project
- Each session is numbered (001, 002, ...) and stored under `.testboost/sessions/`
- The session tracks progress through: analysis → coverage-gaps → generation → validation

## CRITICAL: Failure Protocol

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **STOP IMMEDIATELY** — do NOT attempt to initialize the session yourself
2. **Report the error** to the user exactly as printed by TestBoost
3. **Do NOT create** `.testboost/` directories, `spec.md` files, or any session artifacts manually
4. **Suggest** the user check their TestBoost installation and run `python -m testboost_lite init <path>` directly

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
