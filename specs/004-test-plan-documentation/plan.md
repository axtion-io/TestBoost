# Implementation Plan: Complete Test Plan for TestBoost

**Branch**: `004-test-plan-documentation` | **Date**: 2026-01-04 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/004-test-plan-documentation/spec.md`

## Summary

Implement a comprehensive test plan for TestBoost covering 4 test categories:
1. **CI Tests** (pytest): Unit and integration tests for API, CLI, workflows, database
2. **Manual Tests**: Installation verification checklist (10 items)
3. **Ad-hoc Utilities**: Temporary Python scripts for load testing, multi-provider validation
4. **Integration Tests**: PostgreSQL, LLM providers, Docker, MCP tools

Technical approach: pytest with fixtures for mocking (LLM JSON fixtures, transaction rollback for DB), GitHub Actions CI pipeline, pytest-cov for coverage.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pytest, pytest-asyncio, pytest-cov, pytest-xdist, httpx (for API testing), respx (for HTTP mocking)
**Storage**: PostgreSQL 15 (port 5433) - existing schema, no changes needed
**Testing**: pytest with pytest-asyncio for async tests, pytest-cov for coverage
**Target Platform**: GitHub Actions standard runner (2 vCPU, 7GB RAM, ubuntu-latest)
**Project Type**: Single project (existing structure in `src/`, `tests/`)
**Performance Goals**: All CI tests < 5 minutes, 70% line coverage, 60% branch coverage
**Constraints**: Transaction rollback isolation, LLM mocks via JSON fixtures, no real API calls in unit tests
**Scale/Scope**: 15 unit test files, 5 integration test files, 10 manual test items, 5 ad-hoc utilities

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| 1. Zéro Complaisance | PASS | Tests report real failures, no fake success |
| 2. Outils via MCP | PASS | MCP tools tested via integration tests |
| 3. Pas de Mocks en Production | PASS | Mocks only for dev tests, not user-facing |
| 4. Automatisation avec Contrôle | PASS | CI runs automatically, manual tests documented |
| 5. Traçabilité Complète | PASS | Test reports with coverage, JUnit XML output |
| 6. Validation Avant Modification | PASS | Pre-commit hook for ad-hoc cleanup |
| 7. Isolation et Sécurité | PASS | Transaction rollback, branch isolation |
| 8. Découplage et Modularité | PASS | Tests organized by module (api, cli, workflows, db) |
| 9. Transparence des Décisions | PASS | Clear error messages in test failures |
| 10. Robustesse et Tolérance | PASS | Retry logic for flaky integration tests |
| 11. Performance Raisonnable | PASS | 5-minute target, parallel execution |
| 12. Respect des Standards | PASS | Uses existing pytest structure |
| 13. Simplicité d'Utilisation | PASS | `pytest tests/` runs everything |

**Gate Status**: PASS - All principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/004-test-plan-documentation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (test contracts)
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
tests/
├── unit/
│   ├── api/
│   │   ├── test_health.py
│   │   ├── test_sessions.py
│   │   ├── test_steps.py
│   │   └── test_artifacts.py
│   ├── cli/
│   │   ├── test_maintenance.py
│   │   ├── test_tests.py
│   │   ├── test_deploy.py
│   │   └── test_config.py
│   ├── workflows/
│   │   ├── test_maven_workflow.py
│   │   ├── test_test_workflow.py
│   │   └── test_deploy_workflow.py
│   ├── db/
│   │   ├── test_models.py
│   │   └── test_crud.py
│   └── core/
│       ├── test_config_reload.py
│       └── test_error_handling.py
├── integration/
│   ├── test_database.py
│   ├── test_llm_providers.py
│   ├── test_docker_deploy.py
│   ├── test_mcp_tools.py
│   └── test_git_operations.py
├── fixtures/
│   ├── llm_responses/           # JSON fixtures for LLM mocking
│   │   ├── gemini_responses.json
│   │   ├── claude_responses.json
│   │   └── openai_responses.json
│   └── test_projects/           # Sample Maven project data
│       └── sample_pom.xml
├── conftest.py                  # Shared fixtures (db_session, mock_llm, etc.)
└── pytest.ini                   # pytest configuration

scripts/
└── test-utils/                  # Ad-hoc utilities (gitignored)
    ├── validate_multi_provider.py
    ├── load_test_sessions.py
    ├── verify_db_state.py
    ├── benchmark_mcp_tools.py
    └── template.py

.github/
└── workflows/
    └── tests.yml                # GitHub Actions CI workflow

docs/
└── manual-test-checklist.md     # Manual testing documentation
```

**Structure Decision**: Single project structure, extending existing `tests/` directory with organized subdirectories by test type and module.

## Complexity Tracking

> No violations - all principles satisfied without exceptions.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | - | - |
