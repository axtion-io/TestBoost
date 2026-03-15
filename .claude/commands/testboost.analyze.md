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

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the generated analysis file at `<project_path>/.testboost/sessions/<current_session>/analysis.md`
5. **Summarize the key findings** to the user:
   - Project type and frameworks detected
   - Number of source classes and existing tests
   - Number of testable source files identified
   - Test conventions detected (naming, assertions, mocking)
6. Ask if they want to **identify coverage gaps** next (suggest `/testboost.gaps`)

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

## CRITICAL: Failure Protocol

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **STOP IMMEDIATELY** — do NOT attempt to analyze the project yourself
2. **Report the error** to the user exactly as printed by TestBoost
3. **Do NOT create** `analysis.md` or write any analysis results manually
4. **Do NOT read source files** and fabricate an analysis — only TestBoost's analysis is valid
5. **Suggest** the user check the error and retry

**You are NOT TestBoost. You are the assistant that calls TestBoost. If TestBoost fails, you fail.**

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

A prefix match alone is NOT sufficient. The HMAC digest must be verified.
