# TestBoost - Project Context

## Overview

**TestBoost** is an LLM-powered automation tool for Java/Spring Boot project maintenance. It automates dependency updates, test generation, and Docker deployment while ensuring zero regression through comprehensive testing.

**Repository**: https://github.com/cheche71/TestBoost
**Main Branch**: `001-testboost-core`
**Status**: Implementation complete, feature branches in development

---

## Architecture

### Core Stack
- **Language**: Python 3.11+
- **API**: FastAPI 0.121 (port 8000)
- **CLI**: Typer + Rich
- **Orchestration**: LangGraph 1.0 (state machine workflows)
- **Agents**: DeepAgents 0.2.7 (YAML-configured LLM agents)
- **Database**: PostgreSQL 15 (port 5433, asyncpg + SQLAlchemy 2.0)
- **LLM Providers**: Gemini (default), Claude, GPT-4o (configurable via MODEL env var)

### Key Patterns
1. **MCP Protocol**: All tools exposed via Model Context Protocol servers
2. **LangGraph Workflows**: State machine-based orchestration with pause/resume
3. **Event Sourcing**: Immutable event log for all actions
4. **Repository Pattern**: SQLAlchemy models with async CRUD

---

## Project Structure

```
src/
├── api/                    # FastAPI REST API
│   ├── main.py            # App instance, middleware, health check
│   ├── dependencies.py    # DI for database, auth
│   └── routers/           # v2 endpoints (sessions, steps, artifacts)
├── cli/                   # Typer CLI
│   ├── main.py           # CLI entry point
│   └── commands/         # maintenance, tests, deploy, audit
├── core/                  # Business logic
│   ├── events.py         # Event sourcing service
│   ├── locking.py        # Project lock service
│   ├── session.py        # Session management
│   └── workflow.py       # LangGraph workflow executor
├── db/                    # Database layer
│   ├── models/           # 8 SQLAlchemy models
│   ├── repository.py     # CRUD repositories
│   └── migrations/       # Alembic migrations
├── workflows/            # LangGraph workflows
│   ├── maven_maintenance_agent.py  # Maven dependency update workflow
│   ├── test_generation_agent.py    # Test generation (LLM or template mode)
│   ├── docker_deployment_agent.py  # Docker deployment workflow
│   ├── impact_analysis.py          # Git diff impact analysis
│   └── state.py                    # Shared workflow state
├── mcp_servers/          # MCP tool servers
│   ├── maven_maintenance/
│   ├── git_maintenance/
│   ├── test_generator/   # Test generation tools
│   │   └── tools/
│   │       └── generate_unit.py  # Main test generation logic
│   ├── docker/
│   └── container_runtime/
├── agents/               # DeepAgents configuration
│   ├── loader.py        # YAML config loader
│   └── adapter.py       # LangGraph adapter
├── models/              # Pydantic models
│   └── impact.py        # Impact analysis models
└── lib/                 # Shared utilities
    ├── config.py        # Pydantic settings
    ├── llm.py           # Multi-provider LLM factory
    └── logging.py       # Structlog JSON logging

config/
├── agents/              # DeepAgents YAML configs
└── prompts/             # Markdown prompt templates

specs/                   # Feature specifications
├── 001-testboost-core/  # Core feature (complete)
├── 002-deepagents-integration/
└── 003-impact-analysis-testing/  # Current development

test-projects/           # Java test projects (gitignored)
├── java-maven-junit-helloworld/
├── spring-petclinic-reactjs/
└── spring-petclinic-microservices/  # Multi-module Spring project
```

---

## Key Files

### Test Generation (Two Modes)

**LLM Mode** (default, for production):
```python
run_test_generation_with_agent(use_llm=True)  # Uses LLM for intelligent tests
```

**Template Mode** (for CI without LLM):
```python
run_test_generation_with_agent(use_llm=False)  # Uses templates, no API keys needed
```

- `src/workflows/test_generation_agent.py` - Main workflow
  - `run_test_generation_with_agent()` - Entry point with `use_llm` parameter
  - `_find_source_files()` - Discovers testable Java files
  - `_generate_tests_directly()` - Calls generator for each source file

- `src/mcp_servers/test_generator/tools/generate_unit.py` - Test code generation
  - `generate_adaptive_tests(use_llm=True)` - LLM-powered intelligent tests
  - `generate_adaptive_tests(use_llm=False)` - Template-based tests (fallback)
  - `_generate_test_code_with_llm()` - LLM prompt and response handling
  - `_generate_test_code()` - Template-based generation
  - Supports: Controllers, Services, Repositories, Components
  - Features: Mockito mocks, Spring injection, reactive types (Mono/Flux)

### Configuration
- `.env.example` - Environment variables template
- `pyproject.toml` - Poetry dependencies
- `docker-compose.yaml` - PostgreSQL service

### Specifications
- `specs/001-testboost-core/spec.md` - Functional requirements (FR-001 to FR-052)
- `specs/001-testboost-core/tasks.md` - Implementation tasks (T001 to T154)
- `specs/001-testboost-core/plan.md` - Architecture decisions
- `.specify/memory/constitution.md` - Non-negotiable principles

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

## Current Development

### Branch: 003-impact-analysis-testing
**Focus**: Impact analysis for code changes and targeted test generation

Key additions:
- `src/models/impact.py` - ImpactedFile, TestRequirement models
- `src/workflows/impact_analysis.py` - Analyze git diff for impact
- `src/lib/diff_chunker.py` - Parse git diffs
- `src/lib/risk_keywords.py` - Identify high-risk patterns

### Recent Changes
1. **LLM-powered test generation** - Intelligent tests using LLM (production mode)
2. **Template fallback** - Template-based generation for CI (no LLM needed)
3. **Deleted deprecated workflows** - Removed docker_deployment.py, maven_maintenance.py, test_generation.py
4. Java record detection and proper constructor generation
5. Mockito stub generation for repositories/mappers
6. Reactive type support (StepVerifier for Mono/Flux)

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

## Environment Variables

```env
# Database
DATABASE_URL=postgresql+asyncpg://testboost:testboost@localhost:5433/testboost

# LLM Provider
MODEL=gemini-2.0-flash  # or claude-sonnet-4-20250514, gpt-4o
GOOGLE_API_KEY=...
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...

# Observability
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=testboost

# API
API_KEY=your-api-key
```

---

## Testing Java Projects

The repository includes 3 test projects in `test-projects/`:

1. **java-maven-junit-helloworld** - Small project (~5 classes)
2. **spring-petclinic-reactjs** - Medium Spring Boot (~50 classes)
3. **spring-petclinic-microservices** - Large multi-module (8+ services)

Generated tests go to `src/test/java/` in each project.

---

## GitHub Actions

- `.github/workflows/ci.yml` - Runs on push/PR to main, develop, 001, 002, 003 branches
- `.github/workflows/impact-check.yml` - Analyzes code impact for Java changes

---

## Notes for Development

1. **Windows Compatibility**: CLI uses ASCII-safe progress (no Unicode)
2. **PostgreSQL Port**: 5433 (not default 5432)
3. **LangGraph Recursion**: Limit 25 iterations to prevent infinite loops
4. **Test Generation Modes**:
   - Production: `use_llm=True` (default) - LLM-powered intelligent tests
   - CI: `use_llm=False` - Template-based, no API keys needed
5. **Java Records**: Special handling for constructor parameters (int, Date, String types)
6. **LLM Fallback**: If LLM fails, automatically falls back to template generation
