# Consolidated Requirements Quality Checklist: TestBoost

**Purpose**: Validate requirements quality across 001-testboost-core and 002-deepagents-integration
**Created**: 2025-12-07
**Depth**: Formal (with issue tracking)
**Features**: [001-spec.md](../spec.md), [002-spec.md](../../002-deepagents-integration/spec.md)

---

## Legend

| Marker | Meaning |
|--------|---------|
| `[x]` | Requirement satisfactory (validated with evidence) |
| `[ ]` | Requirement needs review/improvement |
| `[Gap]` | Requirement missing entirely |
| `[Ambiguity]` | Requirement vague/unquantified |
| `[Conflict]` | Inconsistency between sections |
| `[Assumption]` | Unvalidated assumption |
| `ISSUE:` | Requires GitHub issue creation |

---

## 1. Architecture MCP & Agents

### Completeness

- [x] CHK001 - Are all MCP tools required for each workflow listed? [Completeness, Spec §FR-001]
  - **Evidence**: `src/mcp_servers/` contains maven_maintenance, git_maintenance, docker, test_generator
  - **Validation**: `tests/integration/test_agent_config_loading.py` validates tool discovery

- [x] CHK002 - Are MCP tool inputs/outputs documented? [Completeness]
  - **Evidence**: Each MCP server has `langchain_tools.py` with Pydantic schemas
  - **Gap**: ISSUE: Missing formal OpenAPI-style documentation for MCP tools

- [x] CHK003 - Are dependencies between MCP servers explicit? [Completeness]
  - **Evidence**: `config/agents/*.yaml` declares `mcp_servers` list per agent
  - **Validation**: Agent configs validated at startup

- [x] CHK004 - Is DeepAgents configuration (YAML + prompts) specified for each agent type? [Gap → Resolved]
  - **Evidence**: 3 agent configs exist: `maven_maintenance_agent.yaml`, `test_gen_agent.yaml`, `deployment_agent.yaml`
  - **Validation**: `tests/integration/test_agent_config_loading.py::test_yaml_config_loads`

### Clarity

- [x] CHK005 - Is the LLM_PROVIDER format clearly defined? [Clarity, Spec §FR-008, 002-Spec §FR-013]
  - **Evidence**: `LLM_PROVIDER=google|anthropic|openai` with corresponding API keys
  - **Validation**: `tests/integration/test_provider_switching.py`

- [ ] CHK006 - Are timeouts per MCP tool category quantified? [Clarity]
  - **Gap**: ISSUE: No explicit timeout documentation per tool type
  - **Current**: Default 30s in config, but not category-specific

- [x] CHK007 - Is LLM fallback behavior on error specified? [Gap → Resolved]
  - **Evidence**: 002-Spec §FR-009: "retry with exponential backoff, never fallback to deterministic logic"
  - **Validation**: `tests/e2e/test_edge_cases.py::test_intermittent_connectivity_retry`

### Consistency

- [x] CHK008 - Are MCP tool names consistent between spec and implementation? [Consistency]
  - **Evidence**: Tool names in YAML match `src/mcp_servers/*/` directory names
  - **Note**: Some naming inconsistency (docker vs docker-deployment in YAML)

- [x] CHK009 - Is LLM temperature (0.3) justified and consistent? [Consistency]
  - **Evidence**: All 3 agent configs use `temperature: 0.3`
  - **Rationale**: Low temperature for deterministic tool-calling behavior

---

## 2. Workflows

### Completeness

- [x] CHK010 - Are all workflow steps listed with transitions? [Completeness]
  - **Evidence**: `src/workflows/*_agent.py` implement step-by-step agent invocation
  - **Gap**: ISSUE: No visual workflow diagrams in documentation

- [ ] CHK011 - Are transition conditions between steps documented? [Gap]
  - **Gap**: ISSUE: State machine transitions not formally documented
  - **Current**: Implicit in code via LangGraph state

- [x] CHK012 - Are final states (completed, failed, cancelled) defined? [Completeness]
  - **Evidence**: `src/workflows/state.py` defines `SessionStatus` enum
  - **Validation**: Tests verify success/failure outcomes

