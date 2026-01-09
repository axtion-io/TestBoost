# Quickstart: TestBoost Test Plan Implementation

**Feature**: 004-test-plan-documentation
**Date**: 2026-01-04

## Prerequisites

- Python 3.11+
- Poetry installed
- Docker (for PostgreSQL service)
- Git

## Quick Setup

### 1. Install Test Dependencies

```bash
cd TestBoost
poetry install --with dev
```

### 2. Start PostgreSQL

```bash
docker compose up -d postgres
```

### 3. Run All Tests

```bash
# Run all tests with coverage
poetry run pytest tests/ --cov=src --cov-report=term-missing

# Run unit tests only (fast)
poetry run pytest tests/unit/ -v

# Run integration tests (requires services)
poetry run pytest tests/integration/ -v

# Run with parallel execution
poetry run pytest tests/ -n auto
```

## Test Commands Cheatsheet

| Command | Purpose |
|---------|---------|
| `pytest tests/` | Run all tests |
| `pytest tests/unit/` | Unit tests only |
| `pytest tests/integration/` | Integration tests only |
| `pytest -k "test_health"` | Run tests matching pattern |
| `pytest --cov=src` | With coverage report |
| `pytest -n auto` | Parallel execution |
| `pytest -x` | Stop on first failure |
| `pytest --lf` | Run last failed tests |

## Creating New Tests

### Unit Test Template

```python
# tests/unit/api/test_example.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_example_endpoint(client: AsyncClient):
    """Test description."""
    response = await client.get("/api/v2/example")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

### Integration Test Template

```python
# tests/integration/test_example.py
import pytest

@pytest.mark.integration
@pytest.mark.requires_db
@pytest.mark.asyncio
async def test_database_operation(db_session):
    """Test database integration."""
    # Test implementation
    pass
```

## Coverage Report

After running tests with `--cov`, view the HTML report:

```bash
poetry run pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

## Manual Testing

See [docs/manual-test-checklist.md](../../../docs/manual-test-checklist.md) for the complete manual testing checklist.

### Quick Manual Smoke Test

1. Start services: `docker compose up -d`
2. Run migrations: `poetry run alembic upgrade head`
3. Start API: `poetry run uvicorn src.api.main:app --reload`
4. Check health: `curl http://localhost:8000/health`
5. Expected: `{"status": "healthy", ...}`

## Ad-hoc Utilities

Temporary test utilities go in `scripts/test-utils/`. These are **not committed**.

```bash
# Create ad-hoc utility
cp scripts/test-utils/template.py scripts/test-utils/my_test.py

# Run it
poetry run python scripts/test-utils/my_test.py

# Delete before commit!
rm scripts/test-utils/my_test.py
```

## CI Pipeline

Tests run automatically on GitHub Actions for every push and PR.

- **Trigger**: Push to any branch, PR to main
- **Environment**: ubuntu-latest, Python 3.11, PostgreSQL 15
- **Timeout**: 10 minutes (target: < 5 minutes)
- **Coverage**: Reported to Codecov

## Troubleshooting

### Tests failing locally but passing in CI?

1. Check Python version: `python --version` (need 3.11+)
2. Check PostgreSQL: `docker compose ps`
3. Reset database: `docker compose down -v && docker compose up -d postgres`

### Coverage too low?

1. Run with `--cov-report=term-missing` to see uncovered lines
2. Focus on high-priority modules (api, cli, workflows)
3. Add tests for edge cases and error handling

### Flaky tests?

1. Mark with `@pytest.mark.flaky(reruns=2)` for integration tests
2. Unit tests should never be flaky - investigate root cause
3. Check for timing issues or shared state

## Next Steps

1. Run existing tests to establish baseline
2. Implement P1 tests first (api, cli, workflows)
3. Add coverage reporting to CI
4. Create LLM fixture files
5. Document manual test results
