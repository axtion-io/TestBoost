# Feature Specification: Complete Test Plan for TestBoost

**Feature Branch**: `004-test-plan-documentation`
**Created**: 2026-01-04
**Status**: Draft
**Input**: User description: "Re-analyze README.md and all .md files in docs to create a complete test plan: manual tests, ad-hoc Python utilities, and CI-ready tests"

## Clarifications

### Session 2026-01-04

- Q: Quel environnement CI cible pour les tests automatisés ? → A: GitHub Actions uniquement
- Q: Stratégie de mock LLM pour les tests unitaires ? → A: Mock avec réponses pré-enregistrées (fixtures JSON)
- Q: Isolation de la base de données entre les tests ? → A: Transaction rollback après chaque test
- Q: Définition de "standard hardware" pour le critère des 5 minutes ? → A: GitHub Actions runner standard (2 vCPU, 7GB RAM)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - CI Pipeline Validation (Priority: P1)

A DevOps engineer wants to ensure that all critical TestBoost functionalities are validated automatically on every commit and pull request to prevent regressions.

**Why this priority**: CI tests are the first line of defense against regressions and broken deployments. They must run reliably on every code change.

**Independent Test**: Can be fully tested by running `pytest tests/` and verifying all tests pass with exit code 0.

**Acceptance Scenarios**:

1. **Given** a clean clone of the repository, **When** `pytest tests/` is executed, **Then** all tests pass within 5 minutes.
2. **Given** a PR with code changes, **When** the CI pipeline runs, **Then** test results are reported with pass/fail status and coverage metrics.
3. **Given** a test failure, **When** reviewing the output, **Then** the failure reason and location are clearly identifiable.

---

### User Story 2 - Manual Smoke Testing (Priority: P2)

A developer wants to quickly verify that the core workflows function correctly after installation or major changes through manual exploratory testing.

**Why this priority**: Manual testing catches issues that automated tests might miss, especially around UX and edge cases discovered during exploration.

**Independent Test**: Can be tested by following a documented checklist of manual steps and recording pass/fail for each item.

**Acceptance Scenarios**:

1. **Given** a fresh installation, **When** following the manual test checklist, **Then** all smoke test items pass.
2. **Given** a manual tester, **When** performing exploratory testing, **Then** issues found are documented with reproduction steps.
3. **Given** the CLI, **When** running each documented command, **Then** the expected output is displayed.

---

### User Story 3 - Ad-hoc Utility Testing (Priority: P3)

A developer needs temporary Python utilities to test specific scenarios (load testing, multi-provider validation, database state verification) that are not suitable for permanent CI inclusion.

**Why this priority**: Ad-hoc utilities enable deep testing and debugging without polluting the permanent test suite.

**Independent Test**: Can be tested by running ad-hoc scripts from a dedicated `scripts/test-utils/` directory and verifying they produce expected output.

**Acceptance Scenarios**:

1. **Given** an ad-hoc test utility, **When** executed, **Then** it produces a clear report of test results.
2. **Given** ad-hoc utilities exist, **When** preparing for commit, **Then** a pre-commit hook warns if any ad-hoc files remain.
3. **Given** a developer, **When** needing to test a specific scenario, **Then** they can create a utility in `scripts/test-utils/` following a documented template.

---

### User Story 4 - Integration Testing of External Dependencies (Priority: P4)

A developer wants to verify that TestBoost correctly integrates with external services (PostgreSQL, LLM providers, Docker) in a controlled environment.

**Why this priority**: Integration failures are common but harder to debug; dedicated integration tests ensure external dependencies work as expected.

**Independent Test**: Can be tested by running `pytest tests/integration/` with required services running (Docker, PostgreSQL).

**Acceptance Scenarios**:

1. **Given** PostgreSQL is running on port 5433, **When** running database integration tests, **Then** all database operations succeed.
2. **Given** valid LLM API keys are configured, **When** running LLM integration tests, **Then** responses are received within timeout.
3. **Given** Docker is running, **When** running deployment integration tests, **Then** containers are created and health checks pass.

---

### Edge Cases

- What happens when PostgreSQL is not available? Tests should fail gracefully with clear error message.
- What happens when LLM API keys are invalid or missing? Tests should skip or fail with explicit provider error.
- What happens when a test times out? Clear timeout message with configurable duration.
- What happens when running tests without required dependencies? Skip with informative message listing missing dependencies.
- What happens when network connectivity is intermittent? Retry logic with exponential backoff for integration tests.

## Requirements *(mandatory)*