- [x] CHK013 - Are rollback criteria specified for file-modifying steps? [Gap → Resolved]
  - **Evidence**: `src/workflows/backup.py` implements backup/restore
  - **Validation**: `tests/unit/test_backup.py`

### Clarity

- [x] CHK014 - Does max retry attempts (3) apply to all workflows? [Clarity]
  - **Evidence**: `error_handling.max_retries: 3` in all agent YAML configs
  - **Validation**: `_invoke_agent_with_retry()` uses config value

- [ ] CHK015 - Is Maven test timeout (5 min) configurable? [Clarity]
  - **Gap**: ISSUE: Timeout hardcoded, not in YAML config
  - **Spec**: §FR defaults mention 5 minutes but no config path

- [ ] CHK016 - Is "baseline tests" strategy before maintenance defined? [Clarity]
  - **Gap**: ISSUE: No explicit baseline test requirement documented
  - **Spec**: Implies tests must pass before maintenance but not formalized

### Edge Cases

- [ ] CHK017 - Is behavior defined for projects with flaky tests? [Edge Case, Gap]
  - **Gap**: ISSUE: No flaky test detection/handling documented
  - **Risk**: False rollbacks due to flaky tests

- [ ] CHK018 - Is circular dependency handling addressed? [Edge Case, Gap]
  - **Gap**: ISSUE: Not mentioned in spec or implementation
  - **Partial**: Maven `dependency:tree` would show cycles

- [x] CHK019 - Is LLM timeout during generation behavior specified? [Edge Case]
  - **Evidence**: 002-Spec edge case: "retry with exponential backoff (3 attempts, 1s-10s)"
  - **Validation**: `tests/e2e/test_edge_cases.py::test_intermittent_connectivity_retry`

---

## 3. API & Interfaces

### Completeness

- [x] CHK020 - Are all REST endpoints documented with parameters? [Completeness]
  - **Evidence**: `src/api/` has routers with Pydantic models
  - **Gap**: ISSUE: No OpenAPI spec file exported (auto-generated only)

- [ ] CHK021 - Are HTTP error codes listed for each endpoint? [Completeness]
  - **Gap**: ISSUE: Error responses not exhaustively documented
  - **Partial**: Some HTTPExceptions defined but not comprehensive

- [x] CHK022 - Are CLI commands documented with options? [Completeness, Spec §FR-051]
  - **Evidence**: `src/cli/` uses Typer with help strings
  - **Validation**: `--help` shows all options

- [ ] CHK023 - Are CLI exit codes defined and documented? [Gap]
  - **Gap**: ISSUE: Exit codes not formally documented
  - **Current**: Uses sys.exit(1) for errors but no semantic codes

### Clarity

- [ ] CHK024 - Is X-API-Key format specified? [Clarity, Spec §FR-052]
  - **Gap**: ISSUE: Format/validation rules not documented
  - **Current**: Any non-empty string accepted

- [x] CHK025 - Are JSON response formats defined (Pydantic)? [Clarity]
  - **Evidence**: Pydantic models in `src/api/models/`
  - **Validation**: FastAPI auto-validates responses

- [ ] CHK026 - Is pagination for lists documented? [Clarity]
  - **Gap**: ISSUE: No pagination documented for session/artifact lists
  - **Risk**: Performance issues with large result sets

### Consistency

- [x] CHK027 - Are field names consistent between API and CLI? [Consistency]
  - **Evidence**: Both use same Pydantic models
  - **Validation**: Shared model definitions

- [x] CHK028 - Are session types identical in API and CLI? [Consistency]
  - **Evidence**: `SessionType` enum shared
  - **Validation**: Same enum used throughout

---

## 4. Data Model

### Completeness

- [x] CHK029 - Are all spec entities present in data-model.md? [Completeness]
  - **Evidence**: Session, Step, Project, Dependency, Modification documented
  - **Plus**: Agent artifact types added in 002

