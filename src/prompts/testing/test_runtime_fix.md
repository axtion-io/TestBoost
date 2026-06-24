Fix the failing test(s) in this Java test class using the runtime error output below. Return ONLY the corrected Java code, no explanation.

## Test Run Output (failures / stack traces):
```
{{test_errors}}
```

## Current Test Code:
```java
{{test_code}}
```

Rules:
- Fix ONLY the failing test behaviour (mock setup, expected values, test data, assertion matchers).
- Do NOT modify the production code or the class under test; you only see the test.
- Keep passing tests intact. Do not delete a test unless the only correct fix is removal.
- Adjust mocks, argument matchers, and expected values so the test matches the real code under test.
- For `NullPointerException`: check mock stubs (missing `when(...).thenReturn(...)`) and object initialization order.
- For `IllegalArgumentException` / `IllegalStateException` raised during the test body: the setup is likely violating a real constraint — adjust inputs rather than catching the exception.
- For `AssertionError`: reconsider the expected value based on the code under test. Do NOT replace `assertEquals` with `assertNotNull` just to force-pass.
- For `UnfinishedStubbingException` / `PotentialStubbingProblem` from Mockito: fix the stub ordering or argument matcher types (`any(ExactClass.class)` with the exact parameter class).
- Return the complete corrected Java class starting with `package`.