### Functional Requirements

#### CI Tests (Automated pytest suite)

- **FR-001**: System MUST include unit tests for all public API endpoints (`/health`, `/api/v2/sessions/*`, `/api/v2/steps/*`, `/api/v2/artifacts/*`)
- **FR-002**: System MUST include unit tests for all CLI commands (`maintenance list/run`, `tests generate/analyze`, `deploy run`, `config validate/show/backup/rollback/reload`)
- **FR-003**: System MUST include tests for workflow state transitions (pending -> analysis -> planning -> executing -> validating -> completed/failed)
- **FR-004**: System MUST include tests for error handling (all error codes defined in API Error Reference: 400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504)
- **FR-005**: System MUST include tests for database operations (CRUD on sessions, steps, events, artifacts, projects, project_locks)
- **FR-006**: System MUST include tests for configuration hot-reload functionality
- **FR-007**: System MUST achieve minimum 70% line coverage and 60% branch coverage
- **FR-008**: System MUST include mutation testing with PIT achieving 80% mutation score for critical modules

#### Integration Tests

- **FR-009**: System MUST include integration tests for PostgreSQL connectivity and schema validation
- **FR-010**: System MUST include integration tests for LLM provider connectivity (Google Gemini, Anthropic Claude, OpenAI)
- **FR-011**: System MUST include integration tests for Docker deployment workflow
- **FR-012**: System MUST include integration tests for MCP tool invocations (maven_analyze, maven_compile, maven_run_tests, etc.)
- **FR-013**: System MUST include integration tests for Git operations (status, branch, commit)

#### Manual Tests

- **FR-014**: Users MUST be able to perform installation verification using documented checklist
- **FR-015**: Users MUST be able to validate each CLI command with expected output examples
- **FR-016**: Users MUST be able to perform end-to-end workflow testing (Maven maintenance on sample project)
- **FR-017**: Users MUST be able to verify API health endpoint with documented response format

#### Ad-hoc Test Utilities

- **FR-018**: System MUST provide a multi-provider validation script to test all configured LLM providers
- **FR-019**: System MUST provide a load testing utility for concurrent session simulation
- **FR-020**: System MUST provide a database state verification utility
- **FR-021**: System MUST provide a template for creating new ad-hoc test utilities
- **FR-022**: All ad-hoc utilities MUST be placed in `scripts/test-utils/` and excluded from git before commit

#### Test Infrastructure

- **FR-023**: System MUST use pytest as the test framework with pytest-asyncio for async tests
- **FR-024**: System MUST use pytest-cov for coverage reporting
- **FR-025**: System MUST include fixtures for common test setup (database session, mock LLM, test project)
- **FR-026**: System MUST support running tests in parallel with pytest-xdist
- **FR-027**: System MUST include test data fixtures for sample Maven projects
- **FR-028**: System MUST include LLM response fixtures (JSON) for deterministic unit tests without real API calls
- **FR-029**: Database tests MUST use transaction rollback for isolation (each test runs in a transaction that is rolled back after completion)

### Key Entities

- **Test Case**: A single test with name, category (unit/integration/e2e), status, and execution time
- **Test Suite**: A collection of related test cases (e.g., api_tests, cli_tests, workflow_tests)
- **Test Report**: Aggregated results including pass/fail counts, coverage, and duration
- **Ad-hoc Utility**: A temporary Python script for specific testing scenarios, excluded from production code

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All CI tests complete within 5 minutes on GitHub Actions standard runner (2 vCPU, 7GB RAM)
- **SC-002**: Test coverage reaches minimum 70% line coverage (measured by pytest-cov)
- **SC-003**: Zero critical or high-severity bugs escape to production after test implementation
- **SC-004**: Manual test checklist can be completed by a new developer within 30 minutes
- **SC-005**: 95% of test runs produce consistent results (no flaky tests)
- **SC-006**: Integration tests validate all 3 LLM providers successfully when API keys are configured
- **SC-007**: Load testing utility can simulate 50 concurrent sessions without system degradation
- **SC-008**: All ad-hoc utilities are removed before any production commit (verified by pre-commit hook)

## Test Categories Overview

### 1. Unit Tests (CI - pytest)