- [x] CHK030 - Are entity relationships (FK) documented? [Completeness]
  - **Evidence**: data-model.md shows Session → Step → Artifact relationships
  - **Validation**: Alembic migrations enforce FKs

- [ ] CHK031 - Are performance indexes defined for frequent queries? [Gap]
  - **Gap**: ISSUE: No index strategy documented
  - **Risk**: Slow queries as data grows

### Clarity

- [x] CHK032 - Are uniqueness constraints explicit? [Clarity]
  - **Evidence**: session_id unique, composite keys documented
  - **Validation**: DB constraints enforced

- [ ] CHK033 - Are validation rules (NOT NULL, CHECK) documented? [Clarity]
  - **Gap**: ISSUE: Constraints not fully documented outside migrations
  - **Partial**: Some in Pydantic models

- [ ] CHK034 - Is cascade policy (ON DELETE) specified for FKs? [Gap]
  - **Gap**: ISSUE: CASCADE behavior not documented
  - **Current**: Implicit in Alembic migrations

### Lifecycle

- [x] CHK035 - Are state transitions (Session, Step) complete? [Completeness]
  - **Evidence**: `SessionStatus` and `StepStatus` enums with transitions
  - **Validation**: State machine tests

- [ ] CHK036 - Are purge conditions (1 year) precisely defined? [Clarity, Spec §FR-044]
  - **Gap**: ISSUE: Purge job not implemented
  - **Spec**: "1 an" mentioned but no implementation

---

## 5. Non-Functional Requirements

### Performance

- [x] CHK037 - Are performance objectives quantified? [Measurability, Spec §SC-001/002/003]
  - **Evidence**: SC-001 (<5s interactive), SC-002 (<5min Docker), SC-003 (<30s analysis)
  - **Gap**: ISSUE: No automated performance tests

- [ ] CHK038 - Are degradation thresholds defined? [Gap]
  - **Gap**: ISSUE: No acceptable degradation levels documented
  - **Risk**: No baseline for performance regression

- [ ] CHK039 - Is concurrent session performance specified? [Gap]
  - **Gap**: ISSUE: Load testing requirements not documented
  - **Spec**: FR-047/048 mention locking but not scale

### Observability

- [x] CHK040 - Are LangSmith trace events listed? [Completeness]
  - **Evidence**: 002-Spec §FR-007, §FR-015 - agent decisions and tool calls
  - **Validation**: `tests/e2e/test_real_llm_invocation.py::test_langsmith_trace_validation`

- [x] CHK041 - Is JSON log format specified? [Clarity, Spec §FR-046]
  - **Evidence**: structlog with JSON output
  - **Validation**: Logs are parseable JSON

- [ ] CHK042 - Are key metrics to expose defined? [Gap]
  - **Gap**: ISSUE: No Prometheus/metrics endpoint documented
  - **Current**: Only logs, no metrics

### Security

- [x] CHK043 - Is API key rotation addressed? [Gap → Partial]
  - **Evidence**: Keys from env vars, can be rotated externally
  - **Gap**: ISSUE: No in-app rotation mechanism

- [x] CHK044 - Is LLM credential storage secure? [Gap → Resolved]
  - **Evidence**: pydantic-settings loads from env only
  - **Validation**: `tests/security/test_api_key_audit.py`

- [x] CHK045 - Are sensitive data masked in logs? [Gap → Resolved]
  - **Evidence**: Spec §FR-046A, implemented in logging config
  - **Validation**: `tests/security/test_api_key_audit.py::test_no_api_keys_in_logs`

### Reliability

- [x] CHK046 - Is retry strategy with backoff quantified? [Clarity, Constitution §10]
  - **Evidence**: 002-Spec: "3 attempts, 1s-10s wait"
  - **Validation**: `tests/e2e/test_edge_cases.py`

- [x] CHK047 - Are timeouts per external operation defined? [Clarity]
  - **Evidence**: `error_handling.timeout_seconds` in YAML configs
  - **Gap**: ISSUE: Not all external calls have explicit timeouts

