# TestBoost Development Guidelines

AI-powered Java/Spring Boot test generation and maintenance automation platform.

**Last Updated:** 2025-11-30

## Project Overview

TestBoost automates Java project maintenance through AI-powered LangGraph workflows:
- **Maven Dependency Management**: Automated dependency analysis and updates
- **Test Generation**: Unit, integration, and mutation testing with PIT
- **Docker Deployment**: Containerization and deployment automation
- **Session Tracking**: Pause/resume workflows with PostgreSQL persistence

## Technology Stack

| Category | Technology |
|----------|------------|
| Language | Python 3.11+ |
| API Framework | FastAPI 0.121+ with Uvicorn |
| CLI Framework | Typer with Rich terminal UI |
| Database | PostgreSQL 15+ with SQLAlchemy 2.0 + Alembic |
| Workflows | LangGraph 1.0 for state machines |
| Agents | DeepAgents with YAML configuration |
| Tools | MCP (Model Context Protocol) servers |
| LLM Providers | Anthropic, Google Gemini, OpenAI |
| Logging | Structlog (JSON structured logs) |
| Observability | LangSmith tracing (optional) |

## Project Structure

```text
TestBoost/
├── src/
│   ├── api/                    # FastAPI REST API
│   │   ├── main.py            # App initialization, middleware, routers
│   │   ├── middleware/        # Auth, logging, error handling
│   │   ├── models/            # Pydantic request/response models
│   │   └── routers/           # API route handlers (health, sessions)
│   │
│   ├── cli/                    # Typer CLI application
│   │   ├── main.py            # CLI entry point and commands
│   │   ├── commands/          # Subcommands (maintenance, tests, deploy, audit)
│   │   ├── exit_codes.py      # Standard exit codes
│   │   └── progress.py        # ASCII progress indicators
│   │
│   ├── core/                   # Core business logic
│   │   ├── events.py          # Event system
│   │   ├── locking.py         # Project lock management
│   │   ├── session.py         # Session management
│   │   └── workflow.py        # Workflow orchestration
│   │
│   ├── db/                     # Database layer
│   │   ├── base.py            # SQLAlchemy Base
│   │   ├── repository.py      # Data access patterns
│   │   ├── models/            # SQLAlchemy ORM models
│   │   │   ├── session.py     # Workflow sessions
│   │   │   ├── step.py        # Workflow steps
│   │   │   ├── event.py       # Event log
│   │   │   ├── artifact.py    # Build artifacts
│   │   │   ├── project.py     # Maven projects
│   │   │   ├── dependency.py  # Maven dependencies
│   │   │   ├── modification.py # Code changes
│   │   │   └── project_lock.py # Concurrent execution locks
│   │   ├── migrations/        # Alembic migrations
│   │   └── jobs/              # Background jobs (purge, etc.)
│   │
│   ├── workflows/              # LangGraph workflow definitions
│   │   ├── state.py           # Base state TypedDicts
│   │   ├── maven_maintenance.py
│   │   ├── test_generation.py
│   │   └── docker_deployment.py
│   │
│   ├── agents/                 # DeepAgents integration
│   │   ├── loader.py          # YAML config loader
│   │   └── adapter.py         # LLM adapter
│   │
│   └── mcp_servers/            # MCP tool servers
│       ├── maven_maintenance/ # Maven analysis & build tools
│       ├── test_generator/    # Test generation tools
│       ├── git_maintenance/   # Git operations (branch, commit, status)
│       ├── docker/            # Docker/Compose tools
│       ├── container_runtime/ # Container execution tools
│       └── pit_recommendations/ # Mutation testing tools
│
├── config/
│   ├── agents/                 # DeepAgents YAML configurations
│   │   ├── maven_maintenance_agent.yaml
│   │   ├── test_gen_agent.yaml
│   │   └── deployment_agent.yaml
│   └── prompts/                # LLM prompt templates
│       ├── common/            # Shared prompts (java_expert.md)
│       ├── maven/             # Maven-specific prompts
│       ├── testing/           # Test generation strategies
│       └── deployment/        # Docker guidelines
│
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   ├── api/                    # API endpoint tests
│   └── contract/               # Contract tests
│
├── specs/                      # Feature specifications
│   └── 001-testboost-core/    # Core feature spec
│
├── .specify/                   # Speckit templates and memory
├── .claude/                    # Claude Code configuration
│   ├── commands/              # Custom slash commands
│   └── settings.local.json    # Local settings
│
├── pyproject.toml              # Poetry dependencies & tool configs
├── alembic.ini                 # Database migration config
├── docker-compose.yaml         # Local development stack
├── .env.example                # Environment template
└── README.md                   # User documentation
```

## Development Commands

### Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install poetry
poetry install

# Configure environment
cp .env.example .env
# Edit .env with your API keys and database URL
```

### Database

```bash
# Start PostgreSQL (uses port 5433)
docker-compose up -d postgres

# Run migrations
alembic upgrade head

# Create new migration
alembic revision --autogenerate -m "Description"

# Rollback one migration
alembic downgrade -1
```

### Running the Application

```bash
# Start API server
uvicorn src.api.main:app --reload

# Or via CLI
python -m src.cli.main serve --reload

# CLI commands
python -m src.cli.main --help
python -m src.cli.main maintenance list /path/to/project
python -m src.cli.main tests generate /path/to/project
python -m src.cli.main deploy run /path/to/project
```

### Testing

```bash
# Run all tests with coverage
pytest tests/

