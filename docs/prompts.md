# LLM Prompts

TestBoost uses LLM prompts at two stages: **test generation** and **compilation error fixing**. All prompts are stored as markdown files in `config/prompts/` and can be edited without restarting anything.

## Template System

Prompt files use `{{placeholder}}` syntax. The double braces are intentional — single `{` would conflict with Java code blocks in the template, and `$variable` would conflict with Spring EL expressions. Rendering is done by `src/lib/prompt_utils.py` which also caches template reads so disk I/O only happens once per session.

## Active Prompt Files

```
config/prompts/
+-- testing/
|   +-- unit_test_generation.md      # Main test generation prompt
|   +-- unit_test_strategy.md        # Unit test strategy (agent system prompt)
|   +-- compilation_fix.md           # Fix compilation errors in generated tests
|   +-- test_review.md               # Post-generation quality review pass
|   +-- mutation_killer.md           # LLM-powered killer tests for surviving mutants
|   +-- edge_case_analysis.md        # Pre-generation edge case scenario analysis
+-- maven/
|   +-- compilation_errors_format.md # Format Maven errors for LLM consumption
|   +-- system_agent.md              # Maven maintenance agent system prompt
```

## Unit Test Generation

**File:** `config/prompts/testing/unit_test_generation.md`

Used by `generate_adaptive_tests()` in `generate_unit.py`. This is the main prompt the LLM receives when generating tests for a source file.

### Template Variables

| Placeholder | Description |
|-------------|-------------|
| `{{project_context}}` | Java version, Spring Boot version, key dependencies from `pom.xml` |
| `{{conventions_section}}` | Detected test conventions (naming, assertion style, Mockito usage) |
| `{{class_type_instructions}}` | Controller / service / repository-specific test patterns |
| `{{dep_section}}` | Public method signatures of dependency classes |
| `{{source_code}}` | Full source code of the class to test |
| `{{class_name}}` | Simple class name |
| `{{package}}` | Java package |
| `{{class_type}}` | controller, service, repository, utility, model |
| `{{dependencies_json}}` | JSON list of constructor-injected dependencies |
| `{{methods_json}}` | JSON list of public methods with return types |
| `{{test_requirements_section}}` | Specific test requirements, or default coverage instruction |

### What the prompt enforces

- JUnit 5 + Mockito + AssertJ
- Mutation-resistant tests: exact return values, boundary conditions, both boolean paths, `verify()` call counts, `ArgumentCaptor` for mock arguments
- CRITICAL Mockito rules: `doNothing()` for `void` methods, `ReflectionTestUtils` for private fields
- JPA entity rules: never `setId()` on `@GeneratedValue` fields, correct ID types (`Long` vs `Integer`)
- Class-type-specific patterns injected as `{{class_type_instructions}}`:
  - **controller**: `@WebMvcTest`, `MockMvc`, `@MockBean`
  - **service**: `@ExtendWith(MockitoExtension.class)`, `@Mock`, `@InjectMocks`
  - **repository**: `@DataJpaTest`, `TestEntityManager`

## Compilation Fix

**File:** `config/prompts/testing/compilation_fix.md`

Used by `fix_compilation_errors()` when `mvn test-compile` fails on a generated test file. The LLM receives the test code and the error messages, and must return only corrected Java code.

| Placeholder | Description |
|-------------|-------------|
| `{{compile_errors}}` | Maven compilation errors for the failing test file |
| `{{test_code}}` | Current (broken) test file content |

## Maven Error Formatting

**File:** `config/prompts/maven/compilation_errors_format.md`

Used by `MavenErrorParser.format_for_llm()` to produce a structured error report. This is what the LLM CLI sees when the `validate` step fails.

| Placeholder | Description |
|-------------|-------------|
| `{{total_errors}}` | Total number of compilation errors |
| `{{error_details}}` | Per-file, per-error markdown blocks with type, message, and fix suggestion |

## Test Review (Post-Generation Quality Pass)

**File:** `config/prompts/testing/test_review.md`

Used by `_review_generated_tests()` in `generate_unit.py`. Runs automatically after test generation to fix weak assertions, missing mock verifications, and anti-patterns.

| Placeholder | Description |
|-------------|-------------|
| `{{test_code}}` | The generated test class to review |
| `{{source_code}}` | Source code of the class under test |

### What the prompt fixes

- Weak assertions (`isNotNull` → exact value checks)
- Missing `verify()` calls for important side-effects
- `Thread.sleep()` → `Awaitility`
- `try/catch` swallowing → `assertThatThrownBy()`
- Missing tests for untested public methods
- Missing boundary value tests for numeric comparisons

## Mutation Killer (LLM-Powered)

**File:** `config/prompts/testing/mutation_killer.md`

Used by `_generate_killer_tests_llm()` in `killer_tests.py`. Replaces the static template-based killer test generation with LLM-powered tests that use real parameter values computed from the source code.

| Placeholder | Description |
|-------------|-------------|
| `{{surviving_mutants}}` | JSON array of surviving mutants from PIT analysis |
| `{{source_code}}` | Full source code of the class with surviving mutants |
| `{{class_name}}` | Simple class name |
| `{{package}}` | Java package |

## Edge Case Analysis (Pre-Generation)

**File:** `config/prompts/testing/edge_case_analysis.md`

Used by `analyze_edge_cases()` in `generate_unit.py`. Returns a JSON array of edge case scenarios (null inputs, boundaries, empty collections, exception paths) that can be fed into `test_requirements` for targeted generation.

| Placeholder | Description |
|-------------|-------------|
| `{{source_code}}` | Full source code of the class to analyze |
| `{{class_name}}` | Simple class name |
| `{{class_type}}` | controller, service, repository, utility, model |

## How Conventions Flow into Prompts

During the `analyze` step, TestBoost detects your project's existing test conventions:

```
analyze --> conventions JSON --> generate --> {{conventions_section}} in prompt
```

The detected naming pattern, assertion style, Mockito usage, and Spring MockBean usage are injected as the `{{conventions_section}}` placeholder. This means the LLM generates tests that match your existing test style.

## Customizing

Edit any file in `config/prompts/` to adjust behavior. Changes take effect on the next `generate` run — no restart needed. The `{{placeholder}}` values are injected at runtime by `src/lib/prompt_utils.render_template()`.