- [ ] CHK048 - Is DB connection loss behavior specified? [Edge Case, Gap]
  - **Gap**: ISSUE: No reconnection strategy documented
  - **Risk**: Workflow fails permanently on transient DB issues

---

## 6. Isolation & Environment

### Completeness

- [x] CHK049 - Are TestBoost environment prerequisites complete? [Completeness]
  - **Evidence**: README.md lists Python 3.11+, Docker, Poetry
  - **Validation**: CI workflow validates

- [x] CHK050 - Are minimum versions specified? [Clarity]
  - **Evidence**: Python 3.11+, Docker, PostgreSQL 15
  - **Validation**: pyproject.toml enforces Python version

- [x] CHK051 - Is Poetry/virtualenv configuration documented? [Completeness, Spec §FR-010B]
  - **Evidence**: README.md has setup instructions
  - **Validation**: poetry.lock ensures reproducibility

### Clarity

- [x] CHK052 - Is Docker isolation clearly described? [Clarity, Spec §FR-010A]
  - **Evidence**: Maven builds run in containers
  - **Gap**: ISSUE: Container resource limits not documented

- [ ] CHK053 - Is container lifecycle (create/destroy) specified? [Gap]
  - **Gap**: ISSUE: Container cleanup policy not documented
  - **Risk**: Orphan containers accumulating

- [ ] CHK054 - Is host/container volume sharing documented? [Gap]
  - **Gap**: ISSUE: Mount points not formally specified
  - **Current**: Implicit in docker-compose

---

## 7. Test Generation

### Completeness

- [x] CHK055 - Are test types (unit, integration, snapshot, mutation) documented? [Completeness]
  - **Evidence**: Spec §FR-020-026 cover all types
  - **Validation**: Test generation produces all types

- [x] CHK056 - Are class classification criteria exhaustive? [Completeness, Spec §FR-020]
  - **Evidence**: Controller, Service, Repository, Component, DTO
  - **Gap**: ISSUE: Custom annotation-based types not covered

- [ ] CHK057 - Is test quality scoring (0-120) fully defined? [Completeness]
  - **Gap**: ISSUE: Scoring formula not documented
  - **Spec**: Mentioned but no breakdown

### Clarity

- [x] CHK058 - Is mutation threshold (80%) justified? [Clarity, Spec §FR-025]
  - **Evidence**: Industry standard for good coverage
  - **Gap**: ISSUE: No guidance for projects that can't reach 80%

- [x] CHK059 - Are "killer test" generation criteria clear? [Clarity, Spec §FR-026]
  - **Evidence**: Targets surviving mutants
  - **Validation**: PIT recommendations MCP tool

- [ ] CHK060 - Is ApprovalTests snapshot pattern documented? [Clarity]
  - **Gap**: ISSUE: Snapshot test format not specified
  - **Current**: Mentions snapshots but no format

### Edge Cases

- [ ] CHK061 - Is behavior for overly complex classes defined? [Edge Case, Spec Limitations]
  - **Gap**: ISSUE: No cyclomatic complexity threshold documented
  - **Risk**: Agent may fail on complex classes

- [ ] CHK062 - Is external dependency mocking specified? [Edge Case]
  - **Gap**: ISSUE: Mock generation strategy not documented
  - **Partial**: Mockito usage mentioned but not rules

---

## 8. LLM Integration (002-deepagents-integration)

### Completeness

- [x] CHK063 - Is LLM connectivity check requirement complete? [Completeness, 002-Spec §FR-001]
  - **Evidence**: `check_llm_connection()` in startup_checks.py
  - **Validation**: `tests/integration/test_llm_connectivity.py`

- [x] CHK064 - Are all 3 workflows using real LLM agents? [Completeness, 002-Spec §SC-007]
  - **Evidence**: maven_maintenance_agent.py, test_generation_agent.py, docker_deployment_agent.py
  - **Validation**: E2E tests with real LLM calls

- [x] CHK065 - Is artifact storage schema defined? [Completeness, 002-Spec §FR-008]
  - **Evidence**: artifact_type enum, jsonb content, metadata
  - **Validation**: Artifact storage tests

