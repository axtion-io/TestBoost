# Tasks: Simplify TestBoost to Lite CLI Architecture

**Input**: Design documents from `/specs/001-simplify-testboost/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, quickstart.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Verify current branch and run baseline smoke test before any removal

- [x] T001 Confirm active branch is `001-simplify-testboost` (`git branch --show-current`)
- [x] T002 Run baseline smoke test: `python -m testboost_lite --help` must list 6 commands (init, analyze, gaps, generate, validate, status) — record output as baseline

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Audit `src/core/`, `src/agents/`, `src/workflows/state.py` for SQLAlchemy/API imports so later deletions don't cause unresolved reference errors in kept modules

**⚠️ CRITICAL**: Results determine which additional directories must be deleted in Phase 3

- [x] T003 Audit `src/core/` — grep for `fastapi`, `sqlalchemy`, `asyncpg`, `src.db`, `src.api` imports; document which files in `src/core/` are safe to delete vs. needed by `testboost_lite`
- [x] T004 Audit `src/agents/adapter.py` and `src/agents/loader.py` — grep for `fastapi`, `sqlalchemy`, `src.db`, `src.api` imports; document findings
- [x] T005 Audit `src/workflows/state.py` — grep for `sqlalchemy`, `src.db` imports; document findings
- [x] T006 Audit `src/lib/startup_checks.py` — identify the `check_llm_connection()` function (called by `testboost_lite/lib/cli.py:393`) and identify any database connectivity check to remove
- [x] T007 Audit `src/lib/config.py` — identify all Pydantic Settings fields that reference `DATABASE_URL`, `API_KEY`, `API_HOST`, `API_PORT`, `DOCKER_HOST`, `MAVEN_CACHE_PATH`, `SESSION_RETENTION_DAYS`, `PROJECT_LOCK_TIMEOUT_SECONDS`; confirm which have defaults vs. are required

**Checkpoint**: Audit complete — all removal targets confirmed, no kept module has hidden DB/API dependencies

---

## Phase 3: User Story 1 — Run CLI Without Legacy Infrastructure (Priority: P1) 🎯 MVP

**Goal**: `python -m testboost_lite <command>` works on a machine with no database or Docker, and `poetry install` no longer installs legacy packages.

**Independent Test**: `python -m testboost_lite --help` lists 6 commands without ImportError; `poetry show | grep -E "fastapi|sqlalchemy|asyncpg|uvicorn|alembic"` returns empty.

### Implementation for User Story 1

- [x] T008 [US1] Delete `src/api/` directory entirely (FastAPI app, middleware, routers, models) — 35+ files
- [x] T009 [US1] Delete `src/cli/` directory entirely (old Typer CLI with uvicorn serve command)
- [x] T010 [US1] Delete `src/db/` directory entirely (SQLAlchemy models, repository, migrations, jobs)
- [x] T011 [US1] Delete `alembic.ini` at repository root
- [x] T012 [US1] Delete `src/lib/database.py` (SQLAlchemy engine + asyncpg setup)
- [x] T013 [US1] Delete `src/core/` directory — confirmed safe per T003 audit (if NOT safe: delete only files with DB/API imports, keep others)
- [x] T014 [US1] Remove `startup_checks.py` database connectivity check identified in T006 audit; keep `check_llm_connection()` intact in `src/lib/startup_checks.py`
- [x] T015 [US1] Remove Pydantic Settings fields from `src/lib/config.py`: `DATABASE_URL`, `API_KEY`, `API_HOST`, `API_PORT`, `DOCKER_HOST`, `MAVEN_CACHE_PATH`, `SESSION_RETENTION_DAYS`, `PROJECT_LOCK_TIMEOUT_SECONDS` (identified in T007 audit)
- [x] T016 [US1] Update `pyproject.toml`: remove `fastapi`, `uvicorn`, `sqlalchemy`, `alembic`, `asyncpg` from `[tool.poetry.dependencies]`; remove `psycopg2-binary` from `[tool.poetry.group.dev.dependencies]`; remove `[tool.poetry.scripts]` entry `boost = "src.cli.main:app"`; update `description` to "AI-powered Java test generation CLI (TestBoost Lite)"; set `fail_under = 0` in `[tool.coverage.report]`; update `addopts` in `[tool.pytest.ini_options]` to remove `--cov=src` flags
- [x] T017 [US1] Run `poetry install` and verify it completes without error; run `poetry show | grep -E "fastapi|sqlalchemy|asyncpg|uvicorn|alembic"` and confirm empty output
- [x] T018 [US1] Run smoke test: `python -m testboost_lite --help` — must list all 6 commands without ImportError

**Checkpoint**: US1 complete — `python -m testboost_lite` works, legacy packages gone from `pyproject.toml`

---

## Phase 4: User Story 2 — Clean Environment Configuration (Priority: P2)

**Goal**: `.env.example` contains only LLM provider, proxy/SSL, and logging variables — no database, API server, or Docker entries.

**Independent Test**: Count of variables in new `.env.example` is ≤ 14 (half of original ~28); grep for `DATABASE_URL`, `API_KEY`, `API_HOST`, `API_PORT`, `DOCKER_HOST` returns empty.

### Implementation for User Story 2

- [x] T019 [US2] Rewrite `.env.example`: remove `DATABASE_URL`, `API_KEY`, `API_HOST`, `API_PORT`, `DOCKER_HOST`, `MAVEN_CACHE_PATH`, `SESSION_RETENTION_DAYS`, `PROJECT_LOCK_TIMEOUT_SECONDS`; keep all LLM, proxy/SSL, LangSmith, logging variables as documented in `data-model.md` Environment Variables table
- [x] T020 [US2] Verify `.env.example` smoke test: copy to `.env.test`, run `python -m testboost_lite status /nonexistent 2>&1` — must fail with a "not found" or usage error, NOT a Pydantic `ValidationError` about missing env vars

**Checkpoint**: US2 complete — `.env.example` is clean; settings load without DB/API errors

---

## Phase 5: User Story 3 — No Dead Imports in Internal Modules (Priority: P3)

**Goal**: Static scan of `testboost_lite/` and `src/mcp_servers/` finds zero imports of removed packages; Docker-related MCP servers are deleted.

**Independent Test**: `grep -r "fastapi\|sqlalchemy\|asyncpg\|uvicorn\|alembic" testboost_lite/ src/mcp_servers/ src/lib/ src/agents/ src/workflows/` returns zero matches.

### Implementation for User Story 3

- [x] T021 [P] [US3] Delete `src/mcp_servers/docker/` directory (Docker Compose MCP tools)
- [x] T022 [P] [US3] Delete `src/mcp_servers/container_runtime/` directory (container execution MCP tools)
- [x] T023 [US3] Delete `src/workflows/docker_deployment_agent.py`
- [x] T024 [US3] Update `src/mcp_servers/registry.py`: remove any registration or import of `docker` and `container_runtime` MCP servers; keep `test_generator`, `maven_maintenance`, `git_maintenance`, `pit_recommendations`
- [x] T025 [US3] Run import check: `python -c "from src.mcp_servers.registry import *"` — must succeed without ImportError
- [x] T026 [US3] Run static scan: `grep -r "fastapi\|sqlalchemy\|asyncpg\|uvicorn\|alembic\|docker" testboost_lite/ src/mcp_servers/ src/lib/ src/agents/ src/workflows/` — must return zero matches (excluding deleted directories)
- [x] T027 [US3] Delete `src/agents/` if T004 audit showed it only imports from removed modules; otherwise verify `python -c "from src.agents import adapter, loader"` succeeds

**Checkpoint**: US3 complete — zero dead imports across all kept modules

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Delete root-level Docker/infrastructure files, clean up legacy test files, run full validation

- [x] T028 [P] Delete root-level Docker files: `Dockerfile`, `docker-compose.yaml`, `docker-compose.monitoring.yaml`, and the `docker/` utility directory
- [x] T029 [P] Delete legacy test directories: `tests/api/`, `tests/unit/api/`, `tests/unit/db/`, `tests/unit/cli/`, `tests/unit/workflows/test_deploy_workflow.py`
- [x] T030 [P] Delete `scripts/` utility files that reference removed infrastructure: `scripts/test-utils/api_tester.py`, `scripts/test-utils/db_inspector.py`, `scripts/test-utils/smoke_test.py` (verify before deleting — check for references to removed packages)
- [x] T031 Run surviving unit tests: `pytest tests/unit/test_maven_error_parser.py -v` — all 15 tests must pass
- [x] T032 Run full end-to-end smoke test: `python -m testboost_lite init test-projects/BankApp && python -m testboost_lite status test-projects/BankApp` — must create `.testboost/` session files without errors
- [x] T033 Run final static import scan across all non-deleted source directories — zero matches for removed packages
- [x] T034 Update `pyproject.toml` `packages` field: verify `packages = [{include = "src"}]` is still valid (src/ directory still exists with mcp_servers, lib, workflows, models); update if needed
- [x] T035 Commit all changes with message: `refactor: migrate to TestBoost Lite CLI — remove FastAPI, SQLAlchemy, asyncpg, Docker`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational Audit)**: Depends on Phase 1 — audit results gate all deletions
- **Phase 3 (US1 — CLI)**: Depends on Phase 2 audit — T003/T006/T007 results determine exact scope of T013/T014/T015
- **Phase 4 (US2 — Env)**: Depends on Phase 3 (T015 removes config fields; T019 must match)
- **Phase 5 (US3 — Imports)**: Depends on Phase 3 (T008/T009/T010 must be done before import scan)
- **Phase 6 (Polish)**: Depends on US1 + US2 + US3 completion

### User Story Dependencies

- **US1 (P1)**: Critical path — blocks US2 (config) and US3 (import scan)
- **US2 (P2)**: Depends on US1 (config.py changes must be done)
- **US3 (P3)**: Can start parallel with US2 after US1 completes (different files)

### Parallel Opportunities within US1

```bash
# T008, T009, T010, T011, T012 can run in parallel (different directories):
Task: "Delete src/api/"
Task: "Delete src/cli/"
Task: "Delete src/db/"
Task: "Delete alembic.ini"
Task: "Delete src/lib/database.py"
```

### Parallel Opportunities within Phase 6

```bash
# T028, T029, T030 can run in parallel (different directories):
Task: "Delete root-level Docker files"
Task: "Delete legacy test directories"
Task: "Delete legacy script utilities"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Baseline smoke test
2. Complete Phase 2: Audit (10–15 min, non-destructive)
3. Complete Phase 3: US1 — delete legacy infrastructure, clean `pyproject.toml`
4. **STOP and VALIDATE**: `python -m testboost_lite --help` works; `poetry install` clean
5. US1 is independently testable and delivers the core value

### Incremental Delivery

1. Phase 1 + 2 → Audit complete, no code changed
2. Phase 3 → `python -m testboost_lite` works without DB/Docker (US1 done)
3. Phase 4 → `.env.example` clean (US2 done)
4. Phase 5 → No dead imports (US3 done)
5. Phase 6 → All Docker files gone, tests clean, commit

---

## Notes

- [P] tasks = different files, no dependencies on each other
- All deletions are on branch `001-simplify-testboost` — main is untouched
- T003–T007 audit tasks are non-destructive — read-only grep operations
- T013, T027 have conditional logic based on audit results (T003, T004)
- `greenlet` stays in `pyproject.toml` — used by LangGraph, not just SQLAlchemy
- Do NOT touch `test-projects/` — BankApp's own docker-compose is separate
- After T035 commit, open a PR from `001-simplify-testboost` → `main`
