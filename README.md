# TestBoost

AI-powered Java/Spring Boot test generation and maintenance automation platform.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.121-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-1.0-purple.svg)](https://langchain.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-blue.svg)](https://postgresql.org)

## Overview

TestBoost automates Java/Spring Boot project maintenance through AI-powered workflows:
- **Maven Dependency Management**: Automated updates with intelligent validation
- **Test Generation**: Unit, integration, and snapshot tests with PIT mutation testing
- **Docker Deployment**: Automated containerization and deployment
- **Workflow Tracking**: Session-based execution with pause/resume capabilities

## Features

### 🔧 Maven Maintenance
- Dependency analysis and update recommendations
- Security vulnerability scanning
- Automated test validation before updates
- Git branch management for safe updates

### 🧪 Test Generation
- Unit tests with Mockito and JUnit 5
- Integration tests for REST APIs, repositories, and services
- Snapshot tests for data validation
- Mutation testing with PIT for test quality assessment
- Killer test generation for surviving mutants

### 🐳 Docker Deployment
- Automatic Dockerfile generation
- Docker Compose orchestration
- Multi-service deployment support
- Health check integration

### 📊 Observability
- Structured JSON logging with structlog
- LangSmith integration for workflow tracing
- Session-based event tracking
- Artifact storage for build outputs

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ or Docker
- Maven 3.6+ (for Java project analysis)
- Git

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd TestBoost
```

2. **Set up Python environment**
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start PostgreSQL**
```bash
docker-compose up -d postgres
```

5. **Run database migrations**
```bash
alembic upgrade head
```

6. **Start the API server**
```bash
uvicorn src.api.main:app --reload
```

Access the API documentation at http://localhost:8000/docs

### CLI Usage

**Configuration Management:**
```bash
# Validate agent configurations
python -m src.cli.main config validate

# Validate specific agent
python -m src.cli.main config validate --agent maven_maintenance_agent

# Show agent configuration
python -m src.cli.main config show maven_maintenance_agent

# Backup configuration
python -m src.cli.main config backup maven_maintenance_agent

# Rollback to latest backup
python -m src.cli.main config rollback maven_maintenance_agent

# Reload configurations (hot-reload)
python -m src.cli.main config reload --all
```

**Analyze dependencies:**
```bash
python -m src.cli.main maintenance list /path/to/maven/project
```

**Run maintenance workflow:**
```bash
python -m src.cli.main maintenance run /path/to/maven/project --mode autonomous
```

**Generate tests:**
```bash
python -m src.cli.main tests generate /path/to/maven/project
```

**Deploy with Docker:**
```bash
python -m src.cli.main deploy run /path/to/maven/project
```

## Architecture

### Components

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
├── config/               # Agent & prompt configurations
├── tests/                # Test suite
└── test-projects/        # Sample Java projects
```

### Technology Stack

- **Backend**: Python 3.11+, FastAPI, Uvicorn
- **Database**: PostgreSQL 15 with Alembic migrations
- **Workflows**: LangGraph 1.0 for state machines
- **Agents**: DeepAgents 0.2.8 with YAML configuration
- **LLM Providers**: Google Gemini, Anthropic Claude, OpenAI GPT
- **Tools**: MCP (Model Context Protocol) servers
- **CLI**: Typer with Rich for terminal UI
- **Logging**: Structlog for structured JSON logs
- **Observability**: LangSmith tracing integration

### Database Schema

8 core tables:
- `projects`: Maven project metadata
- `sessions`: Workflow execution sessions
- `steps`: Individual workflow steps
- `events`: Session event log
- `artifacts`: Build outputs and reports
- `dependencies`: Maven dependency tracking
- `modifications`: Code change tracking
- `project_locks`: Concurrent execution prevention

## API Endpoints

### Health
- `GET /health` - Health check with database status

### Sessions
- `POST /api/v2/sessions` - Create new workflow session
- `GET /api/v2/sessions` - List sessions (with pagination)
- `GET /api/v2/sessions/{id}` - Get session details
- `PATCH /api/v2/sessions/{id}` - Update session
- `DELETE /api/v2/sessions/{id}` - Delete session
- `POST /api/v2/sessions/{id}/pause` - Pause execution
- `POST /api/v2/sessions/{id}/resume` - Resume execution

### Steps
- `GET /api/v2/sessions/{id}/steps` - List workflow steps
- `GET /api/v2/sessions/{id}/steps/{code}` - Get step details
- `POST /api/v2/sessions/{id}/steps/{code}/execute` - Execute step

### Artifacts
- `GET /api/v2/sessions/{id}/artifacts` - List session artifacts

## Configuration

### Environment Variables

See `.env.example` for all configuration options:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://testboost:testboost@localhost:5433/testboost

# API
API_KEY=your-api-key-here
API_HOST=0.0.0.0
API_PORT=8000

# LLM Providers
MODEL=google-genai/gemini-2.5-flash-preview-09-2025
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key

# LangSmith (optional)
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=testboost
LANGSMITH_TRACING=true
```

### Agent Configuration

Agent behaviors are configured in `config/agents/*.yaml` using DeepAgents 0.2.8 format:

```yaml
name: maven_maintenance_agent
description: Handles Maven dependency updates and security fixes

identity:
  role: Maven Dependency Maintenance Expert
  persona: Technical advisor for Java/Spring Boot projects

llm:
  provider: google-genai
  model: gemini-2.5-flash-preview-09-2025
  temperature: 0.1
  max_tokens: 4096

tools:
  mcp_servers:
    - maven_maintenance
    - container_runtime

prompts:
  system: config/prompts/maven/system.md

workflow:
  graph_name: maven_maintenance_workflow
  node_name: agent_node

error_handling:
  max_retries: 3
  timeout_seconds: 300
```

Available agents:
- `maven_maintenance_agent.yaml` - Dependency update logic
- `test_gen_agent.yaml` - Test generation strategies
- `deployment_agent.yaml` - Docker deployment rules

**Configuration Management Features:**
- **Hot-reload**: Changes detected automatically via file modification time tracking
- **Validation**: 7-layer validation (YAML syntax, schema, MCP servers, prompts, LLM provider, parameters)
- **Backup/Rollback**: Timestamped backups with one-command rollback
- **CLI Integration**: Complete configuration management via `config` command group

Prompt templates are in `config/prompts/`:
- `common/java_expert.md` - Java/Spring Boot expertise
- `maven/dependency_update.md` - Update decision guidelines
- `testing/*.md` - Test generation strategies
- `deployment/docker_guidelines.md` - Containerization rules

## Development

### Running Tests

```bash
pytest tests/
```

### Code Quality

```bash
# Linting
ruff check src/

# Formatting
black src/

# Type checking
mypy src/
```

### Database Migrations

```bash
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## Known Issues

1. **Maven Tool Requirement**: Maven must be in PATH for dependency analysis
2. **Windows Compatibility**: Tested on Windows 11 with Git Bash
3. **LangSmith**: Tracing requires valid API key (optional feature)

## Troubleshooting

### PostgreSQL Connection Error
```bash
# Check if PostgreSQL is running
docker-compose ps

# Restart PostgreSQL
docker-compose restart postgres
```

### CLI Unicode Errors
The CLI uses ASCII-safe progress indicators. If you still see encoding errors:
```bash
# Set environment variables
export PYTHONIOENCODING=utf-8
export LANG=en_US.UTF-8
```

### LangGraph Recursion Limit
Workflow now includes automatic termination conditions. If you encounter recursion errors, check that your project has valid Maven configuration.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run code quality checks
5. Submit a pull request

## License

[Your License Here]

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com)
- [LangChain](https://langchain.com) & [LangGraph](https://langchain.com)
- [DeepAgents](https://github.com/anthropics/deepagents)
- [Typer](https://typer.tiangolo.com)
- [Rich](https://rich.readthedocs.io)
- [SQLAlchemy](https://sqlalchemy.org)
- [Alembic](https://alembic.sqlalchemy.org)

---

**Version**: 0.2.0
**Status**: Beta - DeepAgents integration complete with config management
**Last Updated**: 2025-11-30
