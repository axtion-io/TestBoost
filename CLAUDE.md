# TestBoost Development Guidelines

Auto-generated from all feature plans. Last updated: 2025-11-23

## Active Technologies
- Python 3.11+ (already required by DeepAgents 0.2.7) + DeepAgents 0.2.7, LangChain Core 1.1+, LangGraph 1.0+, FastAPI 0.121 (002-deepagents-integration)
- PostgreSQL 15 on port 5433 (existing, no schema changes needed) (002-deepagents-integration)
- Python 3.11+ + LangGraph 1.0+, LangChain Core 1.1+, FastAPI 0.121, Typer (CLI) (003-impact-analysis-testing)
- PostgreSQL 15 (existing, port 5433) (003-impact-analysis-testing)

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
- 003-impact-analysis-testing: Added Python 3.11+ + LangGraph 1.0+, LangChain Core 1.1+, FastAPI 0.121, Typer (CLI)
- 002-deepagents-integration: Added Python 3.11+ (already required by DeepAgents 0.2.7) + DeepAgents 0.2.7, LangChain Core 1.1+, LangGraph 1.0+, FastAPI 0.121

- 001-testboost-core: Added Python 3.11+

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
