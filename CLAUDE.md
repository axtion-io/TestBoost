# TestBoost Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-23

## Active Technologies
- Python 3.11+ (already required by DeepAgents 0.2.7) + DeepAgents 0.2.7, LangChain Core 1.1+, LangGraph 1.0+, FastAPI 0.121 (002-deepagents-integration)
- PostgreSQL 15 on port 5433 (existing, no schema changes needed) (002-deepagents-integration)
- Python 3.11+ + LangGraph 1.0+, LangChain Core 1.1+, FastAPI 0.121, Typer (CLI) (003-impact-analysis-testing)
- PostgreSQL 15 (existing, port 5433) (003-impact-analysis-testing)
- Python 3.11+ + pytest, pytest-asyncio, pytest-cov, pytest-xdist, httpx (for API testing), respx (for HTTP mocking) (004-test-plan-documentation)
- PostgreSQL 15 (port 5433) - existing schema, no changes needed (004-test-plan-documentation)
- Python 3.11+ + FastAPI 0.121, SQLAlchemy (async), Pydantic, structlog (006-file-modifications-api)
- PostgreSQL 15 (port 5433) - existing artifacts table with new metadata field (006-file-modifications-api)

- Python 3.11+ (001-testboost-core)

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

Python 3.11+: Follow standard conventions

## Recent Changes
- 006-file-modifications-api: Added Python 3.11+ + FastAPI 0.121, SQLAlchemy (async), Pydantic, structlog
- 004-test-plan-documentation: Added Python 3.11+ + pytest, pytest-asyncio, pytest-cov, pytest-xdist, httpx (for API testing), respx (for HTTP mocking)
- 003-impact-analysis-testing: Added Python 3.11+ + LangGraph 1.0+, LangChain Core 1.1+, FastAPI 0.121, Typer (CLI)


<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
