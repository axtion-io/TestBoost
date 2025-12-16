# Tasks: Requirements Gap Resolution

**Input**: Consolidated checklist gaps from `/specs/001-testboost-core/checklists/consolidated.md`
**Purpose**: Address 27 identified gaps to achieve 100% requirements quality
**Organization**: Tasks grouped by priority (High, Medium, Low) then by category

## Format: `[ID] [P?] [Category] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Category]**: Domain category (Doc, Code, Test, Infra)

## Path Conventions

- Documentation: `docs/` or inline in existing files
- Source: `src/`
- Tests: `tests/`
- Config: `config/`

---

## Phase 1: High Priority (Critical Gaps)

**Purpose**: Address gaps that impact production readiness and compliance

### Data Lifecycle

- [x] T001 [Code] Implement session purge job in src/db/jobs/purge.py (DONE - already implemented)
  - Create scheduled job to delete sessions older than 1 year
  - Add configuration for retention period in config/settings.py
  - Log purge operations with count of deleted sessions
  - Reference: Spec §FR-044

- [x] T002 [P] [Test] Create tests/unit/test_session_purge.py (DONE - 12 tests)
  - test_purge_deletes_old_sessions()
  - test_purge_preserves_recent_sessions()
  - test_purge_handles_empty_database()
  - test_purge_logs_deletion_count()

- [x] T003 [Infra] Add purge job to scheduler in src/db/jobs/scheduler.py (DONE - already implemented)
  - Configure APScheduler or similar for daily purge
  - Add health check for job status

### Performance Testing

- [x] T004 [Test] Create tests/performance/test_benchmarks.py (DONE - 6 tests)
  - test_interactive_operation_under_5_seconds()
  - test_docker_deployment_under_5_minutes()
  - test_analysis_200_classes_under_30_seconds()
  - Reference: Spec §SC-001, §SC-002, §SC-003

- [x] T005 [P] [Test] Create tests/performance/test_load.py (DONE - 9 tests)
  - test_concurrent_session_handling()
  - test_memory_usage_under_load()
  - test_database_connection_pool()

- [x] T006 [P] [Infra] Add pytest-benchmark to pyproject.toml (DONE)
  - Configure benchmark storage for regression tracking
  - Add CI step for performance tests (optional, non-blocking)

**Checkpoint**: Session purge implemented, performance baselines established

---

## Phase 2: Medium Priority - Documentation (8 tasks)

**Purpose**: Improve specification clarity and completeness

### MCP Tools Documentation

- [x] T007 [P] [Doc] Create docs/mcp-tools-reference.md (DONE)
  - Document each MCP tool with inputs/outputs
  - Include Pydantic schema definitions
  - Add example invocations
  - Reference: CHK002 gap

### Workflow Documentation

- [x] T008 [P] [Doc] Create docs/workflow-diagrams.md (DONE)
  - Add Mermaid diagrams for Maven, Test Gen, Docker workflows
  - Show state transitions and decision points
  - Reference: CHK010, CHK011 gaps

- [x] T009 [P] [Doc] Document baseline test strategy in docs/testing-strategy.md (DONE)
  - Define "baseline tests must pass" requirement
  - Specify what constitutes a passing baseline
  - Reference: CHK016 gap

- [x] T010 [P] [Doc] Document flaky test handling in docs/testing-strategy.md (DONE)
  - Define flaky test detection criteria
  - Specify handling strategy (retry, skip, flag)
  - Reference: CHK017 gap

### API Documentation

- [x] T011 [Code] OpenAPI spec already configured in FastAPI main.py (DONE - /openapi.json)
  - Add endpoint to serve openapi.json
  - Configure FastAPI to export spec on startup
  - Reference: CHK020 gap

- [x] T012 [P] [Doc] Document HTTP error codes in docs/api-errors.md (DONE)
  - List all endpoints with possible error codes
  - Include error response schemas
  - Reference: CHK021 gap

