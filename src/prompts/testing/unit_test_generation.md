You are an expert Java test engineer. Generate comprehensive, mutation-resistant unit tests for the following Java class.

{{project_context}}{{framework_instructions}}{{conventions_section}}{{class_type_instructions}}{{dep_section}}{{inheritance_context}}{{existing_test_example}}
## CRITICAL: No Placeholder Classes
- NEVER define fake, stub, or shadow classes/interfaces that duplicate real project classes
- NEVER create inner classes that shadow or re-implement the class under test or its dependencies
- All imports MUST reference real project classes or standard test libraries
- If a dependency cannot be imported, mock it using the mocking library or skip that test

{{reflection_section}}## Source Code to Test:
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
1. Generate a complete, compilable test class using the framework specified above
2. Mock dependencies using the approach specified above
3. Add a setup method (with the framework's annotation) only when several tests share fixtures
4. For each public method, generate:
   - Happy path test (valid inputs, expected output)
   - Edge case tests (null handling, boundary values)
   - Error scenario tests where applicable
5. Use meaningful test data, not generic placeholders (e.g. "john@example.com" not "test")
6. Follow AAA pattern: Arrange, Act, Assert
7. Include proper imports at the top
8. Make tests mutation-resistant:
    - Assert exact return values, not just non-null
    - Test boundary conditions (at, below, above)
    - Verify both true AND false paths for boolean returns
    - Use specific equality assertions
{{specific_rules}}
## Output Format:
Return ONLY the complete Java test class code, starting with `package` statement.
Do not include any explanation or markdown - just the raw Java code.
