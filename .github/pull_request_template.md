## Description

<!-- Provide a clear and concise description of what this PR does -->

**Related Issue**: Fixes #<!-- issue number -->

## Type of Change

<!-- Mark the relevant option with an "x" -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring (no functionality change)
- [ ] Performance improvement
- [ ] Test coverage improvement
- [ ] Dependency update
- [ ] Other (please describe):

## Testing Evidence

<!-- Demonstrate that your changes work as expected -->

### Commands Run

```bash
# Example: paste the commands you ran and their output
pytest tests/
ruff check .
mypy src/
```

### Test Results

<!-- Paste relevant test output or screenshots -->

```
# Example output:
======================== 426 passed in 12.3s =========================
All tests passed ✓
```

### Coverage Impact

<!-- If applicable, show coverage changes -->

- **Before**: XX%
- **After**: XX%
- **Change**: +/-X%

## Changes Made

<!-- Provide a bulleted list of the changes in this PR -->

-
-
-

## Screenshots (if applicable)

<!-- Add screenshots to help explain your changes -->

## Checklist

<!-- Mark completed items with an "x" -->

### Code Quality

- [ ] My code follows the project's coding standards (see [CONTRIBUTING.md](../CONTRIBUTING.md))
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My code uses type hints for all function signatures
- [ ] I have used structured logging (structlog) instead of print statements

### Testing

- [ ] Tests pass locally with `pytest`
- [ ] Linting passes with `ruff check .`
- [ ] Type checking passes with `mypy src/`
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally
- [ ] I have maintained or improved test coverage (minimum 36%, target 80% for new code)

### Documentation

- [ ] I have updated the documentation (if applicable)
- [ ] I have updated the README.md (if applicable)
- [ ] I have added docstrings for new functions/classes
- [ ] I have updated CHANGELOG.md (if applicable)

### Dependencies

- [ ] I have not added new dependencies, OR
- [ ] I have justified new dependencies in the PR description
- [ ] New dependencies are compatible with Apache 2.0 license (no GPL/AGPL)
- [ ] I have updated `pyproject.toml` and `poetry.lock`

### Breaking Changes

- [ ] This PR does not introduce breaking changes, OR
- [ ] I have documented all breaking changes in the PR description
- [ ] I have updated the version number according to SemVer (for maintainers)

### Security

- [ ] I have not introduced any security vulnerabilities
- [ ] I have not committed secrets or sensitive data (checked with secret scanning)
- [ ] I have not hardcoded credentials, API keys, or passwords
- [ ] I have used environment variables for sensitive configuration

### License

- [ ] I confirm that my contribution is made under the Apache 2.0 license
- [ ] I have the right to submit this code
- [ ] My code does not violate any third-party licenses

## Additional Notes

<!-- Add any additional context, concerns, or questions here -->

---

## For Reviewers

<!-- This section is optional - provide guidance for reviewers -->

**Focus Areas**:
<!-- e.g., "Please review the error handling in src/workflows/maven_agent.py" -->

**Open Questions**:
<!-- e.g., "Should we add caching for this API call?" -->

---

**Thank you for contributing to TestBoost!** 🚀

See [CONTRIBUTING.md](../CONTRIBUTING.md) for more details on our contribution process.