- [x] T013 [P] [Doc] Document CLI exit codes in docs/cli-reference.md (DONE)
  - Define semantic exit codes (0=success, 1=error, 2=config, etc.)
  - Update CLI to use consistent codes
  - Reference: CHK023 gap

### Database Documentation

- [x] T014 [P] [Doc] Create docs/database-schema.md (DONE)
  - Document index strategy for performance
  - Document CASCADE policies
  - Document validation constraints
  - Reference: CHK031, CHK033, CHK034 gaps

**Checkpoint**: Documentation gaps addressed, specs are complete

---

## Phase 3: Medium Priority - Code (6 tasks)

**Purpose**: Implement missing functionality

### API Pagination

- [x] T015 [Code] Pagination already implemented in src/api/routers/sessions.py (DONE)
  - Add page, page_size query parameters
  - Return pagination metadata (total, pages, current)
  - Reference: CHK026 gap

- [x] T016 [P] [Test] Add pagination tests in tests/integration/test_api_pagination.py (DONE - 18 tests)
  - test_session_list_pagination()
  - test_artifact_list_pagination()
  - test_pagination_edge_cases()

### Observability

- [x] T017 [Code] Add Prometheus metrics endpoint in src/api/routers/metrics.py (DONE)
  - Expose workflow_duration_seconds histogram
  - Expose llm_calls_total counter
  - Expose active_sessions gauge
  - Reference: CHK042 gap

- [x] T018 [P] [Infra] Built-in metrics collector (no external dep needed) (DONE)
  - Configure metrics registry
  - Add /metrics endpoint

### Reliability

- [x] T019 [Code] Add explicit timeouts for all external calls in src/lib/http_client.py (DONE)
  - Create wrapper for httpx with configurable timeouts
  - Apply to all external API calls
  - Reference: CHK047 gap

- [x] T020 [P] [Code] Implement DB reconnection strategy in src/lib/database.py (DONE)
  - Add retry logic for transient DB errors
  - Configure connection pool recovery
  - Reference: CHK048 gap

**Checkpoint**: Core functionality gaps resolved

---

## Phase 4: Medium Priority - Configuration (4 tasks)

**Purpose**: Make system more configurable

### Workflow Configuration

- [x] T021 [P] [Code] Make Maven test timeout configurable in config/agents/maven_maintenance_agent.yaml (DONE)
  - Add test_timeout_seconds field
  - Update workflow to use config value
  - Reference: CHK015 gap

### Performance Thresholds

- [x] T022 [P] [Doc] Define degradation thresholds in docs/operations.md (DONE)
  - Define acceptable performance degradation levels
  - Document alerting thresholds
  - Reference: CHK038 gap

- [x] T023 [P] [Doc] Document load testing requirements in docs/operations.md (DONE)
  - Define expected concurrent users
  - Document resource requirements per scale
  - Reference: CHK039 gap

### Service Assumptions

- [x] T024 [P] [Doc] Document service availability assumptions in docs/dependencies.md (DONE)
  - List all external services with SLA expectations
  - Define fallback behavior when services degrade
  - Reference: CHK078, CHK079 gaps

**Checkpoint**: Configuration and operational docs complete

---

## Phase 5: Low Priority - Documentation Polish (10 tasks)

**Purpose**: Complete documentation for full coverage

### MCP Tools

- [x] T025 [P] [Doc] Document MCP tool timeouts in docs/mcp-tools-reference.md (DONE - already included)
  - Add timeout per tool category
  - Reference: CHK006 gap

### Workflows

- [x] T026 [P] [Doc] Document circular dependency handling in docs/maven-maintenance.md (DONE)
  - Explain how `mvn dependency:tree` detects cycles
  - Define user notification strategy
  - Reference: CHK018 gap

### API

- [x] T027 [P] [Doc] Document X-API-Key format in docs/api-authentication.md (DONE)
  - Specify format requirements
  - Document validation rules
  - Reference: CHK024 gap

