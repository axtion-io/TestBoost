# Tasks: TestBoost Core

**Input**: Design documents from `/specs/001-testboost-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Not explicitly requested in spec - test tasks omitted. Add if needed.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US5)
- Include exact file paths in descriptions
- **Validation**: `> ✓` lines show acceptance criteria, `> $` shows test command

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project structure per plan.md in src/
  > ✓ Répertoires api/, cli/, core/, db/, lib/, workflows/, agents/, mcp_servers/ avec __init__.py
  > $ `find src -type d -name "__pycache__" -prune -o -type d -print | wc -l`
- [X] T002 Initialize Python project with Poetry and pyproject.toml using versions from research.md
  > ✓ `poetry install` réussit, .venv/ créé
  > ✓ All dependency versions MUST match research.md exactly (no substitution)
  > $ `poetry check && poetry install --dry-run`
- [X] T002b Validate pyproject.toml versions against research.md
  > ✓ Every dependency in pyproject.toml matches the version specified in research.md
  > ✓ No missing dependencies from research.md (including deepagents)
  > $ Manual verification or diff check
- [X] T003 [P] Configure ruff linter and black formatter in pyproject.toml
  > ✓ Sections [tool.ruff] et [tool.black] présentes
  > $ `ruff check src/ --select=E999`
- [X] T004 [P] Create .env.example with all required environment variables
  > ✓ DATABASE_URL, API keys, LANGSMITH configurés (placeholders)
  > $ `grep -c "^[A-Z_]=" .env.example`
- [X] T005 [P] Create docker-compose.yaml for PostgreSQL and application
  > ✓ Services postgres et testboost définis
  > $ `docker-compose config -q && echo "Valid"`

---

## Phase 1.5: Test Projects Setup

**Purpose**: Prepare reference Java projects for validation testing

**Projects**:
- **Petit**: `LableOrg/java-maven-junit-helloworld` (~5 classes)
- **Moyen**: `spring-petclinic/spring-petclinic-reactjs` (~50 classes, Spring Boot)
- **Gros**: `spring-petclinic/spring-petclinic-microservices` (8+ modules, Docker)

- [X] T005a Clone test repositories into test-projects/
  > ✓ 3 repos clonés avec .git valide
  > $ `ls test-projects/*/pom.xml`
- [X] T005b Verify small project builds (java-maven-junit-helloworld)
  > ✓ `mvn clean verify` réussit, JAR généré
  > $ `cd test-projects/java-maven-junit-helloworld && mvn clean verify -q`
- [X] T005c Verify medium project builds (spring-petclinic-reactjs)
  > ✓ `mvn clean package -DskipTests` réussit
  > $ `cd test-projects/spring-petclinic-reactjs && mvn clean package -DskipTests -q`
- [X] T005d Verify large project builds (spring-petclinic-microservices)
  > ✓ Tous modules compilent, docker-compose valide
  > $ `cd test-projects/spring-petclinic-microservices && mvn clean install -DskipTests -q`
- [X] T005e Launch and validate all test applications
  > ✓ Petit: tests passent, Moyen: health OK port 8080, Gros: services Docker healthy

**Checkpoint**: Test projects ready for validation testing

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database Layer

- [X] T006 Create SQLAlchemy base and session factory in src/db/__init__.py
  > ✓ Exporte Base, SessionLocal, get_db
  > $ `python -c "from src.db import Base, SessionLocal, get_db; print('OK')"`
- [X] T007 [P] Implement Session model in src/db/models/session.py
  > ✓ Tous champs data-model.md, relations steps/events/artifacts
  > $ `python -c "from src.db.models.session import Session; print(Session.__tablename__)"`
- [X] T008 [P] Implement Step model in src/db/models/step.py
  > ✓ FK Session, inputs/outputs JSON, enum status
  > $ `python -c "from src.db.models.step import Step; print(Step.__tablename__)"`
- [X] T009 [P] Implement Event model in src/db/models/event.py
  > ✓ FK Session/Step, event_data JSON, index event_type
  > $ `python -c "from src.db.models.event import Event; print(Event.__tablename__)"`
- [X] T010 [P] Implement Artifact model in src/db/models/artifact.py
  > ✓ FK Session/Step, content_type, file_path, size_bytes
  > $ `python -c "from src.db.models.artifact import Artifact; print(Artifact.__tablename__)"`
- [X] T011 [P] Implement ProjectLock model in src/db/models/project_lock.py
  > ✓ project_path unique, expires_at, FK Session
  > $ `python -c "from src.db.models.project_lock import ProjectLock; print(ProjectLock.__tablename__)"`
- [X] T012 Create Alembic migrations for all models in src/db/migrations/
  > ✓ alembic.ini, migrations/, `alembic upgrade head` réussit
  > $ `alembic check`
- [X] T013 Implement repository pattern in src/db/repository.py
  > ✓ BaseRepository CRUD, SessionRepository, StepRepository
  > $ `python -c "from src.db.repository import SessionRepository; print('OK')"`

### Core Services

- [X] T014 Implement configuration management with Pydantic Settings in src/lib/config.py
  > ✓ Classe Settings, validation, support .env
  > $ `python -c "from src.lib.config import get_settings; print(get_settings().model_dump_json()[:50])"`
- [X] T015 [P] Implement structured JSON logging with structlog in src/lib/logging.py
  > ✓ JSON en prod, coloré en dev, contexte auto
  > $ `python -c "from src.lib.logging import get_logger; get_logger('test').info('ok')"`
- [X] T016 [P] Implement sensitive data masking in src/lib/logging.py (FR-046A)
  > ✓ Masque password, token, api_key, secret
  > $ `pytest tests/lib/test_logging.py::test_sensitive_masking -v`
- [X] T017 Implement event sourcing service in src/core/events.py
  > ✓ emit(), get_events(), persist en DB
  > $ `python -c "from src.core.events import EventService; print('OK')"`
- [X] T018 Implement project lock service in src/core/locking.py
  > ✓ acquire_lock(), release_lock(), is_locked(), cleanup expired
  > $ `python -c "from src.core.locking import LockService; print('OK')"`

### API Foundation

- [X] T019 Create FastAPI app with middleware in src/api/main.py
  > ✓ CORS, request ID middleware, exception handlers, OpenAPI metadata
  > $ `python -c "from src.api.main import app; print(app.title, app.version)"`
- [X] T020 [P] Implement API key authentication middleware in src/api/middleware/auth.py
  > ✓ Vérifie X-API-Key, 401 si invalide, bypass /health et /docs
  > $ `pytest tests/api/test_auth.py -v`
- [X] T021 [P] Implement request logging middleware in src/api/middleware/logging.py
  > ✓ Log method, path, duration, status, request_id
  > $ `pytest tests/api/test_logging_middleware.py -v`
- [X] T022 Implement health check endpoint in src/api/routers/health.py
  > ✓ Vérifie DB, retourne status/version/checks, 503 si unhealthy
  > $ `pytest tests/api/test_health.py -v`
- [X] T023 Create Pydantic schemas for Session/Step/Event in src/api/models/
  > ✓ SessionCreate, SessionResponse, StepResponse, EventResponse
  > $ `python -c "from src.api.models import SessionCreate, SessionResponse; print('OK')"`

### LangGraph Foundation

- [X] T024 Implement LLM provider factory with retry logic (FR-009A) in src/lib/llm.py
  > ✓ Support OpenAI/Anthropic, retry exponential backoff, timeout
  > $ `python -c "from src.lib.llm import get_llm; print(type(get_llm()).__name__)"`
- [X] T025 Create base workflow state schema in src/workflows/state.py
  > ✓ WorkflowState(TypedDict) avec session_id, project_path, mode, current_step
  > $ `python -c "from src.workflows.state import WorkflowState; print(list(WorkflowState.__annotations__.keys())[:3])"`
- [X] T026 Implement workflow executor with LangGraph in src/core/workflow.py
  > ✓ Charge StateGraph, transitions, events, pause/resume checkpoint
  > $ `python -c "from src.core.workflow import WorkflowExecutor; print('OK')"`

### Agent Foundation

- [X] T027 Implement DeepAgents YAML loader in src/agents/loader.py
  > ✓ Parse YAML DeepAgents, valide avec Pydantic
  > $ `python -c "from src.agents.loader import load_agent_config; print('OK')"`
- [X] T028 Implement LangGraph agent adapter in src/agents/adapter.py
  > ✓ Convertit config en node LangGraph, bind tools MCP
  > $ `python -c "from src.agents.adapter import AgentAdapter; print('OK')"`
- [X] T029 [P] Create common Java expert prompt in config/prompts/common/java_expert.md
  > ✓ Expertise Java/Maven/Spring, guidelines modifications
  > $ `test -f config/prompts/common/java_expert.md && wc -l config/prompts/common/java_expert.md`

### CLI Foundation

- [X] T030 Create Typer CLI app structure in src/cli/main.py
  > ✓ App Typer, --version, --help, structure sous-commandes
  > $ `python -m src.cli.main --help`
- [X] T031 Implement CLI exit codes per quickstart.md in src/cli/main.py
  > ✓ 0=succès, 1=erreur, 2=args invalides dans exit_codes.py
  > $ `python -c "from src.cli.exit_codes import SUCCESS, ERROR; print(SUCCESS, ERROR)"`

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Maintenance Maven avec Non-Régression (Priority: P1) 🎯 MVP

**Goal**: Mettre à jour les dépendances Maven automatiquement en garantissant la non-régression

**Independent Test**: Exécuter le workflow sur un projet Maven avec dépendances obsolètes, vérifier tous tests passent après

### MCP Server - Maven Maintenance

- [X] T032 [P] [US1] Create MCP server structure in src/mcp_servers/maven_maintenance/__init__.py
- [X] T033 [US1] Implement analyze-dependencies tool in src/mcp_servers/maven_maintenance/tools/analyze.py
- [X] T034 [P] [US1] Implement compile-tests tool in src/mcp_servers/maven_maintenance/tools/compile.py
- [X] T035 [P] [US1] Implement run-tests tool in src/mcp_servers/maven_maintenance/tools/run_tests.py
- [X] T036 [P] [US1] Implement package tool in src/mcp_servers/maven_maintenance/tools/package.py

### MCP Server - Git Maintenance

- [X] T037 [P] [US1] Create MCP server structure in src/mcp_servers/git_maintenance/__init__.py
- [X] T038 [US1] Implement create-maintenance-branch tool in src/mcp_servers/git_maintenance/tools/branch.py
- [X] T039 [P] [US1] Implement commit-changes tool in src/mcp_servers/git_maintenance/tools/commit.py
- [X] T040 [P] [US1] Implement get-status tool in src/mcp_servers/git_maintenance/tools/status.py

### Data Models for US1

- [X] T041 [P] [US1] Implement Project model in src/db/models/project.py
- [X] T042 [P] [US1] Implement Dependency model in src/db/models/dependency.py
- [X] T043 [P] [US1] Implement Modification model in src/db/models/modification.py
- [X] T044 [US1] Create Alembic migration for US1 models

### Workflow Implementation

- [X] T045 [US1] Create Maven maintenance workflow graph in src/workflows/maven_maintenance.py
- [X] T046 [US1] Implement validate_project step in src/workflows/maven_maintenance.py
- [X] T047 [US1] Implement check_git_status step in src/workflows/maven_maintenance.py
- [X] T048 [US1] Implement analyze_maven step with dependency classification in src/workflows/maven_maintenance.py
- [X] T048b [US1] Implement fetch_release_notes step (FR-012) in src/workflows/maven_maintenance.py
- [X] T049 [US1] Implement run_baseline_tests step in src/workflows/maven_maintenance.py
- [X] T050 [US1] Implement user_validation step (interactive mode) in src/workflows/maven_maintenance.py
- [X] T051 [US1] Implement create_maintenance_branch step in src/workflows/maven_maintenance.py
- [X] T052 [US1] Implement apply_update_batch step with rollback in src/workflows/maven_maintenance.py
- [X] T053 [US1] Implement validate_changes step in src/workflows/maven_maintenance.py
- [X] T054 [US1] Implement commit_changes step in src/workflows/maven_maintenance.py
- [X] T055 [US1] Implement finalize step with report generation in src/workflows/maven_maintenance.py

### Agent Configuration

- [X] T056 [P] [US1] Create Maven maintenance agent YAML in config/agents/maven_maintenance_agent.yaml
- [X] T057 [P] [US1] Create dependency update prompt in config/prompts/maven/dependency_update.md

### API Endpoints

- [X] T058 [US1] Implement POST /api/testboost/analyze in src/api/routers/testboost.py
- [X] T059 [US1] Implement POST /api/testboost/maintenance/maven in src/api/routers/testboost.py

### CLI Commands

- [X] T060 [US1] Implement `boost maintenance` command in src/cli/commands/maintenance.py
- [X] T061 [US1] Implement `boost audit` command in src/cli/commands/audit.py

### MCP Server - Container Runtime (Constitution Principle 2)

- [X] T062 [P] [US1] Create MCP server structure in src/mcp_servers/container_runtime/__init__.py
- [X] T063 [US1] Implement create-maven-container tool in src/mcp_servers/container_runtime/tools/maven.py
- [X] T064 [P] [US1] Implement execute-in-container tool in src/mcp_servers/container_runtime/tools/execute.py
- [X] T065 [P] [US1] Implement destroy-container tool in src/mcp_servers/container_runtime/tools/destroy.py
- [X] T066 [US1] Create Maven builder Docker image definition in docker/maven-builder/Dockerfile

**Checkpoint**: User Story 1 fully functional - Maven maintenance with rollback

---

## Phase 4: User Story 2 - Génération de Tests Multi-Couches (Priority: P1)

**Goal**: Générer automatiquement une suite de tests complète pour garantir la non-régression

**Independent Test**: Générer tests pour un projet, vérifier compilation et score mutation ≥80%

### MCP Server - Test Generator

- [X] T064 [P] [US2] Create MCP server structure in src/mcp_servers/test_generator/__init__.py
- [X] T065 [US2] Implement analyze-project-context tool in src/mcp_servers/test_generator/tools/analyze.py
- [X] T066 [P] [US2] Implement detect-test-conventions tool in src/mcp_servers/test_generator/tools/conventions.py
- [X] T067 [US2] Implement generate-adaptive-tests tool in src/mcp_servers/test_generator/tools/generate_unit.py
- [X] T068 [US2] Implement generate-integration-tests tool in src/mcp_servers/test_generator/tools/generate_integration.py
- [X] T069 [US2] Implement generate-snapshot-tests tool in src/mcp_servers/test_generator/tools/generate_snapshot.py
- [X] T070 [P] [US2] Implement run-mutation-testing tool in src/mcp_servers/test_generator/tools/mutation.py
- [X] T071 [US2] Implement analyze-mutants tool in src/mcp_servers/test_generator/tools/analyze_mutants.py
- [X] T072 [US2] Implement generate-killer-tests tool in src/mcp_servers/test_generator/tools/killer_tests.py

### MCP Server - PIT Recommendations

- [X] T073 [P] [US2] Create MCP server structure in src/mcp_servers/pit_recommendations/__init__.py
- [X] T074 [US2] Implement analyze-hard-mutants tool in src/mcp_servers/pit_recommendations/tools/analyze.py
- [X] T075 [P] [US2] Implement recommend-test-improvements tool in src/mcp_servers/pit_recommendations/tools/recommend.py
- [X] T076 [P] [US2] Implement prioritize-test-efforts tool in src/mcp_servers/pit_recommendations/tools/prioritize.py

### Workflow Implementation

- [X] T077 [US2] Create test generation workflow graph in src/workflows/test_generation.py
- [X] T078 [US2] Implement analyze_project_structure step in src/workflows/test_generation.py
- [X] T079 [US2] Implement classify_classes step (Controller, Service, Repository) in src/workflows/test_generation.py
- [X] T080 [US2] Implement generate_unit_tests step in src/workflows/test_generation.py
- [X] T081 [US2] Implement compile_and_fix_unit step (3 retries) in src/workflows/test_generation.py
- [X] T082 [US2] Implement generate_integration_tests step in src/workflows/test_generation.py
- [X] T083 [US2] Implement compile_and_fix_integration step in src/workflows/test_generation.py
- [X] T084 [US2] Implement generate_snapshot_tests step in src/workflows/test_generation.py
- [X] T085 [US2] Implement compile_and_fix_snapshot step in src/workflows/test_generation.py
- [X] T086 [US2] Implement deploy_docker step (uses US3 MCP tools) in src/workflows/test_generation.py
- [X] T087 [US2] Implement check_app_health step in src/workflows/test_generation.py
- [X] T088 [US2] Implement generate_e2e_tests step in src/workflows/test_generation.py
- [X] T089 [US2] Implement run_mutation_testing step in src/workflows/test_generation.py
- [X] T090 [US2] Implement generate_killer_tests step (if score <80%) in src/workflows/test_generation.py
- [X] T091 [US2] Implement finalize step with quality report and assertion validation (SC-012) in src/workflows/test_generation.py

### Agent Configuration

- [X] T092 [P] [US2] Create test generation agent YAML in config/agents/test_gen_agent.yaml
- [X] T093 [P] [US2] Create unit test strategy prompt in config/prompts/testing/unit_test_strategy.md
- [X] T094 [P] [US2] Create integration test strategy prompt in config/prompts/testing/integration_strategy.md
- [X] T095 [P] [US2] Create snapshot test prompt in config/prompts/testing/snapshot_strategy.md

### API Endpoints

- [X] T096 [US2] Implement POST /api/testboost/tests/generate in src/api/routers/testboost.py

### CLI Commands

- [X] T097 [US2] Implement `boost tests` command in src/cli/commands/tests.py

**Checkpoint**: User Story 2 fully functional - Test generation with mutation testing

**Note**: US2 depends on US3 MCP Docker tools for deploy_docker/check_app_health steps. Implement US3 MCP server first or in parallel.

---

## Phase 5: User Story 3 - Déploiement Docker Automatisé (Priority: P2)

**Goal**: Déployer l'application dans Docker pour valider le fonctionnement en conteneur

**Independent Test**: Déployer un projet et vérifier health check OK

### MCP Server - Docker

- [X] T098 [P] [US3] Create MCP server structure in src/mcp_servers/docker/__init__.py
- [X] T099 [US3] Implement create-dockerfile tool in src/mcp_servers/docker/tools/dockerfile.py
- [X] T100 [P] [US3] Implement create-compose tool in src/mcp_servers/docker/tools/compose.py
- [X] T101 [US3] Implement deploy-compose tool in src/mcp_servers/docker/tools/deploy.py
- [X] T102 [P] [US3] Implement health-check tool in src/mcp_servers/docker/tools/health.py
- [X] T103 [P] [US3] Implement collect-logs tool in src/mcp_servers/docker/tools/logs.py

### Workflow Implementation

- [X] T104 [US3] Create Docker deployment workflow graph in src/workflows/docker_deployment.py
- [X] T105 [US3] Implement analyze_project step (detect JAR/WAR/Java version) in src/workflows/docker_deployment.py
- [X] T106 [US3] Implement generate_dockerfile step in src/workflows/docker_deployment.py
- [X] T107 [US3] Implement generate_docker_compose step (include dependencies) in src/workflows/docker_deployment.py
- [X] T108 [US3] Implement build_image step in src/workflows/docker_deployment.py
- [X] T109 [US3] Implement run_container step in src/workflows/docker_deployment.py
- [X] T110 [US3] Implement check_health step with wait logic in src/workflows/docker_deployment.py
- [X] T111 [US3] Implement validate_endpoints step in src/workflows/docker_deployment.py
- [X] T112 [US3] Implement finalize step with deployment report in src/workflows/docker_deployment.py

### Agent Configuration

- [X] T113 [P] [US3] Create deployment agent YAML in config/agents/deployment_agent.yaml
- [X] T114 [P] [US3] Create Docker guidelines prompt in config/prompts/deployment/docker_guidelines.md

### CLI Commands

- [X] T115 [US3] Implement `boost deploy` command in src/cli/commands/deploy.py

**Checkpoint**: User Story 3 fully functional - Docker deployment with health check

---

## Phase 6: User Story 4 - Suivi des Workflows en Temps Réel (Priority: P2)

**Goal**: Suivre l'exécution des workflows en temps réel pour comprendre et intervenir

**Independent Test**: Lancer un workflow et vérifier mise à jour temps réel de la progression

### Session Management Service

- [X] T116 [US4] Implement session CRUD service in src/core/session.py
- [X] T117 [US4] Implement real-time status updates in src/core/session.py
- [X] T118 [US4] Implement session history with filters in src/core/session.py
- [X] T119 [US4] Implement audit trail queries in src/core/session.py

### API Endpoints

- [X] T120 [US4] Implement POST /api/v2/sessions in src/api/routers/sessions.py
- [X] T121 [P] [US4] Implement GET /api/v2/sessions with filters in src/api/routers/sessions.py
- [X] T122 [P] [US4] Implement GET /api/v2/sessions/{id} in src/api/routers/sessions.py
- [X] T123 [P] [US4] Implement PATCH /api/v2/sessions/{id} in src/api/routers/sessions.py
- [X] T124 [P] [US4] Implement DELETE /api/v2/sessions/{id} in src/api/routers/sessions.py
- [X] T125 [US4] Implement GET /api/v2/sessions/{id}/steps in src/api/routers/sessions.py
- [X] T126 [P] [US4] Implement GET /api/v2/sessions/{id}/steps/{code} in src/api/routers/sessions.py
- [X] T127 [US4] Implement POST /api/v2/sessions/{id}/steps/{code}/execute in src/api/routers/sessions.py
- [X] T128 [P] [US4] Implement GET /api/v2/sessions/{id}/artifacts in src/api/routers/sessions.py

### Pagination and Filtering

- [X] T129 [US4] Implement pagination helper in src/api/models/pagination.py
- [X] T130 [US4] Add pagination to session list endpoint in src/api/routers/sessions.py

**Checkpoint**: User Story 4 fully functional - Real-time workflow tracking via API

---

## Phase 7: User Story 5 - Mode Interactif vs Autonome (Priority: P3)

**Goal**: Choisir entre mode interactif (confirmations) et autonome (CI/CD)

**Independent Test**: Exécuter même workflow en mode interactif et autonome, vérifier comportements différents

### Mode Management

- [X] T131 [US5] Implement mode configuration in workflow state in src/workflows/state.py
- [X] T132 [US5] Implement confirmation prompts for interactive mode in src/core/workflow.py
- [X] T133 [US5] Implement automatic decisions for autonomous mode in src/core/workflow.py
- [X] T134 [US5] Implement analysis-only mode (no modifications) in src/core/workflow.py
- [X] T135 [US5] Implement debug mode with detailed logs in src/core/workflow.py

### Pause/Resume

- [X] T136 [US5] Implement workflow pause logic in src/core/workflow.py
- [X] T137 [US5] Implement workflow resume with checkpoint restoration (FR-043) in src/core/workflow.py

### API Endpoints

- [X] T138 [US5] Implement POST /api/v2/sessions/{id}/pause in src/api/routers/sessions.py
- [X] T139 [US5] Implement POST /api/v2/sessions/{id}/resume in src/api/routers/sessions.py

### CLI Support

- [X] T140 [US5] Add --mode flag to all CLI commands in src/cli/main.py

**Checkpoint**: User Story 5 fully functional - All execution modes working

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

### Observability

- [X] T141 [P] Integrate LangSmith tracing in src/lib/llm.py
- [X] T142 [P] Add performance metrics logging across workflows
- [X] T143 Configure LangSmith project in src/lib/config.py

### Data Retention

- [X] T144 Implement session purge job (1 year retention) in src/db/jobs/purge.py
- [X] T145 Configure scheduler for purge job (cron/celery beat) in src/db/jobs/scheduler.py
- [X] T146 Implement project cache invalidation in src/core/session.py

### Error Handling

- [X] T147 Implement global exception handler in src/api/middleware/error.py
- [X] T148 Add context to all error messages per FR-032

### Documentation

- [X] T149 [P] Update quickstart.md with actual commands
- [X] T150 [P] Generate OpenAPI schema export in src/api/main.py
- [X] T151 [P] Create deployment documentation in docs/deployment.md

### Final Validation

- [X] T152 Validate all CLI exit codes per quickstart.md
- [X] T153 Run quickstart.md scenarios end-to-end
- [X] T154 Validate OpenAPI contract matches implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational completion
  - US1 and US2 are both P1 - can run in parallel
  - US3 and US4 are both P2 - can run in parallel after P1
  - US5 is P3 - runs after P2
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundational → No story dependencies
- **User Story 2 (P1)**: Foundational → Depends on US3 MCP Docker tools for E2E tests
- **User Story 3 (P2)**: Foundational → Uses Container Runtime MCP from US1
- **User Story 4 (P2)**: Foundational → Uses Session/Step models
- **User Story 5 (P3)**: US4 → Extends session control with pause/resume

### Within Each User Story

- MCP servers before workflows
- Workflow steps in execution order
- Agent config can parallel with implementation
- API/CLI after core implementation

### Parallel Opportunities

**Phase 2 (Foundational)**:
- All models (T007-T011) in parallel
- Config, logging, masking (T014-T016) in parallel
- Auth and logging middleware (T020-T021) in parallel

**Phase 3 (US1)**:
- MCP server structures (T032, T037) in parallel
- Git tools (T039-T040) in parallel
- US1 models (T041-T043) in parallel
- Agent YAML and prompts (T056-T057) in parallel

**Phase 4 (US2)**:
- Convention and mutation tools (T069, T073) in parallel
- PIT tools (T077-T079) in parallel
- All prompts (T092-T095) in parallel

**Phase 5 (US3)**:
- Compose, health, logs tools (T100, T102-T103) in parallel
- Agent config (T113-T114) in parallel

**Phase 6 (US4)**:
- GET endpoints (T121-T124, T126, T128) in parallel

---

## Parallel Example: User Story 1

```bash
# Launch MCP server structures together:
Task: "Create MCP server structure in src/mcp_servers/maven_maintenance/__init__.py"
Task: "Create MCP server structure in src/mcp_servers/git_maintenance/__init__.py"

# Launch all US1 models together:
Task: "Implement Project model in src/db/models/project.py"
Task: "Implement Dependency model in src/db/models/dependency.py"
Task: "Implement Modification model in src/db/models/modification.py"

# Launch agent config together:
Task: "Create Maven maintenance agent YAML in config/agents/maven_maintenance_agent.yaml"
Task: "Create dependency update prompt in config/prompts/maven/dependency_update.md"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Test Maven maintenance end-to-end
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 (Maven Maintenance) → Test → Deploy (MVP!)
3. Add US2 (Test Generation) → Test → Deploy
4. Add US3 (Docker Deployment) → Test → Deploy
5. Add US4 (Workflow Tracking) → Test → Deploy
6. Add US5 (Execution Modes) → Test → Deploy

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (Maven)
   - Developer B: User Story 2 (Tests)
3. After P1 stories:
   - Developer A: User Story 3 (Docker)
   - Developer B: User Story 4 (Tracking)
4. Developer A or B: User Story 5 (Modes)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story
- Avoid: vague tasks, same file conflicts, cross-story dependencies
