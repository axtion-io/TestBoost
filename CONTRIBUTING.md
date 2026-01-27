# Contributing to TestBoost

First off, thank you for considering contributing to TestBoost! It's people like you that make TestBoost such a great tool for the community.

## Table of Contents

1. [Code of Conduct](#code-of-conduct)
2. [Getting Started](#getting-started)
3. [Development Setup](#development-setup)
4. [How to Contribute](#how-to-contribute)
5. [Coding Standards](#coding-standards)
6. [Testing Requirements](#testing-requirements)
7. [Pull Request Process](#pull-request-process)
8. [Review Timeline](#review-timeline)
9. [Getting Help](#getting-help)

---

## Code of Conduct

This project and everyone participating in it is governed by the [TestBoost Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

---

## Getting Started

### Good First Issues

Looking for a place to start? Check out issues labeled:
- [`good first issue`](https://github.com/cheche71/TestBoost/labels/good%20first%20issue) - Perfect for newcomers
- [`help wanted`](https://github.com/cheche71/TestBoost/labels/help%20wanted) - Community contributions welcome
- [`documentation`](https://github.com/cheche71/TestBoost/labels/documentation) - Easy entry point

### Ways to Contribute

We welcome many types of contributions:

- **Bug Reports**: Found a bug? Let us know!
- **Feature Requests**: Have an idea? We'd love to hear it!
- **Code Contributions**: Fix bugs, add features, improve performance
- **Documentation**: Improve README, add examples, write guides
- **Testing**: Expand test coverage, report edge cases
- **Community Support**: Help others in Discussions and Issues

---

## Development Setup

For a complete step-by-step setup guide, see our **[Contributor Quickstart Guide](docs/contributor-quickstart.md)**.

### Quick Setup

1. **Fork and Clone**
```bash
git clone https://github.com/YOUR-USERNAME/TestBoost.git
cd TestBoost
```

2. **Set Up Environment**
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

3. **Configure Database**
```bash
docker-compose up -d postgres
alembic upgrade head
```

4. **Create .env File**
```bash
cp .env.example .env
# Edit .env with your API keys (required for testing workflows)
```

5. **Verify Installation**
```bash
pytest tests/unit/
ruff check .
```

---

## How to Contribute

### Reporting Bugs

Before creating a bug report:
- **Search existing issues** to avoid duplicates
- **Check if it's a security issue** - if so, see [SECURITY.md](SECURITY.md) for private reporting

When creating a bug report, use our **bug report template** and include:
- Clear description of the issue
- Steps to reproduce
- Expected vs actual behavior
- TestBoost version, Python version, OS
- Relevant logs or error messages

### Suggesting Features

Before requesting a feature:
- **Search existing issues and discussions** to avoid duplicates
- **Describe the problem**, not just the solution
- **Consider if it fits TestBoost's scope** (AI-powered Java/Spring Boot maintenance)

When suggesting a feature, use our **feature request template** and include:
- Problem statement (what use case does it address?)
- Proposed solution (how should it work?)
- Alternative solutions you've considered
- Use cases and examples

### Contributing Code

1. **Find or create an issue** describing the bug or feature
2. **Comment on the issue** to let others know you're working on it
3. **Fork the repository** and create a feature branch
4. **Make your changes** following our coding standards
5. **Write or update tests** to cover your changes
6. **Run the test suite** to ensure everything passes
7. **Submit a pull request** following our PR template

---

## Coding Standards

### Python Style Guide

We follow **PEP 8** with some project-specific conventions:

#### Code Formatting

- **Line length**: 100 characters (not the PEP 8 default of 79)
- **Indentation**: 4 spaces (no tabs)
- **Quotes**: Double quotes for strings, single quotes for dict keys
- **Imports**: Organized by standard library, third-party, local (separated by blank lines)

#### Type Hints

**Always use type hints** for function signatures:

```python
# Good
async def create_session(
    project_path: str,
    session_type: str,
    db: AsyncSession
) -> Session:
    ...

# Bad - no type hints
async def create_session(project_path, session_type, db):
    ...
```

#### Async/Await

TestBoost uses **async Python** throughout:

```python
# Good - async for I/O operations
async with AsyncSession() as db:
    result = await db.execute(select(Session))

# Bad - blocking I/O
with Session() as db:
    result = db.execute(select(Session))
```

#### Structured Logging

Use `structlog` for all logging:

```python
from src.lib.logging import get_logger

logger = get_logger(__name__)

# Good - structured with context
logger.info("session_created", session_id=session.id, user_id=user.id)

# Bad - string formatting
logger.info(f"Session {session.id} created for user {user.id}")
```

#### Docstrings

Use **Google-style docstrings** for public functions:

```python
async def execute_workflow(workflow_id: str, config: dict) -> WorkflowResult:
    """Execute a workflow with the given configuration.

    Args:
        workflow_id: Unique identifier for the workflow
        config: Workflow configuration dictionary

    Returns:
        WorkflowResult containing execution status and outputs

    Raises:
        WorkflowNotFoundError: If workflow_id doesn't exist
        ConfigValidationError: If config is invalid
    """
    ...
```

### Linting and Type Checking

Before submitting a PR, run:

```bash
# Linting with Ruff
ruff check .

# Auto-fix issues
ruff check --fix .

# Type checking with mypy
mypy src/ --ignore-missing-imports
```

**All PRs must pass linting and type checking** before being merged.

---

## Testing Requirements

### Current Test Coverage

- **Current coverage**: 36% (as of 2026-01-26)
- **Target coverage**: 80% (long-term goal)
- **Minimum requirement**: 36% (prevent regression)

### Coverage Expectations

#### For New Features
- **Minimum 80% coverage** for new code
- Must include unit tests for all business logic
- Must include integration tests for API endpoints and workflows

#### For Bug Fixes
- **Must cover the bug path** that was previously failing
- Add a regression test to prevent the bug from recurring

### Running Tests

```bash
# All tests
pytest

# Specific test categories
pytest tests/unit/
pytest tests/integration/
pytest tests/e2e/

# With coverage report
pytest --cov=src --cov-report=html
# View report: open htmlcov/index.html

# Specific test file
pytest tests/unit/test_example.py

# Specific test function
pytest tests/unit/test_example.py::test_specific_function

# Tests matching a pattern
pytest -k "test_session"
```

### Test Categories

- **Unit Tests** (`tests/unit/`): Test individual functions/classes in isolation
- **Integration Tests** (`tests/integration/`): Test interactions between components
- **E2E Tests** (`tests/e2e/`): Test complete workflows end-to-end
- **Regression Tests** (`tests/regression/`): Prevent previously fixed bugs from recurring
- **Security Tests** (`tests/security/`): Test security-critical functionality

### Writing Good Tests

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
async def db_session() -> AsyncSession:
    """Provide a clean database session for testing."""
    async with SessionLocal() as session:
        yield session
        await session.rollback()  # Cleanup

async def test_create_session_success(db_session):
    """Test successful session creation with valid inputs."""
    # Arrange
    project_path = "/path/to/project"
    session_type = "test_gen"

    # Act
    session = await create_session(project_path, session_type, db_session)

    # Assert
    assert session.id is not None
    assert session.project_path == project_path
    assert session.status == "created"
```

**Test Naming Convention**: `test_<function>_<scenario>` (e.g., `test_create_session_invalid_path`)

---

## Pull Request Process

### Before Submitting

1. **Create a feature branch** from `main`:
   ```bash
   git checkout main
   git pull origin main
   git checkout -b feature/short-description
   ```

2. **Make your changes** with clear, atomic commits:
   ```bash
   git add <files>
   git commit -m "feat: add session timeout handling

   - Add timeout configuration to session settings
   - Implement automatic cleanup for expired sessions
   - Add tests for timeout edge cases

   Fixes #123"
   ```

3. **Run all quality checks locally**:
   ```bash
   pytest && ruff check . && mypy src/
   ```

4. **Push to your fork**:
   ```bash
   git push origin feature/short-description
   ```

### Commit Message Format

We follow the **Conventional Commits** specification:

```
<type>: <short description>

<optional detailed description>

<optional footer>
```

**Types**:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding or updating tests
- `refactor:` - Code refactoring (no functionality change)
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks (dependencies, config)
- `ci:` - CI/CD changes

**Examples**:
```bash
feat: add test coverage reporting to CI

fix: handle timeout errors in LLM client

docs: update installation instructions for Windows

test: add integration tests for maven workflow

refactor: extract retry logic to shared utility
```

### Pull Request Template

When creating a PR, fill out the template with:
- **Description**: What does this PR do?
- **Related Issue**: Link to the issue (e.g., `Fixes #123`)
- **Type of Change**: Bug fix, feature, docs, etc.
- **Testing Evidence**: Show that tests pass locally
- **Checklist**: Confirm all items are complete

### PR Review Criteria

Your PR will be reviewed for:
- **Functionality**: Does it work as intended?
- **Tests**: Are there adequate tests? Do they pass?
- **Code Quality**: Follows coding standards? No code smells?
- **Documentation**: Is it clear what the code does?
- **Performance**: No obvious performance issues?
- **Security**: No security vulnerabilities introduced?
- **Breaking Changes**: Are they documented and justified?

---

## Review Timeline

We aim to provide timely feedback on contributions:

- **Initial Response**: Within 48 hours (excluding weekends)
- **PR Review**: Within 3-5 business days for active PRs
- **Urgent Issues**: Tag with `urgent` label for faster response

**Please note**:
- Larger PRs may take longer to review
- Reviews may request changes before approval
- Maintainers may ask for clarifications or additional tests

---

## Getting Help

### Communication Channels

- **GitHub Discussions**: https://github.com/cheche71/TestBoost/discussions
  - Ask questions
  - Share ideas
  - Show off your projects using TestBoost

- **GitHub Issues**: https://github.com/cheche71/TestBoost/issues
  - Report bugs
  - Request features
  - Track work in progress

- **Security Issues**: See [SECURITY.md](SECURITY.md)
  - **Never** report security vulnerabilities in public issues
  - Email security@testboost.dev (private reporting)

### Common Questions

**Q: I'm new to Python/FastAPI/LangGraph. Can I still contribute?**
A: Absolutely! Start with issues labeled `good first issue` or `documentation`. We're happy to guide you through your first contribution.

**Q: My PR hasn't been reviewed yet. What should I do?**
A: If it's been more than 5 business days, add a polite comment mentioning @maintainers. We may have missed the notification.

**Q: Can I work on an issue that's already assigned?**
A: Check the issue comments first. If there's been no activity for 2+ weeks, ask if it's still being worked on.

**Q: I found a bug but can't fix it myself. What should I do?**
A: That's perfectly fine! Create a detailed bug report with our template. Others in the community may be able to fix it.

**Q: My tests are failing in CI but pass locally. Help?**
A: This usually means environment differences. Check:
- Python version (CI uses 3.11)
- PostgreSQL version (CI uses 15)
- Environment variables (CI uses test values)

**Q: Do I need to sign a CLA?**
A: No. By submitting a PR, you agree your contribution is made under the Apache 2.0 license (as stated in the PR template).

---

## Additional Resources

- **[README.md](README.md)** - Project overview and quick start
- **[Contributor Quickstart](specs/008-opensource-release/quickstart.md)** - Detailed setup guide
- **[SECURITY.md](SECURITY.md)** - Security policy and vulnerability reporting
- **[LICENSE](LICENSE)** - Apache 2.0 license terms

---

## Recognition

Contributors are recognized in:
- GitHub Contributors page
- Release notes for significant contributions
- Special thanks in project announcements

Thank you for making TestBoost better! 🚀

---

**Questions?** Feel free to ask in [GitHub Discussions](https://github.com/cheche71/TestBoost/discussions) or open an issue with the `question` label.
