# TestBoost

AI-powered Java/Spring Boot test generation and maintenance automation platform.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0-purple.svg)](https://langchain.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://postgresql.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

## Overview

TestBoost automates Java/Spring Boot project maintenance through AI-powered workflows:

- **Maven Dependency Management** - Automated updates with security scanning and non-regression validation
- **Test Generation** - Unit, integration, and snapshot tests with mutation testing (PIT)
- **Docker Deployment** - Automated containerization with health check monitoring
- **Impact Analysis** - Code change analysis to identify required tests

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or Docker)
- Git
- LLM API key (Google Gemini, Anthropic Claude, or OpenAI)

### Installation

```bash
# Clone and install
git clone https://github.com/axtion-io/TestBoost.git
cd TestBoost
pip install poetry && poetry install

# Configure environment
cp .env.example .env
# Edit .env with your LLM API key (GOOGLE_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY)

# Start database and run migrations
docker compose up -d postgres
alembic upgrade head

# Start the API
uvicorn src.api.main:app --reload
```

### CLI Usage

```bash
# Maven maintenance
python -m src.cli.main maintenance list ./my-project
python -m src.cli.main maintenance run ./my-project --mode autonomous

# Test generation
python -m src.cli.main tests generate ./my-project

# Docker deployment
python -m src.cli.main deploy run ./my-project

# Configuration management
python -m src.cli.main config validate
```

## Documentation

Full documentation is available in the [`docs/`](./docs/) directory:

| Document | Description |
|----------|-------------|
| [User Guide](./docs/user-guide.md) | Complete installation and usage guide |
| [CLI Reference](./docs/cli-reference.md) | Full CLI commands documentation |
| [API Authentication](./docs/api-authentication.md) | REST API endpoints and authentication |
| [LLM Providers](./docs/llm-providers.md) | Configure Google Gemini, Claude, or OpenAI |
| [Database Schema](./docs/database-schema.md) | PostgreSQL tables and migrations |
| [Documentation Index](./docs/README.md) | Full documentation table of contents |

## Architecture

```
TestBoost/
├── src/
│   ├── api/              # FastAPI REST API
│   ├── cli/              # Typer CLI commands
│   ├── core/             # Core business logic
│   ├── db/               # Database models & migrations
│   ├── workflows/        # LangGraph workflows
│   ├── agents/           # DeepAgents configurations
│   └── mcp_servers/      # MCP tool servers
├── config/               # Agent YAML & prompt configurations
├── docs/                 # Documentation
├── specs/                # Feature specifications (SpecKit)
└── tests/                # Test suite
```

### Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | PostgreSQL 15, SQLAlchemy, Alembic |
| Workflows | LangGraph 1.0+ |
| Agents | DeepAgents 0.2.8, LangChain Core 1.1+ |
| LLM Providers | Google Gemini, Anthropic Claude, OpenAI |
| CLI | Typer, Rich |
| Observability | Structlog, LangSmith (optional) |

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check with database and LLM status |
| `POST /api/v2/sessions` | Create workflow session |
| `GET /api/v2/sessions` | List sessions (paginated) |
| `GET /api/v2/sessions/{id}` | Get session details |
| `POST /api/v2/sessions/{id}/pause` | Pause workflow |
| `POST /api/v2/sessions/{id}/resume` | Resume workflow |

See [API Authentication](./docs/api-authentication.md) for full endpoint documentation.

## Development

```bash
# Run tests
pytest tests/

# Linting
ruff check src/

# Type checking
mypy src/
```

## Edge Cases & Error Handling

TestBoost handles common edge cases automatically:

| Scenario | Behavior |
|----------|----------|
| **LLM Rate Limit (429)** | Automatic retry with exponential backoff (max 3 attempts) |
| **LLM Timeout** | Configurable timeout (default 120s), retry on transient failures |
| **Invalid API Key** | Startup validation fails with clear error message |
| **Network Errors** | Automatic retry with backoff for transient failures |
| **Malformed LLM Response** | Retry with modified prompt (max 3 attempts) |

For detailed edge case handling, see [LLM Providers](./docs/llm-providers.md#gestion-des-erreurs).

## Troubleshooting

### Common Issues

**LLM not available at startup**
```
Error: LLM not available: GOOGLE_API_KEY not configured
```
Solution: Set your LLM API key in `.env` file.

**Database connection failed**
```
Error: Connection refused on port 5433
```
Solution: Start PostgreSQL with `docker compose up -d postgres`.

**Tests not found (collected 0 items)**
- Verify test files match pattern `test_*.py`
- Check pytest configuration in `pyproject.toml`

**Rate limit exceeded**
```
LLM rate limit exceeded. Retry after 60 seconds.
```
Solution: Wait for the indicated duration or switch to a provider with higher quota.

For more troubleshooting help, see [Operations Guide](./docs/operations.md).

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks
5. Submit a pull request

See [CONTRIBUTING.md](./CONTRIBUTING.md) for detailed guidelines.

## License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

Built with [FastAPI](https://fastapi.tiangolo.com), [LangChain](https://langchain.com), [LangGraph](https://langchain.com), [DeepAgents](https://github.com/anthropics/deepagents), [Typer](https://typer.tiangolo.com), and [Rich](https://rich.readthedocs.io).

---

**Version**: 0.2.0
