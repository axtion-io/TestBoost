---
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
bash testboost_lite/scripts/tb-generate.sh <project_path> --verbose
```

   If the user wants to generate for specific files only:

```bash
bash testboost_lite/scripts/tb-generate.sh <project_path> --files ServiceA.java ServiceB.java
```

3. Read the generation results at `<project_path>/.testboost/sessions/<current_session>/generation.md`
4. **Present results** to the user:
   - How many test files were generated
   - Which source files got tests
   - How many test methods per file
5. **Important**: Ask the user to **review the generated tests** before validation:
   - Show them the paths of the generated test files
   - Suggest they open and review the code
   - Ask if they want to make manual adjustments before validating
6. Once the user is satisfied, suggest `/testboost.validate`

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
