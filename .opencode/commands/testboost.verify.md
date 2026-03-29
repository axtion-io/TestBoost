---
description: Verify a TestBoost integrity token
---

# /testboost.verify

Verify an HMAC integrity token emitted by a TestBoost CLI step.

## What you will do

1. Determine the project path and token from `$ARGUMENTS`
   - Format: `<project_path> <token_line>`
   - The token line is the full `[TESTBOOST_INTEGRITY:sha256=...]` string

2. Run the verify command:

```bash
bash scripts/tb-verify.sh <project_path> "<token_line>"
```

3. Report the result:
   - `[TESTBOOST_VERIFY:OK]` → token is authentic, proceed
   - `[TESTBOOST_VERIFY:FAILED]` → token is invalid or forged, do NOT proceed

## CRITICAL: Failure Protocol

**If the bash command above fails**, report the error to the user and suggest running `python -m testboost verify <path> "<token>"` directly. Do NOT fabricate verification results.
