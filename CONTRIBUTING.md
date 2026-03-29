# Contributing to TestBoost

Thank you for considering contributing to TestBoost! This document covers the guidelines for contributing.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [How to Contribute](#how-to-contribute)
4. [Coding Standards](#coding-standards)
5. [Testing Requirements](#testing-requirements)
6. [Pull Request Process](#pull-request-process)
7. [Getting Help](#getting-help)

---

## Code of Conduct

This project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

---

## Getting Started

See the [Contributor Quickstart](docs/contributor-quickstart.md) for a step-by-step setup guide.

### Quick Setup

```bash
git clone https://github.com/YOUR-USERNAME/TestBoost.git
cd TestBoost
python -m venv .venv && source .venv/bin/activate
pip install poetry && poetry install
```

### Verify Installation

```bash
pytest tests/
ruff check .
```

No database, Docker, or external services are required for development.

---

## How to Contribute

### Reporting Bugs

- Search existing issues first to avoid duplicates
- Security issues: see [SECURITY.md](SECURITY.md) for private reporting
- Use the [bug report template](.github/ISSUE_TEMPLATE/bug_report.md)

### Suggesting Features

- Search existing issues and discussions first
- Use the [feature request template](.github/ISSUE_TEMPLATE/feature_request.md)

### Contributing Code

1. Find or create an issue
2. Fork the repository and create a feature branch
3. Make your changes following the coding standards
4. Write or update tests
5. Run the test suite and linting
6. Submit a pull request

---

## Coding Standards

### Python Style

- **PEP 8** with 100-character line length
- **4-space indentation** (no tabs)
- **Double quotes** for strings
- **Imports** organized: standard library, third-party, local (separated by blank lines)

### Type Hints

Always use type hints for function signatures:

```python
async def analyze_project(project_path: str, verbose: bool = False) -> dict:
    ...
```

### Async/Await

Use async Python for all I/O operations:

```python
result_json = await analyze_project_context(project_path)
```

### Docstrings

Use Google-style docstrings for public functions:

```python
async def generate_tests(project_path: str, source_file: str) -> str:
    """Generate unit tests for a Java source file.

    Args:
        project_path: Path to the Java project root.
        source_file: Relative path to the source file.

    Returns:
        JSON string with test generation results.

    Raises:
        ValueError: If source_file does not exist.
    """
```

### Linting

Before submitting:

```bash
ruff check .          # Lint
ruff check --fix .    # Auto-fix
mypy src/             # Type check
```

All PRs must pass linting and type checking.

---

## Testing Requirements

### Running Tests

```bash
# All tests
pytest tests/

# With coverage
pytest --cov=src --cov=testboost --cov-report=html

# Specific test file
pytest tests/unit/test_cli.py

# Tests matching a pattern
pytest -k "test_session"
```

### Coverage Expectations

- **New features**: 80% minimum coverage for new code
- **Bug fixes**: Must include a regression test covering the bug path
- **TestBoost CLI**: Tests in `testboost/tests/`
- **Core functions**: Tests in `tests/`

### Test Naming

Use the pattern `test_<function>_<scenario>`:

```python
def test_init_creates_session_directory():
    ...

def test_analyze_fails_when_no_session():
    ...
```

### Mocking the Bridge

When testing CLI commands, mock functions at the bridge level:

```python
@patch("testboost.lib.testboost_bridge.analyze_project_context")
async def test_analyze_success(mock_analyze):
    mock_analyze.return_value = '{"success": true, ...}'
    ...
```

---

## Pull Request Process

### Before Submitting

1. Create a feature branch from `main`
2. Make clear, atomic commits
3. Run quality checks: `pytest && ruff check . && mypy src/`
4. Push to your fork

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add coverage gap detection for Gradle projects
fix: handle timeout in LLM test generation
docs: update workflow documentation
test: add tests for session tracker edge cases
refactor: extract prompt builder from generate command
chore: bump langchain-google-genai to v4
```

### PR Review Criteria

- **Functionality**: Does it work as intended?
- **Tests**: Adequate coverage? All passing?
- **Code quality**: Follows standards? No code smells?
- **Documentation**: Updated where needed?
- **Security**: No vulnerabilities introduced?

---

## Getting Help

- **GitHub Discussions**: [Ask questions, share ideas](https://github.com/axtion-io/TestBoost/discussions)
- **GitHub Issues**: [Report bugs, request features](https://github.com/axtion-io/TestBoost/issues)
- **Security Issues**: See [SECURITY.md](SECURITY.md)

We aim to respond to issues within 48 hours and review PRs within 3-5 business days.
