# LLM Prompts

TestBoost uses LLM prompts at two key stages: **project analysis** and **test generation**. The prompts are stored as markdown files in `config/prompts/` and can be customized.

## Prompt Files

```
config/prompts/
+-- common/
|   +-- java_expert.md          # Java expertise context
+-- testing/
|   +-- unit_test_strategy.md   # Unit test generation guidelines
|   +-- integration_strategy.md # Integration test strategy
|   +-- snapshot_strategy.md    # Snapshot test strategy
```

## Java Expert Prompt

**File:** `config/prompts/common/java_expert.md`

This is the base system prompt that establishes the LLM's Java expertise. It covers:

- **Core Java** -- Java 8-21 features (lambdas, streams, records, sealed classes, virtual threads)
- **Testing frameworks** -- JUnit 4/5, TestNG, Mockito, AssertJ, Hamcrest
- **Build tools** -- Maven and Gradle (dependency management, plugins, multi-module)
- **Code quality** -- JaCoCo, PIT mutation testing, SpotBugs, PMD
- **Best practices** -- Arrange-Act-Assert, single responsibility, meaningful names, edge cases

## Unit Test Strategy Prompt

**File:** `config/prompts/testing/unit_test_strategy.md`

This is the main prompt template used during test generation. It includes:

### Context Variables

The following placeholders are filled at runtime from the analysis step:

| Variable | Source | Description |
|----------|--------|-------------|
| `{class_name}` | Source file | Name of the class to test |
| `{class_type}` | Analysis | controller, service, repository, utility, model |
| `{package}` | Source file | Java package name |
| `{methods}` | Source file | List of public methods with signatures |
| `{dependencies}` | Source file | Class dependencies to mock |
| `{conventions}` | Analysis | Detected test conventions (naming, assertions, mocking) |
| `{coverage_target}` | config.yaml | Target coverage percentage |

### Class-Type Patterns

The prompt includes specific test patterns for each class type:

**Controllers** -- Uses `@WebMvcTest`, `MockMvc`, `@MockBean`:
```java
@WebMvcTest(UserController.class)
class UserControllerTest {
    @Autowired private MockMvc mockMvc;
    @MockBean private UserService service;
    // ...
}
```

**Services** -- Uses `@ExtendWith(MockitoExtension.class)`, `@Mock`, `@InjectMocks`:
```java
@ExtendWith(MockitoExtension.class)
class UserServiceTest {
    @Mock private UserRepository repository;
    @InjectMocks private UserService service;
    // ...
}
```

**Repositories** -- Uses `@DataJpaTest`, `TestEntityManager`:
```java
@DataJpaTest
class UserRepositoryTest {
    @Autowired private TestEntityManager entityManager;
    @Autowired private UserRepository repository;
    // ...
}
```

### Mutation-Resistant Patterns

The prompt encourages tests that survive mutation testing:

- **Boundary conditions** -- Test at, below, and above boundaries
- **Exact return values** -- Assert specific values, not just non-null
- **Boolean returns** -- Test both `true` and `false` paths
- **Exception scenarios** -- Verify exception types and messages

### JPA Entity Guidelines

Special rules for testing JPA entities:

- Never call `setId()` on `@GeneratedValue` fields -- use `ReflectionTestUtils`
- Use `Optional.of()` for present entities in mock returns
- Use the correct ID type (`Long`, not `Integer`)
- Check actual date field types before using date values

## Customizing Prompts

You can edit the prompt files in `config/prompts/` to adjust the test generation behavior:

1. **Change test style** -- Modify the test patterns in `unit_test_strategy.md`
2. **Add domain rules** -- Add project-specific instructions to `java_expert.md`
3. **Change framework preferences** -- Update the assertion and mocking examples

Changes take effect on the next `generate` run. No restart needed.

## How Conventions Flow into Prompts

During the `analyze` step, TestBoost detects your project's existing test conventions:

```
analyze --> conventions JSON --> generate --> LLM prompt
```

The detected conventions (naming pattern, assertion style, Mockito usage, Spring MockBean usage) are passed as context variables into the prompt template. This means the LLM generates tests that match your existing test style, not a generic one.
