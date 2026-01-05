# Research: Complete Test Plan for TestBoost

**Feature**: 004-test-plan-documentation
**Date**: 2026-01-04
**Status**: Complete

## Overview

This document consolidates research findings for implementing the TestBoost test plan. All technical decisions are resolved.

---

## 1. pytest Best Practices for Async FastAPI Testing

### Decision
Use `pytest-asyncio` with `httpx.AsyncClient` for testing FastAPI async endpoints.

### Rationale
- FastAPI is async by design; sync test clients add unnecessary overhead
- `httpx.AsyncClient` integrates seamlessly with FastAPI's `TestClient`
- `pytest-asyncio` provides clean async fixture management

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| `requests` + sync TestClient | Doesn't support async, blocks event loop |
| `aiohttp` test client | Not designed for FastAPI, requires manual setup |
| `unittest.IsolatedAsyncioTestCase` | Less flexible than pytest fixtures |

### Implementation Pattern
```python
import pytest
from httpx import AsyncClient, ASGITransport
from src.api.main import app

@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
```

---

## 2. LLM Mocking Strategy with JSON Fixtures

### Decision
Use JSON fixture files with `unittest.mock.patch` to mock LLM provider responses.

### Rationale
- Deterministic test execution without API costs
- Easy to update fixtures when expected responses change
- Supports all 3 providers (Gemini, Claude, OpenAI) with same pattern

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| VCR.py recording | Captures real API calls, may leak sensitive data |
| Ollama local LLM | Requires additional setup, slower |
| respx HTTP mocking | Works but LLM SDKs abstract HTTP layer |

### Implementation Pattern
```python
import json
from unittest.mock import patch, MagicMock

@pytest.fixture
def mock_llm_response():
    with open("tests/fixtures/llm_responses/gemini_responses.json") as f:
        return json.load(f)

@pytest.fixture
def mock_llm(mock_llm_response):
    with patch("src.core.llm.get_llm") as mock:
        mock.return_value.invoke.return_value = mock_llm_response["analyze_class"]
        yield mock
```

---

## 3. Database Test Isolation with Transaction Rollback

### Decision
Use SQLAlchemy's `begin_nested()` with pytest fixture that rolls back after each test.

### Rationale
- Fast: no schema recreation between tests
- Isolated: each test sees clean database state
- Compatible with pytest-xdist parallel execution (separate transactions)

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| Fresh database per test | Too slow (schema creation takes 1-2s) |
| Truncate tables after test | Risk of missing tables, slower than rollback |
| SQLite in-memory | Different SQL dialect, async issues |

### Implementation Pattern
```python
from sqlalchemy.ext.asyncio import AsyncSession

@pytest.fixture
async def db_session(engine):
    async with engine.connect() as conn:
        trans = await conn.begin()
        async with AsyncSession(bind=conn) as session:
            yield session
        await trans.rollback()
```

---

## 4. GitHub Actions CI Configuration

### Decision
Use `ubuntu-latest` with PostgreSQL service container and parallel test execution.

### Rationale
- Standard runner (2 vCPU, 7GB) matches our performance target
- PostgreSQL service container provides isolated DB
- `pytest-xdist` with `-n auto` uses both cores

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| GitHub Actions large runner | Costs money, not needed for 5-min target |
| Self-hosted runner | Maintenance overhead, not portable |
| Docker-in-Docker | Slower startup, complexity |

### Implementation Pattern
```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: testboost
          POSTGRES_PASSWORD: testboost
          POSTGRES_DB: testboost
        ports:
          - 5433:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install poetry && poetry install
      - run: poetry run pytest tests/ -n auto --cov=src --cov-report=xml
      - uses: codecov/codecov-action@v4
```

---

## 5. Coverage Reporting and Thresholds

### Decision
Use `pytest-cov` with XML output for Codecov integration and fail-under threshold.

### Rationale
- XML format integrates with GitHub PR comments via Codecov
- `--fail-under` enforces minimum coverage in CI
- Branch coverage via `--cov-branch` flag

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| coverage.py standalone | Less pytest integration |
| Coveralls | Less popular than Codecov, similar features |
| No coverage | Can't measure progress toward 70% goal |

### Implementation Pattern
```ini
# pytest.ini
[pytest]
addopts = --cov=src --cov-branch --cov-report=term-missing --cov-fail-under=70
```

---

## 6. Flaky Test Handling

### Decision
Use `pytest-rerunfailures` with max 2 retries for integration tests only.

### Rationale
- Integration tests may have transient failures (network, timing)
- Unit tests should never be flaky (fail immediately if they are)
- 2 retries balances reliability with speed

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| No retries | CI would fail on transient network issues |
| Retry all tests | Masks real bugs in unit tests |
| pytest-flaky | Less maintained than pytest-rerunfailures |

### Implementation Pattern
```python
# Mark integration tests for retry
@pytest.mark.flaky(reruns=2, reruns_delay=1)
async def test_llm_provider_connectivity():
    ...
```

---

## 7. Pre-commit Hook for Ad-hoc Utilities

### Decision
Use `.pre-commit-config.yaml` with custom hook to detect `scripts/test-utils/` files.

### Rationale
- Prevents accidental commit of ad-hoc test utilities
- Integrates with existing pre-commit workflow
- Clear error message guides developer

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| .gitignore only | Doesn't warn, files silently ignored |
| Git pre-commit script | Not portable, not integrated with pre-commit |
| CI check | Too late, already committed |

### Implementation Pattern
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: no-adhoc-test-utils
        name: Check for ad-hoc test utilities
        entry: bash -c 'if [ -d "scripts/test-utils" ] && [ "$(ls -A scripts/test-utils 2>/dev/null)" ]; then echo "ERROR: Remove ad-hoc test utilities before commit: scripts/test-utils/"; exit 1; fi'
        language: system
        pass_filenames: false
```

---

## 8. Test Report Format

### Decision
Use JUnit XML output for GitHub Actions integration plus terminal output for local dev.

### Rationale
- GitHub Actions natively displays JUnit XML results
- Terminal output with `--tb=short` for local debugging
- Coverage XML for Codecov integration

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|------------------|
| HTML report only | Not integrated with CI, manual viewing |
| JSON output | Less tooling support than JUnit XML |
| No report | Harder to analyze failures |

### Implementation Pattern
```bash
# CI command
pytest tests/ --junitxml=test-results.xml --cov=src --cov-report=xml

# Local command (via pytest.ini defaults)
pytest tests/
```

---

## Summary

All research items resolved. No outstanding NEEDS CLARIFICATION markers.

| Topic | Decision | Confidence |
|-------|----------|------------|
| Async testing | pytest-asyncio + httpx | High |
| LLM mocking | JSON fixtures + patch | High |
| DB isolation | Transaction rollback | High |
| CI platform | GitHub Actions standard | High |
| Coverage | pytest-cov + Codecov | High |
| Flaky tests | pytest-rerunfailures | High |
| Pre-commit | Custom hook | High |
| Test reports | JUnit XML | High |
