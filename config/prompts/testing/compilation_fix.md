Fix the compilation errors in this Java test class. Return ONLY the corrected Java code, no explanation.

## Compilation Errors:
```
{{compile_errors}}
```

## Current Test Code:
```java
{{test_code}}
```

Rules:
- Fix ONLY the compilation errors listed above
- Do not add or remove test methods
- Keep all test logic intact
- For void methods use doNothing().when(mock).method() not when(mock.method()).thenReturn(null)
- For private field access via reflection, always call field.setAccessible(true) first and declare throws Exception
- Use any(ExactClass.class) for mock matchers matching the exact parameter type
- Return the complete corrected Java class starting with `package`