### Isolation

- [x] T028 [P] [Doc] Document container resource limits in docs/docker-isolation.md (DONE)
  - Specify memory/CPU limits for Maven containers
  - Reference: CHK052 gap

- [x] T029 [P] [Doc] Document container cleanup policy in docs/docker-isolation.md (DONE)
  - Define container lifecycle and cleanup triggers
  - Reference: CHK053 gap

### Test Generation

- [x] T030 [P] [Doc] Document test quality scoring formula in docs/test-generation.md (DONE)
  - Break down 0-120 scoring components
  - Reference: CHK057 gap

- [x] T031 [P] [Doc] Define cyclomatic complexity threshold in docs/test-generation.md (DONE)
  - Specify max complexity for auto-generated tests
  - Define handling for complex classes
  - Reference: CHK061 gap

- [x] T032 [P] [Doc] Document external mock generation in docs/test-generation.md (DONE)
  - Specify Mockito patterns
  - Define external service mock strategy
  - Reference: CHK062 gap

### Traceability

- [x] T033 [P] [Doc] Create FR-to-Constitution traceability matrix in docs/traceability.md (DONE)
  - Map each FR to constitution principles
  - Document any violations with justification
  - Reference: CHK072, CHK073 gaps

### Snapshot Tests

- [x] T034 [P] [Doc] Document ApprovalTests snapshot pattern in docs/test-generation.md (DONE)
  - Specify snapshot file format
  - Document approval workflow
  - Reference: CHK060 gap

**Checkpoint**: All documentation complete, 100% requirements coverage

---

## Phase 6: Implementation Gaps - Placeholder Functions (4 tasks)

**Purpose**: Replace placeholder implementations with real functionality
**Priority**: High - Required for full E2E testing capability
**Discovered**: Code scan on 2024-12-10

### Test Generation Workflow

- [x] T035 [Code] Implement real Docker deployment in src/workflows/test_generation.py:deploy_docker (DONE)
  - Use container_runtime MCP tools (already available)
  - Deploy application using docker-compose
  - Return actual container status
  - Reference: Placeholder at line 438

- [x] T036 [Code] Implement real health check in src/workflows/test_generation.py:check_app_health (DONE)
  - Use docker health MCP tool
  - Wait for container health (max 120s)
  - Return actual health status from container
  - Reference: Placeholder at line 458

- [x] T037 [Code] Implement E2E test generation in src/workflows/test_generation.py:generate_e2e_tests (DONE)
  - Analyze project endpoints from OpenAPI/annotations
  - Generate REST-assured or WebTestClient tests
  - Use LLM agent for test logic generation
  - Reference: Placeholder at line 478

### Maven Maintenance Workflow

- [x] T038 [Code] Implement real release notes fetching in src/workflows/maven_maintenance.py:fetch_release_notes (DONE)
  - Fetch from Maven Central metadata
  - Parse GitHub releases API for common packages
  - Extract breaking changes from CHANGELOG files
  - Reference: Placeholder at line 240

### Code Quality Fixes (Minor)

- [x] T039 [P] [Code] Remove unused variables identified by vulture (DONE)
  - src/cli/commands/maintenance.py:227 - unused 'watch' → prefixed with _
  - src/lib/database.py:238 - unused 'exc_tb' → prefixed with _
  - src/lib/http_client.py:274 - unused 'exc_tb' → prefixed with _

**Checkpoint**: All placeholder functions replaced with real implementations ✅

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (High)**: No dependencies - start immediately
- **Phase 2 (Medium-Doc)**: Can run in parallel with Phase 1
- **Phase 3 (Medium-Code)**: Can start after Phase 1 complete
- **Phase 4 (Medium-Config)**: Can run in parallel with Phase 3
- **Phase 5 (Low)**: Can start anytime, lowest priority
- **Phase 6 (High)**: Depends on Phase 3 (uses MCP tools) - CURRENT PRIORITY