# Run specific test file
pytest tests/unit/test_specific.py

# Run with verbose output
pytest -v tests/

# Coverage report
pytest --cov=src --cov-report=html tests/
```

### Code Quality

```bash
# Lint with ruff
ruff check src/

# Auto-fix lint issues
ruff check --fix src/

# Format with black
black src/

# Type checking
mypy src/
```

### Quick Check (All at Once)

```bash
cd src && pytest && ruff check . && black --check .
```

## Code Conventions

### Python Style

- **Python 3.11+** features encouraged (type hints, `|` union syntax, match statements)
- **Line length**: 100 characters (configured in pyproject.toml)
- **Imports**: Sorted by ruff (isort rules), first-party under `src`
- **Type hints**: Required for all function signatures
- **Docstrings**: Google style for public functions/classes

### SQLAlchemy Models

```python
from sqlalchemy.orm import Mapped, mapped_column
from src.db.base import Base

class MyModel(Base):
    __tablename__ = "my_models"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

### Pydantic Models

```python
from pydantic import BaseModel, Field

class MyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    optional_field: str | None = None
```

### Logging

```python
from src.lib.logging import get_logger

logger = get_logger(__name__)

# Structured logging with key-value pairs
logger.info("operation_name", key1=value1, key2=value2)
logger.error("error_occurred", error=str(exc), context=ctx)
```

### Workflow State

Workflows use TypedDict for state management:

```python
from src.workflows.state import WorkflowState, create_initial_state

# Create initial state
state = create_initial_state(
    session_id=uuid.uuid4(),
    project_path="/path/to/project",
    mode="interactive"
)

# Check execution mode
if is_autonomous_mode(state):
    # Auto-approve actions
    pass
```

### MCP Tools

Tools are organized under `src/mcp_servers/{server_name}/tools/`:

```python
# Each tool is a separate file with a main function
async def analyze_dependencies(project_path: str) -> dict:
    """Analyze Maven dependencies for updates."""
    # Implementation
    pass
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `API_KEY` | API authentication key | Required |
| `API_HOST` | API server host | `0.0.0.0` |
| `API_PORT` | API server port | `8000` |
| `MODEL` | Default LLM model | `google-genai/gemini-2.5-flash-preview-09-2025` |
| `GOOGLE_API_KEY` | Google AI API key | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key | Optional |
| `OPENAI_API_KEY` | OpenAI API key | Optional |
| `LANGSMITH_API_KEY` | LangSmith tracing | Optional |
| `LOG_LEVEL` | Logging level | `INFO` |
| `DEBUG` | Debug mode | `false` |

### Agent Configuration

Agents are configured in `config/agents/*.yaml` with:
- Identity (role, goal, backstory)
- LLM settings (model, temperature, max_tokens)
- Available tools (MCP server connections)
- Workflow steps with timeouts
- Error handling and retry policies

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check with DB status |
| POST | `/api/v2/sessions` | Create workflow session |
| GET | `/api/v2/sessions` | List sessions (paginated) |
| GET | `/api/v2/sessions/{id}` | Get session details |
| PATCH | `/api/v2/sessions/{id}` | Update session |
| DELETE | `/api/v2/sessions/{id}` | Delete session |
| POST | `/api/v2/sessions/{id}/pause` | Pause workflow |
| POST | `/api/v2/sessions/{id}/resume` | Resume workflow |
| GET | `/api/v2/sessions/{id}/steps` | List workflow steps |
| POST | `/api/v2/sessions/{id}/steps/{code}/execute` | Execute step |
| GET | `/api/v2/sessions/{id}/artifacts` | List artifacts |

## Session Modes

| Mode | Behavior |
|------|----------|
| `interactive` | Prompts for user approval on modifications |
| `autonomous` | Auto-approves all actions |
| `analysis_only` | Read-only, no modifications allowed |
| `debug` | Verbose logging with debug traces |

## Database Schema

8 core tables managed by Alembic migrations:

- **sessions**: Workflow execution sessions
- **steps**: Individual workflow steps
- **events**: Session event log
- **artifacts**: Build outputs and reports
- **projects**: Maven project metadata
- **dependencies**: Maven dependency tracking
- **modifications**: Code change tracking
- **project_locks**: Concurrent execution prevention

## Known Issues

1. **Maven Required**: Maven must be in PATH for dependency analysis
2. **PostgreSQL Port**: Uses port 5433 (not default 5432)
3. **LangSmith**: Tracing requires valid API key (optional)
4. **`src.lib` imports**: Code references `src.lib.logging` and `src.lib.config` which need to be implemented or adjusted

## Troubleshooting

### PostgreSQL Connection

```bash
# Check if running
docker-compose ps

# View logs
docker-compose logs postgres

# Restart
docker-compose restart postgres
```

### Unicode/Encoding Errors

```bash
export PYTHONIOENCODING=utf-8
export LANG=en_US.UTF-8
```

### Import Errors

Ensure you're running from the project root with PYTHONPATH set:

```bash
export PYTHONPATH=/home/user/TestBoost
python -m src.cli.main --help
```

## Contributing

1. Create a feature branch from main
2. Make changes with tests
3. Run code quality checks: `ruff check . && black --check . && mypy src/`
4. Run tests: `pytest tests/`
5. Submit a pull request

## Version

- **Version**: 0.1.0
- **Status**: Beta
