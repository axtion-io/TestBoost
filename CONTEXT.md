# TestBoost - Project Context for Cursor

## Overview

**TestBoost** is an LLM-powered automation tool for Java/Spring Boot project maintenance. It automates dependency updates, test generation, and Docker deployment while ensuring zero regression through comprehensive testing.

**Repository**: https://github.com/axtion-io/TestBoost
**Current Branch**: `001-testboost-core`
**Status**: Core implementation complete

---

## Architecture

### Core Stack
| Component | Technology |
|-----------|------------|
| Language | Python 3.11+ |
| API | FastAPI 0.121 (port 8000) |
| CLI | Typer + Rich |
| Orchestration | LangGraph 1.0 |
| Agents | DeepAgents 0.2.7 (YAML configs) |
| Database | PostgreSQL 15 (port 5433) |
| LLM | Gemini 2.0 Flash (default), Claude, GPT-4o |

### LLM Configuration
```yaml
# config/agents/maven_maintenance_agent.yaml
llm:
  provider: google-genai
  model: gemini-2.0-flash
  temperature: 0.3
  max_tokens: 8192
```

Supported providers:
- `google-genai` - Gemini models (default, 1500 req/day free)
- `anthropic` - Claude models
- `openai` - GPT-4o models

---

## Project Structure

```
src/
├── api/                    # FastAPI REST API
│   ├── main.py            # App entry, middleware, health check
│   └── routers/           # v2 endpoints (sessions, steps, artifacts)
├── cli/                   # Typer CLI
│   └── commands/          # maintenance, tests, deploy, audit
├── core/                  # Business logic
│   ├── events.py          # Event sourcing
│   ├── locking.py         # Project locks
│   └── session.py         # Session management
├── db/                    # Database layer
│   ├── models/            # 8 SQLAlchemy models
│   └── repository.py      # CRUD repositories
├── workflows/             # LangGraph workflows (ACTIVE)
│   ├── maven_maintenance_agent.py   # Maven updates
│   ├── test_generation_agent.py     # Test generation
│   ├── docker_deployment_agent.py   # Docker deploy
│   ├── impact_analysis.py           # Git diff analysis
│   └── state.py                     # Shared state
├── mcp_servers/           # MCP tool servers
│   ├── maven_maintenance/
│   ├── git_maintenance/
│   ├── test_generator/
│   │   └── tools/
│   │       └── generate_unit.py     # Test generation logic
│   ├── docker/
│   └── container_runtime/
├── agents/                # DeepAgents
│   ├── loader.py          # YAML config loader
│   └── adapter.py         # LangGraph adapter
├── models/                # Pydantic models
│   └── impact.py          # ImpactedFile, TestRequirement
└── lib/                   # Shared utilities
    ├── config.py          # Pydantic settings
    ├── llm.py             # Multi-provider LLM factory
    └── logging.py         # Structlog JSON logging

config/
├── agents/                # Agent YAML configs
│   ├── maven_maintenance_agent.yaml
│   ├── test_gen_agent.yaml
│   └── deployment_agent.yaml
└── prompts/               # Markdown prompt templates
    ├── common/java_expert.md
    ├── maven/dependency_update.md
    └── testing/unit_test_strategy.md

specs/001-testboost-core/  # Feature specifications
├── spec.md                # Requirements (FR-001 to FR-052)
├── tasks.md               # Tasks (T001 to T154)
├── plan.md                # Architecture decisions
└── data-model.md          # Database schema

test-projects/             # Java test projects
├── java-maven-junit-helloworld/
├── spring-petclinic-reactjs/
└── spring-petclinic-microservices/
```

---

## Test Generation (Key Feature)

### Two Modes

**LLM Mode** (default, for production):
```python
# Uses LLM to generate intelligent, context-aware tests
await run_test_generation_with_agent(
    session_id=uuid,
    project_path="/path/to/java/project",
    use_llm=True  # Default
)
```

**Template Mode** (for CI without LLM):
```python
# Uses templates, no API keys needed
await run_test_generation_with_agent(
    session_id=uuid,
    project_path="/path/to/java/project",
    use_llm=False  # Template-based
)
```

### Key Functions

