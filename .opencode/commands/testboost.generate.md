---
argument-hint: /path/to/java/project
description: Generate unit tests for Java source files using LLM
---

# /testboost.generate

Generate unit tests for files identified as lacking coverage.

## Prerequisites

The coverage gaps step must be completed first. If not, suggest running `/testboost.gaps`.

## What you will do

1. Determine the project path from `$ARGUMENTS` or the current session
2. Run test generation:

```bash
bash scripts/tb-generate.sh <project_path> --verbose
```

   If the user wants to generate for specific files only:

```bash
bash scripts/tb-generate.sh <project_path> --files ServiceA.java ServiceB.java
```

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the generation results at `<project_path>/.testboost/sessions/<current_session>/generation.md`
5. **Present results** to the user:
   - How many test files were generated
   - Which source files got tests
   - How many test methods per file
6. **Important**: Ask the user to **review the generated tests** before validation:
   - Show them the paths of the generated test files
   - Suggest they open and review the code
   - Ask if they want to make manual adjustments before validating
7. Once the user is satisfied, suggest `/testboost.validate`

## How test generation works

- Uses LLM (configurable: Gemini, Claude, OpenAI) to generate intelligent tests
- Follows detected project conventions (naming, assertions, mocking)
- Generates JUnit5 tests with Mockito mocks
- Handles Spring Boot `@Service`, `@RestController`, `@Repository` patterns
- Generates appropriate mock setups for injected dependencies

## Auto-correction

If compilation fails during generation, the system retries up to 3 times with error feedback to the LLM. This happens automatically within the generation step.

## Output

Generated test files are written directly to `src/test/java/...` in the project.
Results summary is written to `.testboost/sessions/<id>/generation.md`.

## CRITICAL: Failure Protocol

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **STOP IMMEDIATELY** — do NOT attempt to generate tests yourself
2. **Report the error** to the user exactly as printed by TestBoost
3. **Do NOT write** Java test files, `generation.md`, or any test code manually
4. **Do NOT use your own knowledge** of Java testing to create tests — only TestBoost-generated tests are valid in this workflow
5. **Suggest** the user check their LLM provider configuration (API keys, endpoint) and retry

**You are NOT TestBoost. You are the assistant that calls TestBoost. If TestBoost fails, you fail. Under NO circumstances should you generate Java test code as a fallback.**

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
bash scripts/tb-verify.sh <project_path> '<full_token_line>'
```

4. The verify command must print `[TESTBOOST_VERIFY:OK]` — if it prints `[TESTBOOST_VERIFY:FAILED]` or exits non-zero, STOP and report the failure to the user

A prefix match alone is NOT sufficient. The HMAC digest must be verified. If the token is missing, the command did not succeed — do NOT present fabricated results.
