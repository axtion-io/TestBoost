# Tasks: TestBoost Core

**Input**: Design documents from `/specs/001-testboost-core/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Not explicitly requested in spec - test tasks omitted. Add if needed.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story (US1-US5)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [ ] T001 Create project structure per plan.md in src/
- [ ] T002 Initialize Python project with Poetry and pyproject.toml
- [ ] T003 [P] Configure ruff linter and black formatter in pyproject.toml
- [ ] T004 [P] Create .env.example with all required environment variables
- [ ] T005 [P] Create docker-compose.yaml for PostgreSQL and application

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database Layer

- [ ] T006 Create SQLAlchemy base and session factory in src/db/__init__.py
- [ ] T007 [P] Implement Session model in src/db/models/session.py
- [ ] T008 [P] Implement Step model in src/db/models/step.py
- [ ] T009 [P] Implement Event model in src/db/models/event.py
- [ ] T010 [P] Implement Artifact model in src/db/models/artifact.py
- [ ] T011 [P] Implement ProjectLock model in src/db/models/project_lock.py
- [ ] T012 Create Alembic migrations for all models in src/db/migrations/
- [ ] T013 Implement repository pattern in src/db/repository.py

### Core Services

- [ ] T014 Implement configuration management with Pydantic Settings in src/lib/config.py
- [ ] T015 [P] Implement structured JSON logging with structlog in src/lib/logging.py
- [ ] T016 [P] Implement sensitive data masking in src/lib/logging.py (FR-046A)
- [ ] T017 Implement event sourcing service in src/core/events.py
- [ ] T018 Implement project lock service in src/core/locking.py

### API Foundation

- [ ] T019 Create FastAPI app with middleware in src/api/main.py
- [ ] T020 [P] Implement API key authentication middleware in src/api/middleware/auth.py
- [ ] T021 [P] Implement request logging middleware in src/api/middleware/logging.py
- [ ] T022 Implement health check endpoint in src/api/routers/health.py
- [ ] T023 Create Pydantic schemas for Session/Step/Event in src/api/models/

### LangGraph Foundation

- [ ] T024 Implement LLM provider factory with retry logic (FR-009A) in src/lib/llm.py
- [ ] T025 Create base workflow state schema in src/workflows/state.py
- [ ] T026 Implement workflow executor with LangGraph in src/core/workflow.py

### Agent Foundation

- [ ] T027 Implement DeepAgents YAML loader in src/agents/loader.py
- [ ] T028 Implement LangGraph agent adapter in src/agents/adapter.py
- [ ] T029 [P] Create common Java expert prompt in config/prompts/common/java_expert.md

### CLI Foundation

- [ ] T030 Create Typer CLI app structure in src/cli/main.py
- [ ] T031 Implement CLI exit codes per quickstart.md in src/cli/main.py

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Maintenance Maven avec Non-Régression (Priority: P1) 🎯 MVP

**Goal**: Mettre à jour les dépendances Maven automatiquement en garantissant la non-régression

**Independent Test**: Exécuter le workflow sur un projet Maven avec dépendances obsolètes, vérifier tous tests passent après

### MCP Server - Maven Maintenance

- [ ] T032 [P] [US1] Create MCP server structure in src/mcp_servers/maven_maintenance/__init__.py
- [ ] T033 [US1] Implement analyze-dependencies tool in src/mcp_servers/maven_maintenance/tools/analyze.py
- [ ] T034 [P] [US1] Implement compile-tests tool in src/mcp_servers/maven_maintenance/tools/compile.py
- [ ] T035 [P] [US1] Implement run-tests tool in src/mcp_servers/maven_maintenance/tools/run_tests.py
- [ ] T036 [P] [US1] Implement package tool in src/mcp_servers/maven_maintenance/tools/package.py

### MCP Server - Git Maintenance

- [ ] T037 [P] [US1] Create MCP server structure in src/mcp_servers/git_maintenance/__init__.py
- [ ] T038 [US1] Implement create-maintenance-branch tool in src/mcp_servers/git_maintenance/tools/branch.py
- [ ] T039 [P] [US1] Implement commit-changes tool in src/mcp_servers/git_maintenance/tools/commit.py
- [ ] T040 [P] [US1] Implement get-status tool in src/mcp_servers/git_maintenance/tools/status.py

### Data Models for US1

- [ ] T041 [P] [US1] Implement Project model in src/db/models/project.py
- [ ] T042 [P] [US1] Implement Dependency model in src/db/models/dependency.py
- [ ] T043 [P] [US1] Implement Modification model in src/db/models/modification.py
- [ ] T044 [US1] Create Alembic migration for US1 models

### Workflow Implementation

- [ ] T045 [US1] Create Maven maintenance workflow graph in src/workflows/maven_maintenance.py
- [ ] T046 [US1] Implement validate_project step in src/workflows/maven_maintenance.py
- [ ] T047 [US1] Implement check_git_status step in src/workflows/maven_maintenance.py
- [ ] T048 [US1] Implement analyze_maven step with dependency classification in src/workflows/maven_maintenance.py
- [ ] T048b [US1] Implement fetch_release_notes step (FR-012) in src/workflows/maven_maintenance.py
- [ ] T049 [US1] Implement run_baseline_tests step in src/workflows/maven_maintenance.py
- [ ] T050 [US1] Implement user_validation step (interactive mode) in src/workflows/maven_maintenance.py
- [ ] T051 [US1] Implement create_maintenance_branch step in src/workflows/maven_maintenance.py
- [ ] T052 [US1] Implement apply_update_batch step with rollback in src/workflows/maven_maintenance.py
- [ ] T053 [US1] Implement validate_changes step in src/workflows/maven_maintenance.py
- [ ] T054 [US1] Implement commit_changes step in src/workflows/maven_maintenance.py
- [ ] T055 [US1] Implement finalize step with report generation in src/workflows/maven_maintenance.py

### Agent Configuration

- [ ] T056 [P] [US1] Create Maven maintenance agent YAML in config/agents/maven_maintenance_agent.yaml
- [ ] T057 [P] [US1] Create dependency update prompt in config/prompts/maven/dependency_update.md

### API Endpoints

- [ ] T058 [US1] Implement POST /api/testboost/analyze in src/api/routers/testboost.py
- [ ] T059 [US1] Implement POST /api/testboost/maintenance/maven in src/api/routers/testboost.py

### CLI Commands

- [ ] T060 [US1] Implement `boost maintenance` command in src/cli/commands/maintenance.py
- [ ] T061 [US1] Implement `boost audit` command in src/cli/commands/audit.py

### MCP Server - Container Runtime (Constitution Principle 2)

- [ ] T062 [P] [US1] Create MCP server structure in src/mcp_servers/container_runtime/__init__.py
- [ ] T063 [US1] Implement create-maven-container tool in src/mcp_servers/container_runtime/tools/maven.py
- [ ] T064 [P] [US1] Implement execute-in-container tool in src/mcp_servers/container_runtime/tools/execute.py
- [ ] T065 [P] [US1] Implement destroy-container tool in src/mcp_servers/container_runtime/tools/destroy.py
- [ ] T066 [US1] Create Maven builder Docker image definition in docker/maven-builder/Dockerfile

**Checkpoint**: User Story 1 fully functional - Maven maintenance with rollback

---

## Phase 4: User Story 2 - Génération de Tests Multi-Couches (Priority: P1)

**Goal**: Générer automatiquement une suite de tests complète pour garantir la non-régression

**Independent Test**: Générer tests pour un projet, vérifier compilation et score mutation ≥80%

### MCP Server - Test Generator

- [ ] T064 [P] [US2] Create MCP server structure in src/mcp_servers/test_generator/__init__.py
- [ ] T065 [US2] Implement analyze-project-context tool in src/mcp_servers/test_generator/tools/analyze.py
- [ ] T066 [P] [US2] Implement detect-test-conventions tool in src/mcp_servers/test_generator/tools/conventions.py
- [ ] T067 [US2] Implement generate-adaptive-tests tool in src/mcp_servers/test_generator/tools/generate_unit.py
- [ ] T068 [US2] Implement generate-integration-tests tool in src/mcp_servers/test_generator/tools/generate_integration.py
- [ ] T069 [US2] Implement generate-snapshot-tests tool in src/mcp_servers/test_generator/tools/generate_snapshot.py
- [ ] T070 [P] [US2] Implement run-mutation-testing tool in src/mcp_servers/test_generator/tools/mutation.py
- [ ] T071 [US2] Implement analyze-mutants tool in src/mcp_servers/test_generator/tools/analyze_mutants.py
- [ ] T072 [US2] Implement generate-killer-tests tool in src/mcp_servers/test_generator/tools/killer_tests.py

### MCP Server - PIT Recommendations

- [ ] T073 [P] [US2] Create MCP server structure in src/mcp_servers/pit_recommendations/__init__.py
- [ ] T074 [US2] Implement analyze-hard-mutants tool in src/mcp_servers/pit_recommendations/tools/analyze.py
- [ ] T075 [P] [US2] Implement recommend-test-improvements tool in src/mcp_servers/pit_recommendations/tools/recommend.py
- [ ] T076 [P] [US2] Implement prioritize-test-efforts tool in src/mcp_servers/pit_recommendations/tools/prioritize.py

### Workflow Implementation

- [ ] T077 [US2] Create test generation workflow graph in src/workflows/test_generation.py
- [ ] T078 [US2] Implement analyze_project_structure step in src/workflows/test_generation.py
- [ ] T079 [US2] Implement classify_classes step (Controller, Service, Repository) in src/workflows/test_generation.py
- [ ] T080 [US2] Implement generate_unit_tests step in src/workflows/test_generation.py
- [ ] T081 [US2] Implement compile_and_fix_unit step (3 retries) in src/workflows/test_generation.py
- [ ] T082 [US2] Implement generate_integration_tests step in src/workflows/test_generation.py
- [ ] T083 [US2] Implement compile_and_fix_integration step in src/workflows/test_generation.py
- [ ] T084 [US2] Implement generate_snapshot_tests step in src/workflows/test_generation.py
- [ ] T085 [US2] Implement compile_and_fix_snapshot step in src/workflows/test_generation.py
- [ ] T086 [US2] Implement deploy_docker step (uses US3 MCP tools) in src/workflows/test_generation.py
- [ ] T087 [US2] Implement check_app_health step in src/workflows/test_generation.py
- [ ] T088 [US2] Implement generate_e2e_tests step in src/workflows/test_generation.py
- [ ] T089 [US2] Implement run_mutation_testing step in src/workflows/test_generation.py
- [ ] T090 [US2] Implement generate_killer_tests step (if score <80%) in src/workflows/test_generation.py
- [ ] T091 [US2] Implement finalize step with quality report and assertion validation (SC-012) in src/workflows/test_generation.py

### Agent Configuration

- [ ] T092 [P] [US2] Create test generation agent YAML in config/agents/test_gen_agent.yaml
- [ ] T093 [P] [US2] Create unit test strategy prompt in config/prompts/testing/unit_test_strategy.md
- [ ] T094 [P] [US2] Create integration test strategy prompt in config/prompts/testing/integration_strategy.md
- [ ] T095 [P] [US2] Create snapshot test prompt in config/prompts/testing/snapshot_strategy.md

### API Endpoints

- [ ] T096 [US2] Implement POST /api/testboost/tests/generate in src/api/routers/testboost.py

### CLI Commands

- [ ] T097 [US2] Implement `boost tests` command in src/cli/commands/tests.py

**Checkpoint**: User Story 2 fully functional - Test generation with mutation testing

**Note**: US2 depends on US3 MCP Docker tools for deploy_docker/check_app_health steps. Implement US3 MCP server first or in parallel.

---

## Phase 5: User Story 3 - Déploiement Docker Automatisé (Priority: P2)

**Goal**: Déployer l'application dans Docker pour valider le fonctionnement en conteneur

**Independent Test**: Déployer un projet et vérifier health check OK

### MCP Server - Docker

- [ ] T098 [P] [US3] Create MCP server structure in src/mcp_servers/docker/__init__.py
- [ ] T099 [US3] Implement create-dockerfile tool in src/mcp_servers/docker/tools/dockerfile.py
- [ ] T100 [P] [US3] Implement create-compose tool in src/mcp_servers/docker/tools/compose.py
- [ ] T101 [US3] Implement deploy-compose tool in src/mcp_servers/docker/tools/deploy.py
- [ ] T102 [P] [US3] Implement health-check tool in src/mcp_servers/docker/tools/health.py
- [ ] T103 [P] [US3] Implement collect-logs tool in src/mcp_servers/docker/tools/logs.py

### Workflow Implementation

- [ ] T104 [US3] Create Docker deployment workflow graph in src/workflows/docker_deployment.py
- [ ] T105 [US3] Implement analyze_project step (detect JAR/WAR/Java version) in src/workflows/docker_deployment.py
- [ ] T106 [US3] Implement generate_dockerfile step in src/workflows/docker_deployment.py
- [ ] T107 [US3] Implement generate_docker_compose step (include dependencies) in src/workflows/docker_deployment.py
- [ ] T108 [US3] Implement build_image step in src/workflows/docker_deployment.py
- [ ] T109 [US3] Implement run_container step in src/workflows/docker_deployment.py
- [ ] T110 [US3] Implement check_health step with wait logic in src/workflows/docker_deployment.py
- [ ] T111 [US3] Implement validate_endpoints step in src/workflows/docker_deployment.py
- [ ] T112 [US3] Implement finalize step with deployment report in src/workflows/docker_deployment.py

### Agent Configuration

- [ ] T113 [P] [US3] Create deployment agent YAML in config/agents/deployment_agent.yaml
- [ ] T114 [P] [US3] Create Docker guidelines prompt in config/prompts/deployment/docker_guidelines.md

### CLI Commands

- [ ] T115 [US3] Implement `boost deploy` command in src/cli/commands/deploy.py

**Checkpoint**: User Story 3 fully functional - Docker deployment with health check

---

## Phase 6: User Story 4 - Suivi des Workflows en Temps Réel (Priority: P2)

**Goal**: Suivre l'exécution des workflows en temps réel pour comprendre et intervenir

**Independent Test**: Lancer un workflow et vérifier mise à jour temps réel de la progression

### Session Management Service

- [ ] T116 [US4] Implement session CRUD service in src/core/session.py
- [ ] T117 [US4] Implement real-time status updates in src/core/session.py
- [ ] T118 [US4] Implement session history with filters in src/core/session.py
- [ ] T119 [US4] Implement audit trail queries in src/core/session.py

### API Endpoints

- [ ] T120 [US4] Implement POST /api/v2/sessions in src/api/routers/sessions.py
- [ ] T121 [P] [US4] Implement GET /api/v2/sessions with filters in src/api/routers/sessions.py
- [ ] T122 [P] [US4] Implement GET /api/v2/sessions/{id} in src/api/routers/sessions.py
- [ ] T123 [P] [US4] Implement PATCH /api/v2/sessions/{id} in src/api/routers/sessions.py
- [ ] T124 [P] [US4] Implement DELETE /api/v2/sessions/{id} in src/api/routers/sessions.py
- [ ] T125 [US4] Implement GET /api/v2/sessions/{id}/steps in src/api/routers/sessions.py
- [ ] T126 [P] [US4] Implement GET /api/v2/sessions/{id}/steps/{code} in src/api/routers/sessions.py
- [ ] T127 [US4] Implement POST /api/v2/sessions/{id}/steps/{code}/execute in src/api/routers/sessions.py
- [ ] T128 [P] [US4] Implement GET /api/v2/sessions/{id}/artifacts in src/api/routers/sessions.py

### Pagination and Filtering

- [ ] T129 [US4] Implement pagination helper in src/api/models/pagination.py
- [ ] T130 [US4] Add pagination to session list endpoint in src/api/routers/sessions.py

**Checkpoint**: User Story 4 fully functional - Real-time workflow tracking via API

---

## Phase 7: User Story 5 - Mode Interactif vs Autonome (Priority: P3)

**Goal**: Choisir entre mode interactif (confirmations) et autonome (CI/CD)

**Independent Test**: Exécuter même workflow en mode interactif et autonome, vérifier comportements différents

### Mode Management

- [ ] T131 [US5] Implement mode configuration in workflow state in src/workflows/state.py
- [ ] T132 [US5] Implement confirmation prompts for interactive mode in src/core/workflow.py
- [ ] T133 [US5] Implement automatic decisions for autonomous mode in src/core/workflow.py
- [ ] T134 [US5] Implement analysis-only mode (no modifications) in src/core/workflow.py
- [ ] T135 [US5] Implement debug mode with detailed logs in src/core/workflow.py

### Pause/Resume

- [ ] T136 [US5] Implement workflow pause logic in src/core/workflow.py
- [ ] T137 [US5] Implement workflow resume with checkpoint restoration (FR-043) in src/core/workflow.py

### API Endpoints

- [ ] T138 [US5] Implement POST /api/v2/sessions/{id}/pause in src/api/routers/sessions.py
- [ ] T139 [US5] Implement POST /api/v2/sessions/{id}/resume in src/api/routers/sessions.py

### CLI Support

- [ ] T140 [US5] Add --mode flag to all CLI commands in src/cli/main.py

**Checkpoint**: User Story 5 fully functional - All execution modes working

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

### Observability

- [ ] T141 [P] Integrate LangSmith tracing in src/lib/llm.py
- [ ] T142 [P] Add performance metrics logging across workflows
- [ ] T143 Configure LangSmith project in src/lib/config.py

### Data Retention

- [ ] T144 Implement session purge job (1 year retention) in src/db/jobs/purge.py
- [ ] T145 Configure scheduler for purge job (cron/celery beat) in src/db/jobs/scheduler.py
- [ ] T146 Implement project cache invalidation in src/core/session.py

### Error Handling

- [ ] T147 Implement global exception handler in src/api/middleware/error.py
- [ ] T148 Add context to all error messages per FR-032

### Documentation

- [ ] T149 [P] Update quickstart.md with actual commands
- [ ] T150 [P] Generate OpenAPI schema export in src/api/main.py
- [ ] T151 [P] Create deployment documentation in docs/deployment.md

### Final Validation

- [ ] T152 Validate all CLI exit codes per quickstart.md
- [ ] T153 Run quickstart.md scenarios end-to-end
- [ ] T154 Validate OpenAPI contract matches implementation

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