| Test File | Coverage Area | Priority |
|-----------|---------------|----------|
| `tests/unit/api/test_health.py` | Health endpoint | P1 |
| `tests/unit/api/test_sessions.py` | Session CRUD operations | P1 |
| `tests/unit/api/test_steps.py` | Step operations | P1 |
| `tests/unit/api/test_artifacts.py` | Artifact operations | P2 |
| `tests/unit/cli/test_maintenance.py` | Maintenance CLI commands | P1 |
| `tests/unit/cli/test_tests.py` | Test generation CLI | P1 |
| `tests/unit/cli/test_deploy.py` | Deploy CLI commands | P2 |
| `tests/unit/cli/test_config.py` | Config management CLI | P2 |
| `tests/unit/workflows/test_maven_workflow.py` | Maven maintenance workflow states | P1 |
| `tests/unit/workflows/test_test_workflow.py` | Test generation workflow states | P1 |
| `tests/unit/workflows/test_deploy_workflow.py` | Docker deployment workflow | P2 |
| `tests/unit/db/test_models.py` | Database model validation | P1 |
| `tests/unit/db/test_crud.py` | CRUD operations | P1 |
| `tests/unit/core/test_config_reload.py` | Configuration hot-reload | P2 |
| `tests/unit/core/test_error_handling.py` | Error code handling | P1 |

### 2. Integration Tests (CI - pytest)

| Test File | Coverage Area | Prerequisites |
|-----------|---------------|---------------|
| `tests/integration/test_database.py` | PostgreSQL integration | PostgreSQL on port 5433 |
| `tests/integration/test_llm_providers.py` | LLM provider connectivity | Valid API keys |
| `tests/integration/test_docker_deploy.py` | Docker deployment | Docker running |
| `tests/integration/test_mcp_tools.py` | MCP tool invocations | Maven, Git installed |
| `tests/integration/test_git_operations.py` | Git operations | Git repository |

### 3. Manual Tests (Checklist)

| Test ID | Description | Expected Result |
|---------|-------------|-----------------|
| MT-001 | Verify installation with `poetry install` | No errors, all dependencies installed |
| MT-002 | Start PostgreSQL with `docker compose up -d postgres` | Container running, port 5433 accessible |
| MT-003 | Run migrations with `alembic upgrade head` | No errors, schema created |
| MT-004 | Start API with `uvicorn src.api.main:app --reload` | Server running on port 8000 |
| MT-005 | Check health endpoint `GET /health` | `{"status": "healthy", "version": "..."}` |
| MT-006 | Run `python -m src.cli.main maintenance list test-projects/spring-petclinic` | Dependency list displayed |
| MT-007 | Run `python -m src.cli.main tests analyze test-projects/spring-petclinic` | Analysis report generated |
| MT-008 | Run `python -m src.cli.main config validate` | Configuration validation result |
| MT-009 | Verify LLM connectivity on startup | No "LLM not available" errors |
| MT-010 | Test session creation via API | Session ID returned |

### 4. Ad-hoc Test Utilities (Temporary)

| Utility | Purpose | Delete Before Commit |
|---------|---------|----------------------|
| `scripts/test-utils/validate_multi_provider.py` | Test all LLM providers | Yes |
| `scripts/test-utils/load_test_sessions.py` | Concurrent session simulation | Yes |
| `scripts/test-utils/verify_db_state.py` | Database state validation | Yes |
| `scripts/test-utils/benchmark_mcp_tools.py` | MCP tool performance | Yes |
| `scripts/test-utils/template.py` | Template for new utilities | Yes |

## Assumptions

1. **Test Environment**: Tests assume Python 3.11+ is installed with Poetry for dependency management
2. **PostgreSQL**: Integration tests assume PostgreSQL 15 is available on port 5433 (via Docker)
3. **LLM API Keys**: LLM integration tests are skipped if API keys are not configured
4. **Docker**: Docker deployment tests are skipped if Docker is not running
5. **Maven**: MCP tool tests assume Maven 3.6+ is in PATH
6. **Git**: Git operations tests assume execution within a Git repository
7. **Test Projects**: Sample Maven projects are available in `test-projects/` directory
8. **Coverage Thresholds**: Based on industry standards for critical systems (70% line, 60% branch)
9. **Test Duration**: 5-minute target based on typical CI pipeline constraints
10. **Flaky Test Tolerance**: 5% flaky rate is acceptable; tests failing >3 times are quarantined
11. **CI Platform**: GitHub Actions is the target CI environment; workflow files go in `.github/workflows/`

## Out of Scope

- Performance testing beyond basic load simulation (handled by separate performance suite)
- Security penetration testing (handled by security audit)
- UI/UX testing (no frontend in current scope)
- Cross-platform testing (Windows-specific issues handled separately)
- LLM response quality evaluation (handled by separate evaluation suite)
