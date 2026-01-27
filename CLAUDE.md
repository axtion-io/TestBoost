# TestBoost Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-26

## Active Technologies
- Python 3.11+
- FastAPI 0.121+ for REST API
- SQLAlchemy 2.x (async) + PostgreSQL 15 (port 5433)
- LangGraph 1.0+ and LangChain Core 1.1+ for AI workflows
- DeepAgents 0.2.7+ for LLM integration
- Pydantic for data validation
- structlog for structured logging
- pytest, pytest-asyncio, pytest-cov for testing
- Typer for CLI interface

## Project Structure

```text
backend/
frontend/
tests/
```

## Commands

cd src; pytest; ruff check .

## Code Style

- Follow PEP 8 conventions (100 character line length)
- Use type hints for all function signatures
- Use async/await for I/O operations
- Use structlog for structured logging (no print statements)
- Follow Conventional Commits format for commit messages

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:
- Development setup
- Coding standards
- Testing requirements
- Pull request process

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
