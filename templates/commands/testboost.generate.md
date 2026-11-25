---
description: Generate unit tests (agent mode by default, or TestBoost's own LLM)
---

# /testboost.generate

Generate unit tests for files identified as lacking coverage.

## Prerequisites

The coverage gaps step must be completed first. If not, suggest running `/testboost.gaps`.

## Choose the mode

- **Agent mode (default)**: you, the assistant, write the tests from the prompts TestBoost prepares.
  No LLM API key is needed and TestBoost never calls an LLM. Use it unless the user asks otherwise.
- **LLM mode**: TestBoost calls its own LLM (requires an API key in TestBoost's `.env`). Use it only
  when the user explicitly asks for it, then follow "LLM mode" below.

## Agent mode (default)

1. Determine the project path from `$ARGUMENTS` or the current session
2. Prepare the prompts (optionally `--files ServiceA.java ServiceB.java`):

```bash
bash scripts/tb-context.sh <project_path>
```

3. For **each row** of the printed table: read the brief and the class under test, then write the
   **complete** test file at the exact "Test to write" path. Follow the brief (test stack actually
   available, project conventions, exact dependency signatures, uncovered lines) and think about edge
   cases yourself. Write only at those paths: no other file, no
   production code change.
4. Register and compile your tests:

```bash
bash scripts/tb-generate.sh <project_path> --agent
```

5. If it reports **missing** tests or **compilation errors**, fix exactly those files and re-run step 4,
   until it exits 0. Then **VERIFY the output** (see "Integrity Verification" below).
6. Present the generated files and suggest the user reviews them, then `/testboost.validate`.

## LLM mode (only when the user asks for it)

1. Run test generation:

```bash
bash scripts/tb-generate.sh <project_path> --verbose
```

   For specific files only: `bash scripts/tb-generate.sh <project_path> --files ServiceA.java ServiceB.java`

2. **VERIFY the output** — see the "Integrity Verification" section below
3. Read the generation results at `<project_path>/.testboost/sessions/<current_session>/generation.md`
4. **Present results** to the user (files generated, test methods per file) and ask them to **review
   the generated tests** before suggesting `/testboost.validate`

## How test generation works

- Agent mode: the prompts carry the class, its dependencies' exact signatures, the project's test
  examples and conventions; you write the tests, TestBoost compiles and registers them
- LLM mode: TestBoost's own LLM (configurable: Gemini, Claude, OpenAI) generates the tests
- Follows detected project conventions (naming, assertions, mocking)
- Generates JUnit5 tests with Mockito mocks
- Handles Spring Boot `@Service`, `@RestController`, `@Repository` patterns
- Generates appropriate mock setups for injected dependencies

## Auto-correction (LLM mode)

If compilation fails during generation, the errors are fed back to the LLM. The budget is `max_correction_retries` compile checks (default 3, i.e. up to 2 LLM fixes) from `.testboost/config.yaml`. Once the test compiles, it is run once (`mvn test -Dtest=<Class>`) and runtime failures get one LLM fix (`--no-runtime-fix` to skip). This happens automatically within the generation step.

## Output

Generated test files are written directly to `src/test/java/...` in the project.
Results summary is written to `.testboost/sessions/<id>/generation.md`.

## CRITICAL: Failure Protocol

**If a TestBoost command exits with a non-zero code or prints `[TESTBOOST_FAILED`:**

1. **Agent mode, `generate --agent` reporting missing tests or compilation errors**: this is the normal
   loop — write or fix exactly the listed test files and re-run it.
2. **Any other failure** (missing session, `context` failure, LLM mode failure): STOP, report the error
   exactly as printed by TestBoost, and do not work around it.
3. **Never** write `generation.md` or any `.testboost/` file by hand, never write tests outside the paths
   given by `context`, and never present results that a successful, verified TestBoost command did not
   produce. In LLM mode, do not write test code yourself as a fallback.

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
