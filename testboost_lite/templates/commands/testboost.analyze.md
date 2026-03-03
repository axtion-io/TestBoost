---
description: Analyze a Java project's structure, frameworks, and test conventions
---

# /testboost.analyze

Analyze the Java project to understand its structure, frameworks, and existing test patterns.

## What you will do

1. Determine the project path. If `$ARGUMENTS` is provided, use it. Otherwise, check the current session by running:

```bash
bash testboost_lite/scripts/tb-status.sh <project_path>
```

2. Run the analysis:

```bash
bash testboost_lite/scripts/tb-analyze.sh <project_path> --verbose
```

3. Read the generated analysis file at `<project_path>/.testboost/sessions/<current_session>/analysis.md`
4. **Summarize the key findings** to the user:
   - Project type and frameworks detected
   - Number of source classes and existing tests
   - Number of testable source files identified
   - Test conventions detected (naming, assertions, mocking)
5. Ask if they want to **identify coverage gaps** next (suggest `/testboost.gaps`)

## What this does under the hood

- Parses `pom.xml` or `build.gradle` for dependencies and Java version
- Scans source directories for Java classes and their packages
- Detects frameworks (Spring Boot, JPA, Quarkus, etc.)
- Detects test frameworks (JUnit5, Mockito, AssertJ, etc.)
- Analyzes existing test conventions (naming patterns, assertion styles, mock patterns)
- Identifies testable source files (filters out DTOs, configs, exceptions)

## Output

Results are written to `.testboost/sessions/<id>/analysis.md` with:
- Human-readable summary
- Raw JSON data block for downstream steps
