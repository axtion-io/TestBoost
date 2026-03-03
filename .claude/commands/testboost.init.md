---
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

3. Read the generated `<project_path>/.testboost/sessions/<session_id>/spec.md` file
4. Present the session information to the user
5. Ask the user if they want to **proceed with analysis** (suggest running `/testboost.analyze`)

## Important notes

- The project must contain a `pom.xml` (Maven) or `build.gradle` (Gradle) file
- This creates a `.testboost/` directory in the target project
- Each session is numbered (001, 002, ...) and stored under `.testboost/sessions/`
- The session tracks progress through: analysis → coverage-gaps → generation → validation
