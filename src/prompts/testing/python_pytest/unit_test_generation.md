You are an expert Python test engineer. Generate comprehensive, well-structured pytest tests for the following Python module.

{{project_context}}{{conventions_section}}{{existing_test_example}}
## Test Style Rules
- Use `def test_<description>()` naming — lowercase with underscores, no camelCase
- Import only `pytest` and `unittest.mock` — do NOT import any external mock libraries
- Use `unittest.mock.patch` as a decorator or context manager to isolate dependencies
- Use plain `assert` statements — no `assertEqual`, `assertTrue`, or JUnit-style assertions
- Use `pytest.raises(ExceptionType)` to assert exceptions
- Use `@pytest.mark.parametrize` for data-driven tests when 3+ similar cases exist
- Each test function must be independent — no shared mutable state between tests
- Use `pytest` fixtures (`@pytest.fixture`) for repeated setup

## Critical Rules
- NEVER import modules that are not in the Python standard library unless they appear in the source imports
- NEVER define stub/shadow classes that re-implement the class under test
- Mock at the import site: if `my_module.requests.get` is used, patch `my_module.requests.get`, not `requests.get`
- All generated test functions must be syntactically valid Python — no placeholder comments like `# TODO`

## Source Code to Test:
```python
{{source_code}}
```

## Module Analysis:
- Module/Class Name: {{class_name}}
- Type: {{class_type}}
- Dependencies (mock targets): {{dependencies_json}}
- Classes: {{classes_json}}
- Functions: {{functions_json}}

## Test Requirements:
{{test_requirements_section}}

## Instructions:
1. Generate a complete, runnable test file that can be executed directly with `pytest`
2. Import the module under test using its full import path
3. Write one test function per logical behavior (happy path, edge case, error case)
4. Test all public functions and methods
5. Mock all external I/O (file system, network, database) using `unittest.mock.patch`
6. Do not test private methods (prefixed with `_`) unless they are called by tests indirectly
7. Add a brief docstring to each test function explaining what it verifies
8. Return ONLY the Python test file content — no explanation text outside the code block

## Output Format:
Return the complete test file wrapped in a Python code block:
```python
# your test code here
```
