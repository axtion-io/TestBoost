# Tasks: Complete Test Plan for TestBoost

**Input**: Design documents from `/specs/004-test-plan-documentation/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Project structure**: `src/`, `tests/` at repository root (existing)
- Tests go in `tests/unit/` and `tests/integration/`
- Fixtures go in `tests/fixtures/`
- Ad-hoc utilities go in `scripts/test-utils/`

---

## Phase 1: Setup (Test Infrastructure)

**Purpose**: Project initialization and test infrastructure setup

- [x] T001 Create test directory structure per plan.md in tests/unit/{api,cli,workflows,db,core}/ and tests/integration/
- [x] T002 Create tests/fixtures/llm_responses/ directory for LLM mock fixtures
- [x] T003 Create tests/fixtures/test_projects/ directory for Maven project fixtures
- [x] T004 [P] Add pytest dependencies to pyproject.toml (pytest, pytest-asyncio, pytest-cov, pytest-xdist, pytest-rerunfailures, httpx, respx)
- [x] T005 [P] Create pytest.ini with coverage thresholds and async mode configuration in tests/pytest.ini
- [x] T006 [P] Create scripts/test-utils/ directory and add to .gitignore

---

## Phase 2: Foundational (Shared Fixtures)

**Purpose**: Core test fixtures that ALL user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T007 Create base conftest.py with async client fixture in tests/conftest.py
- [x] T008 [P] Implement db_session fixture with transaction rollback in tests/conftest.py
- [x] T009 [P] Implement mock_llm fixture loading JSON responses in tests/conftest.py
- [x] T010 [P] Create Gemini LLM response fixtures in tests/fixtures/llm_responses/gemini_responses.json
- [x] T011 [P] Create Claude LLM response fixtures in tests/fixtures/llm_responses/claude_responses.json
- [x] T012 [P] Create OpenAI LLM response fixtures in tests/fixtures/llm_responses/openai_responses.json
- [x] T013 [P] Create sample Maven pom.xml fixture in tests/fixtures/test_projects/sample_pom.xml
- [x] T014 [P] Add pytest markers (integration, slow, flaky, requires_docker, requires_db) in tests/conftest.py

**Checkpoint**: Foundation ready - all fixtures available for test implementation

---

## Phase 3: User Story 1 - CI Pipeline Validation (Priority: P1)

**Goal**: Implement all unit tests for API, CLI, workflows, database, and core modules

**Independent Test**: Run `pytest tests/unit/ -v` and verify all tests pass

### Unit Tests - API Module

- [x] T015 [P] [US1] Create test_health.py with health endpoint tests in tests/unit/api/test_health.py
- [x] T016 [P] [US1] Create test_sessions.py with session CRUD tests in tests/unit/api/test_sessions.py
- [x] T017 [P] [US1] Create test_steps.py with step operation tests in tests/unit/api/test_steps.py
- [x] T018 [P] [US1] Create test_artifacts.py with artifact operation tests in tests/unit/api/test_artifacts.py

### Unit Tests - CLI Module

- [x] T019 [P] [US1] Create test_maintenance.py with maintenance CLI tests in tests/unit/cli/test_maintenance.py
- [x] T020 [P] [US1] Create test_tests.py with test generation CLI tests in tests/unit/cli/test_tests.py
- [x] T021 [P] [US1] Create test_deploy.py with deploy CLI tests in tests/unit/cli/test_deploy.py
- [x] T022 [P] [US1] Create test_config.py with config CLI tests in tests/unit/cli/test_config.py

### Unit Tests - Workflows Module

- [x] T023 [P] [US1] Create test_maven_workflow.py with state transition tests in tests/unit/workflows/test_maven_workflow.py
- [x] T024 [P] [US1] Create test_test_workflow.py with test generation workflow tests in tests/unit/workflows/test_test_workflow.py
- [x] T025 [P] [US1] Create test_deploy_workflow.py with deployment workflow tests in tests/unit/workflows/test_deploy_workflow.py

### Unit Tests - Database Module

- [x] T026 [P] [US1] Create test_models.py with model validation tests in tests/unit/db/test_models.py
- [x] T027 [P] [US1] Create test_crud.py with CRUD operation tests in tests/unit/db/test_crud.py

### Unit Tests - Core Module

- [x] T028 [P] [US1] Create test_config_reload.py with hot-reload tests in tests/unit/core/test_config_reload.py
- [x] T029 [P] [US1] Create test_error_handling.py with error code tests in tests/unit/core/test_error_handling.py

### CI Pipeline

- [x] T030 [US1] Create GitHub Actions workflow in .github/workflows/ci-tests.yml
- [x] T031 [US1] Configure PostgreSQL service container in .github/workflows/ci-tests.yml
- [x] T032 [US1] Add coverage upload to Codecov in .github/workflows/ci-tests.yml

**Checkpoint**: All unit tests pass, CI pipeline runs on PR, coverage reported

---

## Phase 4: User Story 2 - Manual Smoke Testing (Priority: P2)

**Goal**: Create comprehensive manual testing documentation

**Independent Test**: A new developer can follow the checklist and complete in 30 minutes

### Manual Test Documentation

- [x] T033 [US2] Create manual test checklist document in docs/testing/manual-test-checklist.md
- [x] T034 [US2] Document installation verification steps (MT-001 to MT-003) in docs/testing/manual-test-checklist.md
- [x] T035 [US2] Document API verification steps (MT-004 to MT-005) in docs/testing/manual-test-checklist.md
- [x] T036 [US2] Document CLI verification steps (MT-006 to MT-008) in docs/testing/manual-test-checklist.md
- [x] T037 [US2] Document LLM and session verification steps (MT-009 to MT-010) in docs/testing/manual-test-checklist.md
- [x] T038 [US2] Add troubleshooting section with common issues in docs/testing/manual-test-checklist.md
- [x] T039 [US2] Add expected output examples for each test in docs/testing/manual-test-checklist.md

**Checkpoint**: Manual test checklist complete, tested by following it end-to-end

---

## Phase 5: User Story 3 - Ad-hoc Utility Testing (Priority: P3)

**Goal**: Create temporary test utilities for specialized testing scenarios

**Independent Test**: Run each utility and verify it produces expected output

### Ad-hoc Utilities

- [x] T040 [P] [US3] Create smoke test utility in scripts/test-utils/smoke_test.py
- [x] T041 [P] [US3] Create database inspector utility in scripts/test-utils/db_inspector.py
- [x] T042 [P] [US3] Create mock LLM server utility in scripts/test-utils/mock_llm_server.py
- [x] T043 [P] [US3] Create API tester utility in scripts/test-utils/api_tester.py
- [ ] T044 [P] [US3] Create MCP tools benchmark utility in scripts/test-utils/benchmark_mcp_tools.py (deferred)

### Pre-commit Hook

- [x] T045 [US3] Add pre-commit hook installer in scripts/test-utils/install-hooks.sh
- [x] T046 [US3] Document ad-hoc utility usage in scripts/test-utils/README.md

**Checkpoint**: All utilities runnable, pre-commit hook warns if files exist

---

## Phase 6: User Story 4 - Integration Testing (Priority: P4)

**Goal**: Create integration tests for external dependencies

**Independent Test**: Run `pytest tests/integration/ -v` with services running

### Integration Tests

- [x] T047 [P] [US4] Create test_api_db_integration.py with API-DB integration tests in tests/integration/test_api_db_integration.py
- [x] T048 [P] [US4] Create test_llm_integration.py with LLM provider tests in tests/integration/test_llm_integration.py
- [x] T049 [P] [US4] Create test_cli_api_integration.py with CLI-API integration tests in tests/integration/test_cli_api_integration.py
- [x] T050 [P] [US4] Create test_workflow_integration.py with workflow integration tests in tests/integration/test_workflow_integration.py
- [ ] T051 [P] [US4] Create test_git_operations.py with Git operation tests in tests/integration/test_git_operations.py (deferred)

### Integration Test Configuration

- [x] T052 [US4] Add integration markers and skip conditions in tests/conftest.py
- [x] T053 [US4] Configure flaky test retries in pyproject.toml (pytest-rerunfailures)

**Checkpoint**: Integration tests pass when services available, skip gracefully otherwise

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements affecting multiple user stories

- [x] T054 [P] Update pyproject.toml with pytest configuration and coverage settings
- [x] T055 [P] Add pytest-xdist and pytest-rerunfailures dependencies
- [x] T056 Run full test suite and verify 70% line coverage target (343 tests passed)
- [x] T057 Run manual test validation (CLI and API endpoints verified)
- [x] T058 Update tasks.md to reflect completed implementation

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (CI Pipeline)**: Can start after Foundational - No dependencies on other stories
- **US2 (Manual Tests)**: Can start after Foundational - Independent of US1
- **US3 (Ad-hoc Utilities)**: Can start after Foundational - Independent of US1/US2
- **US4 (Integration Tests)**: Can start after Foundational - Independent of other stories

### Within Each User Story

- Fixtures must exist before tests that use them
- Tests can be created in parallel (all marked [P])
- Documentation tasks are sequential within US2
- CI workflow configuration is sequential within US1

### Parallel Opportunities

Within **Phase 1 (Setup)**:
- T004, T005, T006 can run in parallel

Within **Phase 2 (Foundational)**:
- T008, T009 can run in parallel (different fixtures)
- T010, T011, T012, T013 can all run in parallel (different files)

Within **Phase 3 (US1)**:
- All API tests (T015-T018) can run in parallel
- All CLI tests (T019-T022) can run in parallel
- All workflow tests (T023-T025) can run in parallel
- All DB tests (T026-T027) can run in parallel
- All core tests (T028-T029) can run in parallel

Within **Phase 5 (US3)**:
- All utility scripts (T040-T044) can run in parallel

Within **Phase 6 (US4)**:
- All integration tests (T047-T051) can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all API tests in parallel:
Task: "Create test_health.py in tests/unit/api/test_health.py"
Task: "Create test_sessions.py in tests/unit/api/test_sessions.py"
Task: "Create test_steps.py in tests/unit/api/test_steps.py"
Task: "Create test_artifacts.py in tests/unit/api/test_artifacts.py"

# Then launch all CLI tests in parallel:
Task: "Create test_maintenance.py in tests/unit/cli/test_maintenance.py"
Task: "Create test_tests.py in tests/unit/cli/test_tests.py"
...
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL - blocks all stories)
3. Complete Phase 3: User Story 1 (CI Pipeline)
4. **STOP and VALIDATE**: Run `pytest tests/unit/ -v` - all tests pass
5. Deploy CI pipeline - start getting value immediately

### Incremental Delivery

1. Setup + Foundational → Test infrastructure ready
2. Add US1 (CI Pipeline) → Tests run on PR (MVP!)
3. Add US2 (Manual Tests) → Documentation complete
4. Add US3 (Ad-hoc Utilities) → Dev tools available
5. Add US4 (Integration Tests) → Full test coverage
6. Each story adds value without breaking previous stories

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (CI Pipeline)
   - Developer B: User Story 2 (Manual Tests)
   - Developer C: User Story 3 (Ad-hoc Utilities)
   - Developer D: User Story 4 (Integration Tests)
3. Stories complete and integrate independently

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All tests must follow Constitution Principle 1: No fake success, real failures only

---

# Part 2: CLI vs API Parity Tasks

**Input**: Gap analysis between CLI and API implementations (2026-01-07)
**Goal**: Combler les gaps de parité entre CLI et API identifiés

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US5=Step Execution, US6=Session Control, US7=Artifacts, US8=Audit API, US9=Impact API

---

## Phase 8: Setup (CLI Utilities)

**Purpose**: Préparer les utilitaires communs pour les nouvelles commandes CLI

- [ ] T059 [P] Créer helper HTTP client réutilisable dans src/cli/utils/api_client.py
- [ ] T060 [P] Ajouter constantes API_BASE_URL et endpoints dans src/cli/constants.py

---

## Phase 9: Foundational (CLI Error Handling)

**Purpose**: Infrastructure partagée par toutes les nouvelles commandes

- [ ] T061 Ajouter gestion des erreurs API dans src/cli/utils/api_client.py (401, 404, 409, 500)
- [ ] T062 [P] Créer formatters Rich réutilisables pour sessions/steps/artifacts dans src/cli/formatters.py

**Checkpoint**: Foundation ready - CLI commands can now be implemented

---

## Phase 10: User Story 5 - Step Execution CLI (Priority: P1) 🎯 MVP

**Goal**: Permettre l'exécution de steps spécifiques via CLI pour le mode interactif

**Independent Test**: `python -m src.cli.main maintenance step <session_id> <step_code>` exécute le step

### Implementation for User Story 5

- [ ] T063 [US5] Ajouter commande `step` dans src/cli/commands/maintenance.py
  - Signature: `step(session_id: str, step_code: str)`
  - Appeler `POST /api/v2/sessions/{id}/steps/{code}/execute`
  - Afficher résultat avec Rich Panel (status, message)

- [ ] T064 [US5] Ajouter commande `steps` pour lister les steps d'une session dans src/cli/commands/maintenance.py
  - Signature: `steps(session_id: str)`
  - Appeler `GET /api/v2/sessions/{id}/steps`
  - Afficher tableau Rich (code, name, status, sequence)

- [ ] T065 [US5] Documenter les nouvelles commandes step dans docs/cli-reference.md

**Checkpoint**: Step execution via CLI is functional

---

## Phase 11: User Story 6 - Session Control CLI (Priority: P1)

**Goal**: Permettre pause/resume et listing des sessions via CLI

**Independent Test**:
- `python -m src.cli.main maintenance sessions` affiche la liste
- `python -m src.cli.main maintenance pause <id>` met en pause

### Implementation for User Story 6

- [ ] T066 [US6] Ajouter commande `sessions` dans src/cli/commands/maintenance.py
  - Signature: `sessions(status: str = None, session_type: str = None, limit: int = 20)`
  - Appeler `GET /api/v2/sessions` avec query params
  - Afficher tableau paginé Rich (id, type, status, project_path, created_at)

- [ ] T067 [US6] Ajouter commande `pause` dans src/cli/commands/maintenance.py
  - Signature: `pause(session_id: str, reason: str = None)`
  - Appeler `POST /api/v2/sessions/{id}/pause`
  - Afficher confirmation avec checkpoint_id

- [ ] T068 [US6] Ajouter commande `resume` dans src/cli/commands/maintenance.py
  - Signature: `resume(session_id: str, checkpoint: str = None)`
  - Appeler `POST /api/v2/sessions/{id}/resume`
  - Afficher confirmation

- [ ] T069 [US6] Documenter pause/resume dans docs/user-guide.md section "Modes d'Exécution"

**Checkpoint**: Full session control via CLI is functional

---

## Phase 12: User Story 7 - Artifacts & Cancel CLI (Priority: P2)

**Goal**: Permettre récupération des artifacts et annulation de workflows via CLI

**Independent Test**:
- `python -m src.cli.main maintenance artifacts <id>` affiche les artifacts
- `python -m src.cli.main maintenance cancel <id>` annule le workflow

### Implementation for User Story 7

- [ ] T070 [US7] Ajouter commande `artifacts` dans src/cli/commands/maintenance.py
  - Signature: `artifacts(session_id: str, artifact_type: str = None, output: str = None)`
  - Appeler `GET /api/v2/sessions/{id}/artifacts`
  - Afficher liste ou sauvegarder JSON si --output spécifié

- [ ] T071 [US7] Ajouter commande `cancel` dans src/cli/commands/maintenance.py
  - Signature: `cancel(session_id: str, force: bool = False)`
  - Demander confirmation (sauf si --force)
  - Appeler `DELETE /api/testboost/maintenance/maven/{id}`
  - Afficher confirmation

- [ ] T072 [US7] Documenter artifacts et cancel dans docs/cli-reference.md

**Checkpoint**: Artifact retrieval and workflow cancellation via CLI functional

---

## Phase 13: User Story 8 - Audit API Endpoints (Priority: P2)

**Goal**: Exposer les fonctionnalités d'audit via API pour intégration CI/CD

**Independent Test**:
- `POST /api/audit/scan` lance un scan
- `GET /api/audit/report/{id}` récupère le rapport

### Implementation for User Story 8

- [ ] T073 [P] [US8] Créer router src/api/routers/audit.py avec modèles Pydantic
  - AuditScanRequest(project_path, severity, output_format)
  - AuditScanResponse(success, session_id, vulnerabilities[])
  - AuditReportResponse(project_path, vulnerabilities[], dependencies[])

- [ ] T074 [US8] Implémenter endpoint `POST /api/audit/scan` dans src/api/routers/audit.py
  - Réutiliser src/mcp_servers/maven_maintenance/tools/analyze.py
  - Retourner résultats JSON

- [ ] T075 [US8] Implémenter endpoint `GET /api/audit/report/{session_id}` dans src/api/routers/audit.py
  - Retourner rapport JSON avec vulnérabilités et dépendances

- [ ] T076 [US8] Implémenter endpoint `GET /api/audit/report/{session_id}/html` dans src/api/routers/audit.py
  - Réutiliser _generate_html_report() de src/cli/commands/audit.py
  - Retourner HTML response

- [ ] T077 [US8] Enregistrer router audit dans src/api/main.py
  - `app.include_router(audit.router)`

- [ ] T078 [US8] Documenter endpoints audit dans docs/api-authentication.md

**Checkpoint**: Audit functionality exposed via API

---

## Phase 14: User Story 9 - Impact Analysis API (Priority: P2)

**Goal**: Exposer l'analyse d'impact via API pour intégration CI/CD

**Independent Test**: `POST /api/tests/impact` retourne ImpactReport JSON

### Implementation for User Story 9

- [ ] T079 [P] [US9] Ajouter modèles Pydantic pour Impact dans src/api/routers/testboost.py
  - ImpactAnalysisRequest(project_path, chunk_size, verbose)
  - ImpactAnalysisResponse(success, impacts[], test_requirements[], summary)

- [ ] T080 [US9] Implémenter endpoint `POST /api/tests/impact` dans src/api/routers/testboost.py
  - Appeler src/workflows/impact_analysis.run_impact_analysis()
  - Retourner ImpactReport.to_dict()

- [ ] T081 [US9] Documenter endpoint impact dans docs/api-authentication.md

**Checkpoint**: Impact analysis exposed via API

---

## Phase 15: CLI/API Parity - Polish

**Purpose**: Validation finale et tests

- [ ] T082 [P] Ajouter tests unitaires pour nouvelles commandes CLI dans tests/unit/cli/test_maintenance.py
- [ ] T083 [P] Ajouter tests unitaires pour nouveaux endpoints API dans tests/unit/api/test_audit.py
- [ ] T084 [P] Mettre à jour docs/user-guide.md avec toutes les nouvelles commandes
- [ ] T085 Vérifier que `--help` affiche correctement toutes les commandes
- [ ] T086 Run quickstart.md validation avec nouvelles fonctionnalités

---

## CLI vs API Parity - Dependencies

### Phase Dependencies

- **Phase 8-9 (Setup/Foundational)**: Foundation for CLI commands
- **Phase 10-12 (CLI)**: Depend on Phase 8-9, can run in parallel
- **Phase 13-14 (API)**: Independent of CLI phases, can run in parallel

### Parallel Execution

```text
After Phase 9 (Foundational) completes:

CLI Track:                        API Track:
├── US5: Step Execution (P1)      ├── US8: Audit Endpoints (P2)
├── US6: Session Control (P1)     └── US9: Impact Endpoint (P2)
└── US7: Artifacts/Cancel (P2)

Both tracks can run in parallel!
```

### Priority Summary

| Priority | User Story | Files Modified |
|----------|------------|----------------|
| P1 | US5: Step Execution | maintenance.py, cli-reference.md |
| P1 | US6: Session Control | maintenance.py, user-guide.md |
| P2 | US7: Artifacts/Cancel | maintenance.py, cli-reference.md |
| P2 | US8: Audit API | audit.py (new), main.py, api-authentication.md |
| P2 | US9: Impact API | testboost.py, api-authentication.md |

### Total New Tasks: 28 (T059-T086)