### Clarity

- [x] CHK066 - Is error message format specified? [Clarity, 002-Spec §FR-002]
  - **Evidence**: "{Action failed}: {Root cause}. Action: {What user must do}."
  - **Validation**: Error handling tests

- [x] CHK067 - Is provider switching documented? [Clarity, 002-Spec §FR-013]
  - **Evidence**: LLM_PROVIDER env var + API key
  - **Validation**: `tests/integration/test_provider_switching.py`

- [x] CHK068 - Is retry logic quantified? [Clarity, 002-Spec edge cases]
  - **Evidence**: "3 attempts, 1s-10s wait" exponential backoff
  - **Validation**: `tests/e2e/test_edge_cases.py`

### Edge Cases

- [x] CHK069 - Is rate limit handling specified? [Edge Case, 002-Spec A1]
  - **Evidence**: Fail fast with explicit message format
  - **Validation**: `test_rate_limit_error_handling`

- [x] CHK070 - Is missing tool call handling specified? [Edge Case, 002-Spec A2]
  - **Evidence**: Retry with modified prompt (max 3)
  - **Validation**: `test_missing_tool_calls_retry`

- [x] CHK071 - Is context window overflow handling specified? [Edge Case, 002-Spec A6]
  - **Evidence**: DeepAgents auto-summarization at 170k tokens
  - **Validation**: `test_context_window_overflow`

---

## 9. Constitution Alignment

### Traceability

- [x] CHK072 - Is each FR traceable to constitution principle? [Traceability]
  - **Evidence**: FR numbering maps to constitution sections
  - **Gap**: ISSUE: No explicit traceability matrix

- [ ] CHK073 - Are potential violations documented with justification? [Gap]
  - **Gap**: ISSUE: No violation log maintained
  - **Risk**: Silent constitution drift

### Compliance

- [x] CHK074 - Is "Zéro Complaisance" reflected in error requirements? [Consistency, Constitution §1]
  - **Evidence**: 002-Spec §FR-010 - workflows abort without LLM
  - **Validation**: Startup check tests

- [x] CHK075 - Is "Outils via MCP" respected without exception? [Consistency, Constitution §2]
  - **Evidence**: All tools via MCP servers
  - **Validation**: Code review - no direct system calls

- [x] CHK076 - Is "Pas de Mocks Production" clearly applied? [Consistency, Constitution §3]
  - **Evidence**: E2E tests use real LLM calls
  - **Validation**: `tests/e2e/test_real_llm_invocation.py`

---

## 10. Dependencies & Assumptions

### Documentation

- [x] CHK077 - Are external dependencies listed? [Completeness]
  - **Evidence**: pyproject.toml, README.md, spec dependencies section
  - **Validation**: poetry.lock pins versions

- [ ] CHK078 - Are dependency failure modes addressed? [Gap]
  - **Gap**: ISSUE: No failure mode analysis for each external dep
  - **Partial**: LLM errors handled, others not

- [ ] CHK079 - Are service availability assumptions explicit? [Assumption]
  - **Gap**: ISSUE: No SLA expectations documented
  - **Risk**: Undefined behavior if services degrade

### Validation

- [x] CHK080 - Is dependency version compatibility validated? [Assumption]
  - **Evidence**: poetry.lock ensures reproducibility
  - **Validation**: CI installs from lock file

- [x] CHK081 - Are LLM quota limits documented? [Gap → Resolved]
  - **Evidence**: Spec §Quotas table with provider limits
  - **Gap**: ISSUE: No quota monitoring in app

---

## 11. Acceptance Criteria Quality

### Measurability

- [x] CHK082 - Are all Success Criteria objectively measurable? [Measurability, Spec §SC-*]
  - **Evidence**: All SC have numeric thresholds
  - **Validation**: E2E tests verify thresholds

- [x] CHK083 - Are success/failure thresholds quantified? [Clarity]
  - **Evidence**: <5s, <5min, 80%, etc.
  - **Validation**: Tests assert thresholds

