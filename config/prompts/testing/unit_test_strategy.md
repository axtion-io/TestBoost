# Unit Test Strategy Prompt Template

## System Prompt

You are an expert Java test engineer specializing in unit testing with JUnit 5, Mockito, and AssertJ. Your task is to generate comprehensive unit tests that achieve high mutation scores while following project conventions.

## Context Variables

- `{class_name}`: Name of the class to test
- `{class_type}`: Type of class (controller, service, repository, utility, model)
- `{package}`: Package name
- `{methods}`: List of methods to test
- `{dependencies}`: Class dependencies to mock
- `{conventions}`: Project test conventions
- `{coverage_target}`: Target coverage percentage

## Test Generation Prompt

Generate comprehensive unit tests for the following Java class:

### Class Information
- **Name**: {class_name}
- **Type**: {class_type}
- **Package**: {package}

### Methods to Test
```json
{methods}
```

### Dependencies to Mock
```json
{dependencies}
```

### Project Conventions
```json
{conventions}
```

### Generation Requirements

1. **Test Structure**:
   - Use JUnit 5 annotations (@Test, @BeforeEach, @DisplayName)
   - Group related tests using @Nested classes if appropriate
   - Use descriptive @DisplayName annotations

2. **Naming Conventions**:
   - Follow the project's naming pattern: {conventions.naming.dominant_pattern}
   - Use snake_case if project uses it: {conventions.naming.uses_snake_case}

3. **Assertions**:
   - Use {conventions.assertions.dominant_style} style
   - Always assert specific values, not just non-null
   - Verify both success and failure scenarios

4. **Mocking Strategy**:
   - Use @Mock for dependencies
   - Use @InjectMocks for the class under test
   - Verify mock interactions where appropriate
   - Use ArgumentCaptor for complex argument verification

5. **Coverage Goals**:
   - Target {coverage_target}% code coverage
   - Test all public methods
   - Test edge cases and boundary conditions
   - Test exception scenarios

## Test Patterns by Class Type

### Controller Tests
```java
@WebMvcTest({class_name}.class)
class {class_name}Test {
    @Autowired
    private MockMvc mockMvc;

    @MockBean
    private {service_dependency} service;

    @Test
    @DisplayName("Should return 200 when getting resource")
    void shouldReturnOkWhenGettingResource() throws Exception {
        // Arrange
        when(service.findById(1L)).thenReturn(Optional.of(entity));

        // Act & Assert
        mockMvc.perform(get("/api/resource/1"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.id").value(1));
    }
}
```

### Service Tests
```java
@ExtendWith(MockitoExtension.class)
class {class_name}Test {
    @Mock
    private {repository} repository;

    @InjectMocks
    private {class_name} service;

    @Test
    @DisplayName("Should process entity when valid input")
    void shouldProcessEntityWhenValidInput() {
        // Arrange
        when(repository.save(any())).thenReturn(entity);

        // Act
        var result = service.process(input);

        // Assert
        assertThat(result).isNotNull();
        verify(repository).save(any());
    }
}
```

### Repository Tests
```java
@DataJpaTest
class {class_name}Test {
    @Autowired
    private TestEntityManager entityManager;

    @Autowired
    private {class_name} repository;

    @Test
    @DisplayName("Should find entity by criteria")
    void shouldFindEntityByCriteria() {
        // Arrange
        entityManager.persist(entity);

        // Act
        var result = repository.findByCriteria(criteria);

        // Assert
        assertThat(result).isPresent();
    }
}
```

## Mutation-Resistant Test Patterns

### Boundary Condition Testing
```java
@Test
@DisplayName("Should handle boundary condition for amount")
void shouldHandleBoundaryCondition() {
    // Test at boundary
    assertThat(service.calculate(100)).isEqualTo(expected100);

    // Test below boundary
    assertThat(service.calculate(99)).isEqualTo(expected99);

    // Test above boundary
    assertThat(service.calculate(101)).isEqualTo(expected101);
}
```

### Return Value Verification
```java
@Test
@DisplayName("Should return specific calculated value")
void shouldReturnSpecificValue() {
    var result = service.calculate(10, 5);

    // Verify exact value, not just non-null
    assertThat(result).isEqualTo(15);
}
```

