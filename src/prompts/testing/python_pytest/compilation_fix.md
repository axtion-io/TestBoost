You are an expert Python test engineer. Fix the syntax and import errors in the following pytest test file.

## Error Output:
```
{{compile_errors}}
```

## Current Test Code:
```python
{{test_code}}
```

## Common Python Test Errors and Fixes

### SyntaxError
- Missing colon after `def`, `class`, `if`, `for`, `with`
- Incorrect indentation (mix of tabs and spaces)
- Unclosed parentheses, brackets, or quotes
- Invalid f-string syntax

**Fix**: Carefully check indentation (use 4 spaces consistently) and ensure all blocks end with `:`.

### ImportError / ModuleNotFoundError
- Importing a module that does not exist or has a wrong path
- Wrong import path for the module under test

**Fix**: Check the actual module path in the project. Use the format `from src.package.module import ClassName`.

### Wrong mock path
- Patching `requests.get` instead of `mymodule.requests.get`
- Patching the wrong import site

**Fix**: Always patch where the name is *used*, not where it is *defined*.
```python
# WRONG: patches the library directly
@patch("requests.get")
# RIGHT: patches the import in the module under test
@patch("mymodule.requests.get")
```

### NameError: fixture not defined
- Using a pytest fixture without declaring it as a parameter
- Missing `@pytest.fixture` decorator

**Fix**: Declare fixtures as function parameters or add `@pytest.fixture` decorator.

### AttributeError on mock
- Calling `.return_value` on a non-Mock object
- Missing `spec=` argument causes wrong attribute access

**Fix**: Ensure the patched object is the right type and that `return_value` is set correctly.

### IndentationError
- Test function body not indented
- Class body or fixture not indented

**Fix**: Each function body must be indented exactly one level (4 spaces) relative to the `def` line.

## Anti-Patterns to Remove

```python
# WRONG: JUnit-style assertions
self.assertEqual(result, expected)
self.assertTrue(condition)

# RIGHT: pytest style
assert result == expected
assert condition
```

```python
# WRONG: unittest.TestCase base class (unnecessary with pytest)
class TestMyClass(unittest.TestCase):

# RIGHT: plain class or no class
class TestMyClass:
```

```python
# WRONG: placeholder code
def test_something():
    pass  # TODO: implement

# RIGHT: remove or implement the test
```

## Instructions:
1. Analyze each error message and locate the exact line causing it
2. Fix all errors listed — do not introduce new ones
3. Preserve all test logic that was working correctly
4. Return ONLY the fixed Python test file — no explanation text

## Output Format:
```python
# fixed test code here
```