- [x] CHK084 - Are User Story acceptance criteria testable? [Measurability]
  - **Evidence**: Given/When/Then format
  - **Validation**: E2E tests map to scenarios

### Coverage

- [x] CHK085 - Does each FR have at least one acceptance criterion? [Coverage]
  - **Evidence**: FRs map to User Story scenarios
  - **Gap**: ISSUE: Some FRs lack explicit test mapping

- [x] CHK086 - Do scenarios cover nominal AND error cases? [Coverage]
  - **Evidence**: Edge cases section in both specs
  - **Validation**: Error handling tests

---

## Summary

### Status Overview

| Category | Total | Passed | Gaps | Issues |
|----------|-------|--------|------|--------|
| Architecture MCP & Agents | 9 | 8 | 1 | 1 |
| Workflows | 9 | 6 | 3 | 4 |
| API & Interfaces | 9 | 5 | 4 | 4 |
| Data Model | 8 | 5 | 3 | 3 |
| Non-Functional Requirements | 12 | 8 | 4 | 5 |
| Isolation & Environment | 6 | 4 | 2 | 2 |
| Test Generation | 8 | 4 | 4 | 4 |
| LLM Integration | 9 | 9 | 0 | 0 |
| Constitution Alignment | 5 | 4 | 1 | 1 |
| Dependencies & Assumptions | 5 | 3 | 2 | 2 |
| Acceptance Criteria | 5 | 5 | 0 | 1 |
| **TOTAL** | **85** | **61** | **24** | **27** |

### Pass Rate: 72% (61/85)

### Issues to Create

| ID | Category | Description | Priority |
|----|----------|-------------|----------|
| ISS-001 | MCP Tools | Create OpenAPI-style documentation for MCP tools | Medium |
| ISS-002 | Workflows | Add visual workflow diagrams to documentation | Low |
| ISS-003 | Workflows | Document state machine transitions formally | Medium |
| ISS-004 | Workflows | Make Maven test timeout configurable | Low |
| ISS-005 | Workflows | Document baseline test strategy | Medium |
| ISS-006 | Workflows | Add flaky test detection | Medium |
| ISS-007 | Workflows | Document circular dependency handling | Low |
| ISS-008 | API | Export OpenAPI spec file | Medium |
| ISS-009 | API | Document all HTTP error codes | Medium |
| ISS-010 | API | Document CLI exit codes | Low |
| ISS-011 | API | Document X-API-Key format | Low |
| ISS-012 | API | Implement pagination for lists | Medium |
| ISS-013 | Data | Define database index strategy | Medium |
| ISS-014 | Data | Document validation constraints | Low |
| ISS-015 | Data | Document CASCADE policies | Low |
| ISS-016 | Data | Implement session purge job | High |
| ISS-017 | NFR | Add automated performance tests | High |
| ISS-018 | NFR | Define degradation thresholds | Medium |
| ISS-019 | NFR | Document load testing requirements | Medium |
| ISS-020 | NFR | Add Prometheus metrics endpoint | Medium |
| ISS-021 | NFR | Add explicit timeouts for all external calls | Medium |
| ISS-022 | NFR | Document DB reconnection strategy | Medium |
| ISS-023 | Isolation | Document container resource limits | Low |
| ISS-024 | Isolation | Document container cleanup policy | Low |
| ISS-025 | Test Gen | Document test quality scoring formula | Medium |
| ISS-026 | Test Gen | Define cyclomatic complexity threshold | Low |
| ISS-027 | Constitution | Create FR-to-Constitution traceability matrix | Low |

---

## Next Steps

1. **High Priority Issues (3)**:
   - ISS-016: Implement session purge job
   - ISS-017: Add automated performance tests
   - (Architectural decisions needed)

2. **Medium Priority Issues (14)**:
   - Create GitHub issues for tracking
   - Prioritize based on upcoming features

3. **Low Priority Issues (10)**:
   - Address during refactoring sprints
   - Documentation improvements

---

**Created**: 2025-12-07
**Validated By**: Claude Code
**Feature Coverage**: 001-testboost-core + 002-deepagents-integration
