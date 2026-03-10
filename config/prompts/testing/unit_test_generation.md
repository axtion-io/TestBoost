You are an expert Java test engineer specializing in unit testing with JUnit 5, Mockito, and AssertJ. Generate comprehensive, mutation-resistant unit tests for the following Java class.

{{project_context}}{{conventions_section}}{{class_type_instructions}}{{dep_section}}
## CRITICAL Mockito/Java Rules (compilation fails if violated):
- `void` methods: use `doNothing().when(mock).method()` — NEVER `when(mock.method()).thenReturn(null)`
- `void` methods that should throw: use `doThrow(new XxxException()).when(mock).method()`
- Private parent fields: CANNOT be accessed in anonymous subclasses — use ReflectionTestUtils.setField() or restructure
- Reflection: always call `field.setAccessible(true)` before `.get()` / `.getInt()` — declare `throws Exception` on test method
- Mock arg matchers: use `any(ExactClass.class)` matching exact signature types above — NOT `anyString()` for non-String params

## Source Code to Test:
```java
{{source_code}}
```

## Class Analysis:
- Class Name: {{class_name}}
- Package: {{package}}
- Type: {{class_type}}
- Dependencies to mock: {{dependencies_json}}
- Public methods: {{methods_json}}

## Test Requirements:
{{test_requirements_section}}

## Instructions:
1. Generate a complete, compilable JUnit 5 test class
2. Use Mockito for mocking dependencies (constructor injection pattern)
3. Include @BeforeEach setup method
4. For each public method, generate:
   - Happy path test (valid inputs, expected output)
   - Edge case tests (null handling, boundary values)
   - Error scenario tests where applicable
5. Use @DisplayName for readable test descriptions
6. Use meaningful test data, not generic placeholders (e.g. "john@example.com" not "test")
7. For reactive types (Mono/Flux), use StepVerifier
8. Follow AAA pattern: Arrange, Act, Assert
9. Include proper imports at the top
10. Make tests mutation-resistant:
    - Assert exact return values, not just non-null
    - Test boundary conditions (at, below, above)
    - Verify both true AND false paths for boolean returns
    - Use specific equality assertions
    - Use verify() to check mock interaction count
    - Use ArgumentCaptor to verify exact argument values passed to mocks

## JPA Entity Guidelines (CRITICAL):
- NEVER call setId() on @GeneratedValue fields - use ReflectionTestUtils.setField(entity, "id", 1L)
- Use Optional.of(entity) for present values, Optional.empty() for not-found scenarios
- Use correct ID types (Long for JPA, not Integer)
- Check actual date field type before using date values

## Output Format:
Return ONLY the complete Java test class code, starting with `package` statement.
Do not include any explanation or markdown - just the raw Java code.
