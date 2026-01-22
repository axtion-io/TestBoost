# Contributing to TestBoost

Thank you for your interest in contributing to TestBoost! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Contributions](#making-contributions)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Community](#community)

---

## Code of Conduct

By participating in this project, you agree to maintain a respectful, inclusive environment for all contributors. We expect everyone to:

- Be respectful and constructive in discussions
- Welcome newcomers and help them get started
- Focus on what is best for the community
- Show empathy towards other community members

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- Python 3.11+
- PostgreSQL 15+ or Docker
- Maven 3.6+ (for testing Java project analysis features)
- Git

### Understanding the Project

TestBoost is an AI-powered Java/Spring Boot test generation and maintenance platform. Key areas include:

| Area | Directory | Description |
|------|-----------|-------------|
| API | `src/api/` | FastAPI REST endpoints |
| CLI | `src/cli/` | Typer command-line interface |
| Core | `src/core/` | Business logic and utilities |
| Database | `src/db/` | SQLAlchemy models and migrations |
| Workflows | `src/workflows/` | LangGraph state machines |
| Agents | `src/agents/` | DeepAgents configurations |
| MCP Servers | `src/mcp_servers/` | Model Context Protocol tools |
| Configuration | `config/` | Agent and prompt configurations |
| Tests | `tests/` | Unit and integration tests |

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/<your-username>/TestBoost.git
cd TestBoost
```

### 2. Set Up Python Environment

```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

### 3. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 4. Start Services

```bash
# Start PostgreSQL
docker-compose up -d postgres

# Run database migrations
alembic upgrade head
```

### 5. Verify Setup

```bash
# Run tests to verify everything works
pytest tests/

# Start the API server
uvicorn src.api.main:app --reload
```

---

## Making Contributions

### Types of Contributions

We welcome various types of contributions:

| Type | Description | Label |
|------|-------------|-------|
| Bug Fix | Fix an existing bug | `bug` |
| Feature | Add new functionality | `enhancement` |
| Documentation | Improve or add documentation | `documentation` |
| Test | Add or improve tests | `testing` |
| Refactor | Improve code structure | `refactor` |
| Performance | Optimize performance | `performance` |

### Contribution Workflow

1. **Check existing issues**: Look for related issues before starting work
2. **Create an issue**: For significant changes, create an issue first to discuss
3. **Fork the repository**: Create your own fork to work on
4. **Create a feature branch**: Branch from `main` with a descriptive name
5. **Make your changes**: Follow code style guidelines
6. **Write tests**: Ensure adequate test coverage
7. **Run quality checks**: Pass all linting and tests
8. **Submit a pull request**: Follow the PR template

### Branch Naming Convention

Use descriptive branch names following this pattern:

```
<type>/<short-description>

Examples:
feature/add-snapshot-tests
fix/maven-dependency-parsing
docs/update-api-reference
refactor/simplify-workflow-state
```

---

## Code Style Guidelines

### Python Style

We follow PEP 8 with some project-specific conventions:

```bash
# Run linting
ruff check src/

# Run formatting
black src/

# Run type checking
mypy src/
```

### Key Conventions

| Convention | Example | Notes |
|------------|---------|-------|
| Class names | `PascalCase` | `SessionManager`, `WorkflowState` |
| Functions | `snake_case` | `create_session`, `run_workflow` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRIES`, `DEFAULT_TIMEOUT` |
| Private | `_leading_underscore` | `_internal_method` |
| Type hints | Required | All functions must have type hints |

### Documentation Standards

- All public functions require docstrings
- Use Google-style docstrings
- Include type information in docstrings

```python
def create_session(
    project_id: str,
    workflow_type: str,
    *,
    mode: str = "assisted"
) -> Session:
    """Create a new workflow session.

    Args:
        project_id: The UUID of the target project.
        workflow_type: Type of workflow (maintenance, testing, deployment).
        mode: Execution mode - "assisted" or "autonomous".

    Returns:
        Session: The newly created session object.

    Raises:
        ProjectNotFoundError: If the project doesn't exist.
        ValidationError: If parameters are invalid.
    """
```

### Import Organization

Organize imports in this order:

1. Standard library imports
2. Third-party imports
3. Local application imports

```python
# Standard library
import asyncio
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# Local
from src.core.session import SessionManager
from src.db.models import Session
```

---

## Testing Requirements

### Test Coverage

All contributions must include appropriate tests:

| Requirement | Threshold | Description |
|-------------|-----------|-------------|
| Line coverage | 70% minimum | New code must be tested |
| Branch coverage | 60% minimum | Decision paths covered |
| Integration tests | Required | For API changes |

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test category
pytest tests/unit/
pytest tests/integration/

# Run tests in parallel
pytest tests/ -n auto
```

### Writing Tests

Follow these guidelines when writing tests:

```python
import pytest
from httpx import AsyncClient

from src.api.main import app


class TestSessionEndpoints:
    """Test suite for session API endpoints."""

    @pytest.fixture
    async def client(self) -> AsyncClient:
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client

    @pytest.mark.asyncio
    async def test_create_session_success(self, client: AsyncClient):
        """Test successful session creation."""
        response = await client.post(
            "/api/v2/sessions",
            json={"project_id": "test-project", "workflow_type": "maintenance"}
        )
        assert response.status_code == 201
        assert "id" in response.json()

    @pytest.mark.asyncio
    async def test_create_session_invalid_project(self, client: AsyncClient):
        """Test session creation with invalid project."""
        response = await client.post(
            "/api/v2/sessions",
            json={"project_id": "nonexistent", "workflow_type": "maintenance"}
        )
        assert response.status_code == 404
```

---

## Pull Request Process

### Before Submitting

1. **Run quality checks**:
   ```bash
   ruff check src/
   black src/
   mypy src/
   pytest tests/
   ```

2. **Update documentation**: If your changes affect user-facing features

3. **Add changelog entry**: For significant changes

### PR Template

When creating a pull request, include:

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing performed

## Checklist
- [ ] Code follows project style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] No new warnings introduced
```

### Review Process

| Stage | Description | Timeline |
|-------|-------------|----------|
| Initial Review | Maintainer assigns reviewers | 1-2 days |
| Code Review | Technical review and feedback | 3-5 days |
| Revision | Address review comments | As needed |
| Approval | Requires 1 maintainer approval | - |
| Merge | Squash merge to main | After approval |

---

## Issue Guidelines

### Bug Reports

When reporting bugs, include:

- **Description**: Clear description of the issue
- **Steps to Reproduce**: Minimal steps to reproduce
- **Expected Behavior**: What should happen
- **Actual Behavior**: What actually happens
- **Environment**: Python version, OS, relevant configuration
- **Logs**: Relevant error messages or stack traces

### Feature Requests

When requesting features:

- **Use Case**: Describe the problem you're trying to solve
- **Proposed Solution**: Your suggested approach
- **Alternatives**: Other approaches considered
- **Additional Context**: Mockups, examples, or references

### Issue Labels

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature or improvement |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Extra attention needed |
| `priority: high` | Critical issues |
| `priority: low` | Nice to have |

---

## Community

### Getting Help

- **GitHub Issues**: For bugs and feature requests
- **Discussions**: For questions and general discussion
- **Documentation**: Check the `docs/` directory

### Recognition

Contributors are recognized in:

- Release notes for significant contributions
- The project's CONTRIBUTORS file (if applicable)
- GitHub's contributor graph

---

## License

By contributing to TestBoost, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to TestBoost!