| File | Function | Purpose |
|------|----------|---------|
| `test_generation_agent.py` | `run_test_generation_with_agent()` | Main entry point |
| `test_generation_agent.py` | `_find_source_files()` | Discover testable Java files |
| `test_generation_agent.py` | `_generate_tests_directly()` | Call generator per file |
| `generate_unit.py` | `generate_adaptive_tests()` | Generate test code |
| `generate_unit.py` | `_generate_test_code_with_llm()` | LLM prompt handling |
| `generate_unit.py` | `_generate_test_code()` | Template-based fallback |

### Fallback Behavior
If LLM fails (timeout, quota, error), automatically falls back to template generation.

---

## Constitution Principles (Non-Negotiable)

1. **Zero Complaisance** - Never fake results or logs
2. **MCP Only** - All tools via MCP protocol
3. **No Mocks in Production** - Real services for user testing
4. **User Control** - Interactive/autonomous modes
5. **Full Traceability** - Immutable event log
6. **Validate Before Modify** - Backups, checks first
7. **Isolation** - Dedicated branches, atomic commits
8. **Modularity** - Independent, interchangeable components
9. **Transparency** - Clear error messages, justifications
10. **Robustness** - Graceful degradation, retries
11. **Performance** - <5s interactive, <5min deployments
12. **Standards** - Respect target project conventions
13. **Simplicity** - Minimal configuration to start

---

## Commands

```bash
# Start API
uvicorn src.api.main:app --reload

# CLI commands
python -m src.cli.main maintenance <project_path>
python -m src.cli.main tests generate <project_path>
python -m src.cli.main deploy <project_path>
python -m src.cli.main audit <session_id>

# Run tests
poetry run pytest tests/ -v

# Linting
poetry run ruff check src/
```

---

## Environment Variables

```env
# Database (PostgreSQL on port 5433)
DATABASE_URL=postgresql+asyncpg://testboost:testboost@localhost:5433/testboost

# LLM Provider (choose one)
MODEL=gemini-2.0-flash
GOOGLE_API_KEY=your-google-api-key

# Alternative providers
# MODEL=claude-sonnet-4-20250514
# ANTHROPIC_API_KEY=your-anthropic-key

# MODEL=gpt-4o
# OPENAI_API_KEY=your-openai-key

# Observability (optional)
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=testboost

# API Authentication
API_KEY=your-api-key
```

---

## Database Models

| Model | Purpose |
|-------|---------|
| Session | Workflow execution instance |
| Step | Atomic workflow step |
| Event | Immutable action log |
| Artifact | Generated files/reports |
| Project | Target Java project metadata |
| ProjectLock | Exclusive project access |
| Dependency | Maven dependency info |
| Modification | File change record |

---

## GitHub Actions

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | push/PR to main, 001, 002, 003 | Run pytest, ruff, mypy |
| `impact-check.yml` | Java file changes | Analyze code impact |

---

## Development Notes

1. **Windows**: CLI uses ASCII-safe progress (no Unicode issues)
2. **PostgreSQL**: Port 5433 (not default 5432)
3. **LangGraph**: Recursion limit 25 iterations
4. **Test Generation**:
   - Production: `use_llm=True` (LLM-powered)
   - CI: `use_llm=False` (templates, no API keys)
5. **Java Records**: Special constructor handling
6. **Reactive Types**: StepVerifier for Mono/Flux
7. **LLM Fallback**: Auto-fallback to templates on failure

---

## Quick Reference

### Run Test Generation (Production)
```python
from src.workflows.test_generation_agent import run_test_generation_with_agent

result = await run_test_generation_with_agent(
    session_id=uuid4(),
    project_path="test-projects/spring-petclinic-microservices",
    db_session=async_session,
    use_llm=True,  # Uses LLM
)
```

### Run Test Generation (CI - No LLM)
```python
result = await run_test_generation_with_agent(
    session_id=uuid4(),
    project_path="test-projects/spring-petclinic-microservices",
    db_session=async_session,
    use_llm=False,  # Templates only
)
```

### Generate Tests for Single File
```python
from src.mcp_servers.test_generator.tools.generate_unit import generate_adaptive_tests

result = await generate_adaptive_tests(
    project_path="/path/to/project",
    source_file="src/main/java/com/example/MyService.java",
    use_llm=True,  # or False for templates
)
```
