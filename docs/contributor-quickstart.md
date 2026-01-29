# Contributor Quickstart Guide

**Welcome to TestBoost!** This guide will help you set up your development environment and make your first contribution in under 30 minutes.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Setup (10 minutes)](#quick-setup-10-minutes)
3. [Running Tests (5 minutes)](#running-tests-5-minutes)
4. [Making Your First Contribution](#making-your-first-contribution)
5. [Project Structure](#project-structure)
6. [Key Patterns](#key-patterns)
7. [Getting Help](#getting-help)

---

## Prerequisites

Before starting, ensure you have:

- **Python 3.11+** ([download](https://www.python.org/downloads/))
- **Git** ([download](https://git-scm.com/downloads))
- **PostgreSQL 15+** ([download](https://www.postgresql.org/download/)) OR **Docker** ([download](https://www.docker.com/get-started/))
- **GitHub account** for contributing

Optional but recommended:
- **Poetry** ([install](https://python-poetry.org/docs/#installation)) - Python dependency management
- **VS Code** with Python extension ([download](https://code.visualstudio.com/))

---

## Quick Setup (10 minutes)

### 1. Fork and Clone

```bash
# Fork the repository on GitHub (click "Fork" button)
# Then clone YOUR fork
git clone https://github.com/YOUR-USERNAME/TestBoost.git
cd TestBoost
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate it
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install Poetry (if not already installed)
pip install poetry

# Install all dependencies
poetry install
```

### 3. Set Up Database

**Option A: Using Docker** (Recommended for contributors)
```bash
# Start PostgreSQL in Docker
docker-compose up -d postgres

# Verify it's running
docker ps
```

**Option B: Using Local PostgreSQL**
```bash
# Create database
createdb -U postgres testboost

# Update connection string if needed
# Edit .env file (see step 4)
```

### 4. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
# Minimum required for local development:
DATABASE_URL=postgresql+asyncpg://testboost:testboost@localhost:5433/testboost
GOOGLE_API_KEY=your-google-api-key-here  # Required for LLM features
```

> **Note**: You'll need a Google Gemini API key for full functionality. Get one free at [https://makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)

### 5. Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify migrations
alembic current
```

### 6. Verify Installation

```bash
# Run quick health check
python -c "from src.api.main import app; print('✅ Installation successful!')"

# Start the API server
uvicorn src.api.main:app --reload

# Open http://localhost:8000/docs in your browser
# You should see the API documentation
```

---

## Running Tests (5 minutes)

### Run All Tests

```bash
# From the project root
cd src
pytest

# With coverage report
pytest --cov=src --cov-report=html

# Open coverage report
# Windows: start htmlcov\index.html
# macOS: open htmlcov/index.html
# Linux: xdg-open htmlcov/index.html
```

### Run Specific Test Categories

```bash
# Unit tests only
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# Specific test file
pytest tests/unit/test_example.py

# Specific test function
pytest tests/unit/test_example.py::test_specific_function

# Tests matching a pattern
pytest -k "test_session"
```

### Run Code Quality Checks

```bash
# Linting with ruff
ruff check .

# Auto-fix issues
ruff check --fix .

# Type checking with mypy
mypy src/

# Run all quality checks (what CI runs)
ruff check . && mypy src/ && pytest
```

---

## Making Your First Contribution

### Step 1: Find an Issue

Look for issues labeled:
- [`good first issue`](https://github.com/axtion-io/TestBoost/labels/good%20first%20issue) - Perfect for newcomers
- [`help wanted`](https://github.com/axtion-io/TestBoost/labels/help%20wanted) - Community contributions welcome
- [`documentation`](https://github.com/axtion-io/TestBoost/labels/documentation) - Easy entry point

Or report a bug/suggest a feature by creating an issue.

### Step 2: Create a Feature Branch

```bash
# Update main branch
git checkout main
git pull origin main

# Create your feature branch
git checkout -b feature/short-description
# or
git checkout -b fix/bug-description
```

### Step 3: Make Your Changes

```python
# Edit files...
# Add tests...

# Run tests to verify
pytest tests/

# Run linting
ruff check --fix .
```

### Step 4: Commit Your Changes

```bash
# Stage your changes
git add .

# Commit with descriptive message
git commit -m "feat: add test coverage for step executor

- Add unit tests for execute_step function
- Add integration tests for async execution
- Achieve 80% coverage for core module

Fixes #123"
```

**Commit Message Format**:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Adding tests
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### Step 5: Push and Create Pull Request

```bash
# Push to your fork
git push origin feature/short-description

# Go to GitHub and create Pull Request
# Fill out the PR template
# Link related issues
```

### Step 6: Respond to Reviews

- Be open to feedback
- Make requested changes
- Ask questions if something is unclear
- Push additional commits to update PR

---

## Project Structure

```
TestBoost/
├── src/                        # Source code
│   ├── api/                    # FastAPI REST API
│   │   ├── main.py            # API entry point
│   │   ├── routers/           # API endpoints
│   │   ├── middleware/        # Logging, error handling
│   │   └── models/            # Pydantic models
│   │
│   ├── cli/                    # Command-line interface
│   │   ├── main.py            # CLI entry point
│   │   └── commands/          # Command implementations
│   │
│   ├── core/                   # Core business logic
│   │   ├── session.py         # Session management
│   │   └── step_executor.py   # Workflow execution
│   │
│   ├── workflows/              # LangGraph workflows
│   │   ├── test_generation_agent.py
│   │   ├── maven_maintenance_agent.py
│   │   └── docker_deployment_agent.py
│   │
│   ├── agents/                 # DeepAgents configurations
│   │   ├── loader.py          # Agent loading
│   │   └── adapter.py         # Agent adaptation
│   │
│   ├── mcp_servers/            # MCP tool servers
│   │   ├── test_generator/    # Test generation tools
│   │   ├── maven_maintenance/ # Maven tools
│   │   └── container_runtime/ # Docker tools
│   │
│   ├── db/                     # Database layer
│   │   ├── models/            # SQLAlchemy models
│   │   └── migrations/        # Alembic migrations
│   │
│   └── lib/                    # Shared utilities
│       ├── llm.py             # LLM client creation
│       ├── logging.py         # Structured logging
│       └── config.py          # Configuration loading
│
├── tests/                      # Test suite
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   ├── e2e/                   # End-to-end tests
│   ├── regression/            # Regression tests
│   ├── security/              # Security tests
│   ├── conftest.py            # Pytest configuration
│   └── fixtures/              # Test fixtures
│
├── config/                     # Configuration files
│   ├── agents/                # Agent YAML configs
│   └── prompts/               # Prompt templates
│
├── docs/                       # Documentation
│   ├── api-*.md              # API documentation
│   └── testing-strategy.md   # Test strategy
│
├── .github/                    # GitHub workflows
│   └── workflows/             # CI/CD pipelines
│
├── pyproject.toml              # Project dependencies
├── README.md                   # Project overview
└── CONTRIBUTING.md             # Contribution guide (detailed)
```

---

## Key Patterns

### 1. Async/Await Everywhere

TestBoost uses async Python for all I/O operations:

```python
# Database operations
async with SessionLocal() as db:
    result = await db.execute(select(Session))

# HTTP requests
async with httpx.AsyncClient() as client:
    response = await client.get("https://api.example.com")

# LangGraph workflows
result = await agent.ainvoke({"messages": messages})
```

### 2. Structured Logging

Use `structlog` for consistent, queryable logs:

```python
from src.lib.logging import get_logger

logger = get_logger(__name__)

# Good: Structured logging
logger.info("session_created", session_id=session.id, user_id=user.id)

# Avoid: String formatting
logger.info(f"Session {session.id} created")  # ❌
```

### 3. Dependency Injection

FastAPI uses dependency injection:

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.db import get_db

@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    # db is automatically injected
    result = await db.execute(select(Session))
    return result.scalars().all()
```

### 4. Type Hints

Always use type hints:

```python
from typing import Optional

async def create_session(
    project_path: str,
    session_type: str,
    db: AsyncSession
) -> Session:
    session = Session(project_path=project_path, session_type=session_type)
    db.add(session)
    await db.commit()
    return session
```

### 5. Test Fixtures

Reuse test setup with pytest fixtures:

```python
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
async def db_session() -> AsyncSession:
    async with SessionLocal() as session:
        yield session
        await session.rollback()

def test_create_session(db_session):
    # db_session is automatically provided
    session = await create_session("./project", "test_gen", db_session)
    assert session.id is not None
```

### 6. Configuration from Environment

Use `.env` files and `pydantic-settings`:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str
    google_api_key: str

    class Config:
        env_file = ".env"

settings = Settings()
```

---

## Common Development Tasks

### Adding a New API Endpoint

```python
# 1. Create router in src/api/routers/your_router.py
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1", tags=["your-feature"])

@router.get("/your-endpoint")
async def your_endpoint():
    return {"message": "Hello"}

# 2. Register router in src/api/main.py
from src.api.routers import your_router

app.include_router(your_router.router)

# 3. Add tests in tests/unit/api/test_your_router.py
async def test_your_endpoint(client):
    response = await client.get("/api/v1/your-endpoint")
    assert response.status_code == 200
```

### Adding a Database Model

```python
# 1. Create model in src/db/models/your_model.py
from sqlalchemy import Column, Integer, String
from src.db import Base

class YourModel(Base):
    __tablename__ = "your_table"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

# 2. Create migration
alembic revision --autogenerate -m "Add your_table"

# 3. Review and apply migration
alembic upgrade head

# 4. Add tests
```

### Adding a CLI Command

```python
# 1. Create command in src/cli/commands/your_command.py
import typer

app = typer.Typer()

@app.command()
def your_command(name: str):
    """Your command description."""
    typer.echo(f"Hello {name}")

# 2. Register in src/cli/main.py
from src.cli.commands import your_command

app.add_typer(your_command.app, name="your-cmd")

# 3. Test it
python -m src.cli.main your-cmd your-argument
```

---

## Troubleshooting

### Tests Failing Locally

```bash
# Clear pytest cache
rm -rf .pytest_cache

# Recreate database
docker-compose down postgres
docker-compose up -d postgres
alembic upgrade head

# Run tests with verbose output
pytest -vv
```

### Import Errors

```bash
# Ensure you're in the right directory
pwd  # Should be TestBoost root

# Reinstall dependencies
poetry install

# Check PYTHONPATH (should include src/)
echo $PYTHONPATH  # Linux/macOS
echo %PYTHONPATH%  # Windows
```

### Database Connection Errors

```bash
# Check PostgreSQL is running
docker ps

# Test connection manually
psql -h localhost -p 5433 -U testboost -d testboost

# Check .env file has correct DATABASE_URL
cat .env | grep DATABASE_URL
```

### LLM API Errors

```bash
# Verify API key is set
echo $GOOGLE_API_KEY  # Linux/macOS
echo %GOOGLE_API_KEY%  # Windows

# Test LLM connection
python -c "from src.lib.llm import create_llm; llm = create_llm('google-genai'); print('✅ LLM connected')"
```

---

## Getting Help

### Resources

- **Documentation**: Check `docs/` folder for detailed guides
- **GitHub Discussions**: [Discussions](https://github.com/axtion-io/TestBoost/discussions) - Ask questions, share ideas
- **GitHub Issues**: [Issues](https://github.com/axtion-io/TestBoost/issues) - Report bugs, request features
- **CONTRIBUTING.md**: Detailed contribution guidelines

### Communication

- **Questions**: Use GitHub Discussions (preferred) or open an issue with `question` label
- **Bugs**: Create an issue using the bug report template
- **Features**: Create an issue using the feature request template
- **Security**: Email security@[domain] (see SECURITY.md)

### Response Times

- **Initial Response**: We aim for 48 hours (excluding weekends)
- **PR Reviews**: Usually within 3-5 business days
- **Urgent Issues**: Tag with `urgent` label

---

## Next Steps

1. **Set up your environment** following the Quick Setup guide
2. **Run the tests** to verify everything works
3. **Pick a `good first issue`** from GitHub
4. **Make your first contribution** following the guide above
5. **Read CONTRIBUTING.md** for detailed guidelines

**Welcome to the TestBoost community!** We're excited to work with you. 🚀

---

## Quick Reference

```bash
# Common commands
poetry install                  # Install dependencies
pytest                         # Run tests
ruff check .                   # Lint code
alembic upgrade head           # Apply migrations
uvicorn src.api.main:app      # Start API server
python -m src.cli.main         # Run CLI

# Workflow
git checkout -b feature/name   # Create branch
# ... make changes ...
pytest && ruff check .         # Verify
git commit -m "feat: ..."      # Commit
git push origin feature/name   # Push
# Create PR on GitHub
```

---

**Document Version**: 1.0
**Last Updated**: 2026-01-26
**Status**: Ready for contributors