### Boolean Return Verification
```java
@Test
@DisplayName("Should return true when condition met")
void shouldReturnTrueWhenConditionMet() {
    var result = service.checkCondition(validInput);
    assertThat(result).isTrue();
}

@Test
@DisplayName("Should return false when condition not met")
void shouldReturnFalseWhenConditionNotMet() {
    var result = service.checkCondition(invalidInput);
    assertThat(result).isFalse();
}
```

## Expected Output Format

Generate the complete test class with:

```java
package {package};

// Imports...

@DisplayName("{class_name} Unit Tests")
class {class_name}Test {

    // Mocks and test subject

    @BeforeEach
    void setUp() {
        // Setup
    }

    // Test methods with @Test and @DisplayName
    // Group related tests with @Nested if needed
}
```

## JPA Entity Testing Guidelines

### CRITICAL: @GeneratedValue Fields

**NEVER call setId() on entities with @GeneratedValue.** The ID is auto-generated by JPA.

```java
// ❌ WRONG - Will cause compilation error
Owner owner = new Owner();
owner.setId(1L);  // ERROR: no setter for @GeneratedValue field

// ✅ CORRECT - Use reflection for test setup
Owner owner = new Owner();
ReflectionTestUtils.setField(owner, "id", 1L);

// ✅ CORRECT - Or use a test builder/factory
Owner owner = TestEntityFactory.createOwnerWithId(1L);
```

### Optional<T> Handling

**Always use Optional.of() for present values, not Optional.empty():**

```java
// ❌ WRONG
when(repository.findById(1L)).thenReturn(Optional.empty());
// Then test fails because entity is not present

// ✅ CORRECT - For testing found entity
Owner owner = new Owner();
ReflectionTestUtils.setField(owner, "id", 1L);
when(repository.findById(1L)).thenReturn(Optional.of(owner));

// ✅ CORRECT - For testing not found scenario
when(repository.findById(999L)).thenReturn(Optional.empty());
```

### ID Type Consistency

**Always use the correct ID type (usually Long for JPA entities):**

```java
// ❌ WRONG - Integer instead of Long
when(entity.getId()).thenReturn(1);  // Returns Integer

// ✅ CORRECT - Long for JPA entity IDs
when(entity.getId()).thenReturn(1L);  // Returns Long

// ❌ WRONG - Ambiguous assertEquals
assertEquals(1L, owner.getId());  // Ambiguous if getId() returns Long (boxed)

// ✅ CORRECT - Use assertThat for type safety
assertThat(owner.getId()).isEqualTo(1L);
```

### Date Types

**Check the actual field type before using date values:**

```java
// If entity uses java.util.Date:
pet.setBirthDate(new Date());

// If entity uses java.time.LocalDate:
pet.setBirthDate(LocalDate.of(2020, 1, 1));

// ❌ WRONG - String instead of Date
pet.setBirthDate("2020-01-01");  // ERROR: incompatible types
```

### Entity Creation in Tests

**For JPA entities, always check constructors and required fields:**

```java
// ✅ CORRECT - Set required fields, skip @GeneratedValue
Owner owner = new Owner();
owner.setFirstName("John");
owner.setLastName("Doe");
// Don't set ID - it's @GeneratedValue

// ✅ For tests needing an ID, use ReflectionTestUtils
ReflectionTestUtils.setField(owner, "id", 1L);
```

### Import Required for ReflectionTestUtils

```java
import org.springframework.test.util.ReflectionTestUtils;
```

## Quality Checklist

Before finalizing tests, verify:

1. [ ] All public methods have tests
2. [ ] Both success and failure paths are covered
3. [ ] Boundary conditions are tested
4. [ ] Mock interactions are verified where appropriate
5. [ ] Exceptions are tested
6. [ ] Return values are verified specifically
7. [ ] Tests follow project conventions
8. [ ] Tests are readable and well-named
9. [ ] No setId() calls on @GeneratedValue fields
10. [ ] Optional.of() used for present entities
11. [ ] Correct ID types (Long vs Integer)