### Parallel Opportunities

| Phase | Parallel Tasks |
|-------|---------------|
| Phase 1 | T002, T005, T006 |
| Phase 2 | T007-T014 (all [P]) |
| Phase 3 | T016, T018, T020 |
| Phase 4 | T021-T024 (all [P]) |
| Phase 5 | T025-T034 (all [P]) |
| Phase 6 | T035-T037 (same workflow), T039 |

**Maximum parallelization**: 8 tasks simultaneously in Phase 2

---

## Implementation Strategy

### MVP First (Phase 1 Only)

1. Complete T001-T003: Session purge job
2. Complete T004-T006: Performance tests
3. **STOP and VALIDATE**: Run purge job, verify performance baselines
4. Critical gaps resolved, production-ready

### Incremental Delivery

1. **Phase 1** → High priority gaps → Critical for production ✅ DONE
2. **Phase 2** → Documentation → Enables onboarding ✅ DONE
3. **Phase 3** → Code features → Improves usability ✅ DONE
4. **Phase 4** → Configuration → Enables ops team ✅ DONE
5. **Phase 5** → Polish → Complete coverage ✅ DONE
6. **Phase 6** → Placeholder implementations → Full E2E capability ✅ DONE

### Suggested Sprint Allocation

| Sprint | Phases | Focus |
|--------|--------|-------|
| Sprint 1 | Phase 1 | Critical gaps ✅ |
| Sprint 2 | Phase 2 + 3 | Medium priority ✅ |
| Sprint 3 | Phase 4 + 5 | Low priority + polish ✅ |
| Sprint 4 | Phase 6 | Implementation gaps ✅ |

---

## Summary

| Priority | Tasks | Effort | Impact | Status |
|----------|-------|--------|--------|--------|
| High | 6 | ~8h | Production readiness | ✅ DONE |
| Medium (Doc) | 8 | ~4h | Spec completeness | ✅ DONE |
| Medium (Code) | 6 | ~6h | Functionality | ✅ DONE |
| Medium (Config) | 4 | ~2h | Operations | ✅ DONE |
| Low | 10 | ~4h | Polish | ✅ DONE |
| **High (New)** | **5** | **~6h** | **Full E2E capability** | **✅ DONE** |
| **TOTAL** | **39** | **~30h** | **100% coverage** | **39/39 (100%)** |

---

## Checklist Mapping

| Task | Resolves CHK | Issue ID |
|------|--------------|----------|
| T001-T003 | CHK036 | ISS-016 |
| T004-T006 | CHK037, CHK038 | ISS-017 |
| T007 | CHK002 | ISS-001 |
| T008 | CHK010, CHK011 | ISS-002, ISS-003 |
| T009 | CHK016 | ISS-005 |
| T010 | CHK017 | ISS-006 |
| T011-T012 | CHK020, CHK021 | ISS-008, ISS-009 |
| T013 | CHK023 | ISS-010 |
| T014 | CHK031, CHK033, CHK034 | ISS-013, ISS-014, ISS-015 |
| T015-T016 | CHK026 | ISS-012 |
| T017-T018 | CHK042 | ISS-020 |
| T019 | CHK047 | ISS-021 |
| T020 | CHK048 | ISS-022 |
| T021 | CHK015 | ISS-004 |
| T022 | CHK038 | ISS-018 |
| T023 | CHK039 | ISS-019 |
| T024 | CHK078, CHK079 | - |
| T025 | CHK006 | - |
| T026 | CHK018 | ISS-007 |
| T027 | CHK024 | ISS-011 |
| T028-T029 | CHK052, CHK053 | ISS-023, ISS-024 |
| T030 | CHK057 | ISS-025 |
| T031 | CHK061 | ISS-026 |
| T032 | CHK062 | - |
| T033 | CHK072, CHK073 | ISS-027 |
| T034 | CHK060 | - |

All 27 issues from consolidated.md are addressed.
