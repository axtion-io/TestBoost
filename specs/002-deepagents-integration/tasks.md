# Tasks: DeepAgents LLM Integration

**Input**: Design documents from `/specs/002-deepagents-integration/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: E2E tests are explicitly requested in spec.md and are REQUIRED to validate real LLM invocations.

**Organization**: Tasks are grouped by user story (P1: US1, P2: US2/US4/US5, P3: US3) to enable independent implementation and testing. All 3 workflows (Maven, test generation, deployment) are migrated to use LLM agents.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

Single Python backend project (from plan.md):
- Source: `src/`
- Tests: `tests/`
- Config: `config/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure (no new files needed - feature modifies existing codebase)

- [ ] T001 Verify Python 3.11+ environment and DeepAgents 0.2.7 installed
- [ ] T002 [P] Verify existing agent infrastructure (src/agents/loader.py, config/agents/*.yaml)
- [ ] T003 [P] Verify existing MCP servers (src/mcp_servers/maven_maintenance/, git_maintenance/, docker/, test_generator/)
- [ ] T004 [P] Verify PostgreSQL 15 running on port 5433 with sessions/artifacts tables
- [ ] T005 [P] Verify tenacity library already installed (from 001-testboost-core) for retry logic (U1)
- [ ] T006 [P] Verify MCP servers expose get_tools() functions (check src/mcp_servers/*/\_\_init\_\_.py) (U2)
- [ ] T006a [P] Verify backup strategy: check if existing backup utility exists or plan to create new one (Constitution Principle 6)

**Checkpoint**: Environment validated - ready for implementation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core LLM connectivity infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete. This phase fixes the constitutional violation where workflows execute without LLM agents.

- [ ] T007 Create src/lib/startup_checks.py with check_llm_connection() function
- [ ] T008 Modify src/api/main.py to add startup event calling check_llm_connection()
- [ ] T009 [P] Modify src/cli/main.py to add callback calling check_llm_connection()
- [ ] T010 Create src/mcp_servers/registry.py with get_mcp_tool_registry() function
- [ ] T011 [P] Add retry logic to src/lib/llm.py if not present (check T005 verification first)
- [ ] T011a [P] Implement API key security validation in src/lib/startup_checks.py: validate_api_key_security() function that verifies (1) keys loaded from .env only, (2) keys never logged in plaintext, (3) keys never transmitted in URLs, (4) add test in tests/integration/test_llm_connectivity.py::test_api_keys_not_logged (Constitution Principle 7 - Isolation et Sécurité)

**Checkpoint**: Foundation ready - LLM connectivity check implemented, MCP registry created. User story implementation can now begin.

---

## Phase 3: User Story 1 - Application Startup Validation (Priority: P1) 🎯 MVP

**Goal**: Verify LLM provider connectivity at startup before accepting commands, ensuring zero workflows execute without agents (fixes constitutional violation)

**Independent Test**: Start application with invalid/missing API key and verify it fails immediately with clear error message within 5 seconds

**Unblocks**: CHK003, CHK020, CHK090 from 001-testboost-core E2E checklist

### Tests for User Story 1 (REQUIRED)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T012 [P] [US1] Create tests/integration/test_llm_connectivity.py with test_llm_connection_success()
- [ ] T013 [P] [US1] Add test_llm_connection_failure() to tests/integration/test_llm_connectivity.py
- [ ] T014 [P] [US1] Add test_llm_connection_timeout() to tests/integration/test_llm_connectivity.py

### Implementation for User Story 1

- [ ] T015 [US1] Implement check_llm_connection() in src/lib/startup_checks.py with ping to configured LLM
- [ ] T016 [US1] Add error handling in check_llm_connection() for missing API keys (raise LLMProviderError)
- [ ] T017 [US1] Add error handling in check_llm_connection() for invalid API keys (raise AuthenticationError)
- [ ] T018 [US1] Add timeout handling in check_llm_connection() (5 second max, raise TimeoutError)
- [ ] T019 [US1] Add retry logic with exponential backoff for intermittent connectivity (A4: 3 attempts, 1s-10s wait)
- [ ] T020 [US1] Add rate limit error detection (catch 429, extract retry-after header, fail with EXPLICIT message format: "LLM rate limit exceeded by {provider}. Retry after {duration} seconds. Workflow aborted. Zero results generated.") (A1, Constitution Principle 1)
- [ ] T021 [US1] Implement startup event in src/api/main.py calling check_llm_connection() with error logging
- [ ] T022 [US1] Implement CLI callback in src/cli/main.py calling check_llm_connection() with error exit
- [ ] T023 [US1] Add structured logging for "llm_connection_ok" and "llm_connection_failed" events

**Validation**:
```bash
# Test 1: Missing API key
unset GOOGLE_API_KEY
.venv/Scripts/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# Expected: Fails within 5s with "LLM not available: GOOGLE_API_KEY not configured"

# Test 2: Valid API key
export GOOGLE_API_KEY=your_key
.venv/Scripts/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# Expected: Starts successfully, logs "llm_connection_ok"

# Test 3: Run integration tests
pytest tests/integration/test_llm_connectivity.py -v
# Expected: All 3 tests pass
```

**Checkpoint**: Application refuses to start without valid LLM connection. CHK003, CHK020, CHK090 now pass.

---

## Phase 4: User Story 2 - Maven Maintenance with Real LLM Agent (Priority: P2)

**Goal**: Refactor Maven maintenance workflow to use DeepAgents `create_deep_agent()` for real AI agent reasoning with MCP tool calls

**Independent Test**: Run Maven maintenance on Java project and verify LangSmith traces show ≥3 real LLM API calls with tool invocations

**Unblocks**: CHK097, CHK095, CHK082, CHK084 from 001-testboost-core E2E checklist

### Tests for User Story 2 (REQUIRED)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T024 [P] [US2] Create tests/integration/test_maven_agent_workflow.py with test_maven_workflow_uses_agent()
- [ ] T025 [P] [US2] Add test_maven_workflow_stores_artifacts() to tests/integration/test_maven_agent_workflow.py
- [ ] T026 [P] [US2] Create tests/e2e/test_real_llm_invocation.py with test_maven_workflow_llm_calls()
- [ ] T027 [P] [US2] Add test_langsmith_trace_validation() to tests/e2e/test_real_llm_invocation.py
- [ ] T028 [P] [US2] Add test_maven_agent_tool_call_retry() to verify A2 (agent retries if no tools called)

### Implementation for User Story 2

- [ ] T029 [US2] Implement get_mcp_tool_registry() in src/mcp_servers/registry.py returning 4 required MCP servers: maven_maintenance, git_maintenance, docker, test_generator (NOTE: pit_recommendations and container_runtime exist in codebase but not needed for this feature - agents don't use them)
- [ ] T030 [P] [US2] Add or verify get_tools() function in src/mcp_servers/maven_maintenance/__init__.py (check T006)
- [ ] T031 [P] [US2] Add or verify get_tools() function in src/mcp_servers/git_maintenance/__init__.py (check T006)
- [ ] T032 [P] [US2] Add or verify get_tools() function in src/mcp_servers/docker/__init__.py (check T006)
- [ ] T033 [P] [US2] Add or verify get_tools() function in src/mcp_servers/test_generator/__init__.py (check T006)
- [ ] T033a [US2] Create backup utility in src/workflows/backup.py with create_backup(file_path) function returning backup path (Constitution Principle 6)
- [ ] T034 [US2] Create src/workflows/maven_maintenance_agent.py with run_maven_maintenance_with_agent() function
- [ ] T034a [US2] Implement backup creation in maven_maintenance_agent.py before pom.xml modifications (call backup.create_backup() before tool invocations that modify files, store backup_path in artifacts) (Constitution Principle 6)
- [ ] T035 [US2] Implement agent creation in maven_maintenance_agent.py using create_deep_agent() with MCP tools
- [ ] T036 [US2] Load agent config from config/agents/maven_maintenance_agent.yaml in maven_maintenance_agent.py
- [ ] T037 [US2] Implement config reload on workflow resume (A3: reload YAML if workflow paused)
- [ ] T038 [US2] Load system prompt from config/prompts/maven/dependency_update.md in maven_maintenance_agent.py
- [ ] T039 [US2] Bind MCP tools to LLM using llm.bind_tools(maven_tools) in maven_maintenance_agent.py
- [ ] T040 [US2] Implement agent invocation with ainvoke() in maven_maintenance_agent.py
- [ ] T041 [US2] Add retry logic for agent invocation (A4: retry with backoff, A2: retry if no tools)
- [ ] T042 [US2] Add JSON validation for tool calls (A5: catch JSONDecodeError, retry max 3 times)
- [ ] T043 [US2] Add tool call verification (A2: check expected tools called, retry with modified prompt if not)
- [ ] T044 [US2] Store agent reasoning in artifacts table with artifact_type="agent_reasoning"
- [ ] T045 [US2] Store tool calls in artifacts table with artifact_type="llm_tool_call"
- [ ] T046 [US2] Store LLM metrics in artifacts table with artifact_type="llm_metrics" (tokens, duration, cost)
- [ ] T047 [US2] Add deprecation warning to old src/workflows/maven_maintenance.py run_maven_maintenance()
- [ ] T048 [US2] Update src/cli/commands/maintenance.py to call run_maven_maintenance_with_agent()
- [ ] T049 [US2] Add LangSmith tracing validation (check LANGSMITH_TRACING env var) in maven_maintenance_agent.py

**Validation**:
```bash
# Test 1: Run Maven workflow with agent
export GOOGLE_API_KEY=your_key
export LANGSMITH_API_KEY=your_langsmith_key
export LANGSMITH_TRACING=true
.venv/Scripts/python -m src.cli.main maintenance maven --project-path /path/to/spring-petclinic --mode autonomous
# Expected: Workflow completes, logs show "agent_loaded", LangSmith shows ≥3 LLM calls

# Test 2: Verify artifacts stored
psql -h localhost -p 5433 -d testboost -c "SELECT artifact_type, content FROM artifacts WHERE session_id='<session_id>';"
# Expected: agent_reasoning, llm_tool_call, llm_metrics records present

# Test 3: Run E2E tests
pytest tests/e2e/test_real_llm_invocation.py::test_maven_workflow_llm_calls -v --langsmith
# Expected: Test passes, LangSmith trace shows ≥3 calls with tool invocations
```

**Checkpoint**: Maven workflow uses real LLM agents, all tool calls traced. CHK097, CHK095, CHK082, CHK084 now pass.

---

## Phase 5: User Story 4 - Test Generation with Real LLM Agent (Priority: P2)

**Goal**: Refactor test generation workflow to use DeepAgents for AI-driven test creation based on class analysis

**Independent Test**: Run test generation on Java project and verify LangSmith traces show ≥3 real LLM API calls analyzing classes

**Unblocks**: Same pattern as Maven (CHK097, CHK082, CHK084) for test generation workflow

### Tests for User Story 4 (REQUIRED)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T050 [P] [US4] Create tests/integration/test_test_gen_agent_workflow.py with test_test_gen_workflow_uses_agent()
- [ ] T051 [P] [US4] Add test_test_gen_workflow_stores_artifacts() to tests/integration/test_test_gen_agent_workflow.py
- [ ] T052 [P] [US4] Add test_test_gen_workflow_llm_calls() to tests/e2e/test_real_llm_invocation.py
- [ ] T053 [P] [US4] Add test_test_gen_agent_tool_call_retry() to verify error correction retry logic

### Implementation for User Story 4

- [ ] T054 [US4] Create src/workflows/test_generation_agent.py with run_test_generation_with_agent() function
- [ ] T054a [US4] Implement backup creation in test_generation_agent.py before test file generation (call backup.create_backup() on target test directory before writing test files) (Constitution Principle 6)
- [ ] T055 [US4] Implement agent creation in test_generation_agent.py using create_deep_agent() with test gen MCP tools
- [ ] T056 [US4] Load agent config from config/agents/test_gen_agent.yaml in test_generation_agent.py
- [ ] T057 [US4] Load system prompt from config/prompts/test_generation/class_analysis.md (or similar)
- [ ] T058 [US4] Bind test generator MCP tools to LLM using llm.bind_tools(test_gen_tools)
- [ ] T059 [US4] Implement agent invocation with retry logic (same as T041-T043: backoff, tool validation, JSON check)
- [ ] T060 [US4] Add auto-correction retry logic (spec: max 3 attempts if compilation errors)
- [ ] T061 [US4] Store agent reasoning and tool calls in artifacts (same pattern as T044-T046)
- [ ] T062 [US4] Add deprecation warning to old src/workflows/test_generation.py
- [ ] T063 [US4] Update src/cli/commands/test.py to call run_test_generation_with_agent()
- [ ] T064 [US4] Add LangSmith tracing validation for test generation workflow

**Validation**:
```bash
# Test: Run test generation with agent
.venv/Scripts/python -m src.cli.main test generate --project-path /path/to/spring-petclinic --mode autonomous
# Expected: LangSmith shows ≥3 LLM calls, agent analyzes class types, generates tests
```

**Checkpoint**: Test generation workflow uses real LLM agents. Same validation pattern as Maven.

---

## Phase 6: User Story 5 - Docker Deployment with Real LLM Agent (Priority: P2)

**Goal**: Refactor Docker deployment workflow to use DeepAgents for AI-driven project type detection and configuration

**Independent Test**: Run Docker deployment and verify LangSmith traces show ≥3 real LLM API calls detecting project type

**Unblocks**: Same pattern as Maven/Test Gen for deployment workflow

### Tests for User Story 5 (REQUIRED)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T065 [P] [US5] Create tests/integration/test_docker_agent_workflow.py with test_docker_workflow_uses_agent()
- [ ] T066 [P] [US5] Add test_docker_workflow_stores_artifacts() to tests/integration/test_docker_agent_workflow.py
- [ ] T067 [P] [US5] Add test_docker_workflow_llm_calls() to tests/e2e/test_real_llm_invocation.py
- [ ] T068 [P] [US5] Add test_docker_agent_health_check_monitoring() to verify agent waits for health OK

### Implementation for User Story 5

- [ ] T069 [US5] Create src/workflows/docker_deployment_agent.py with run_docker_deployment_with_agent() function
- [ ] T069a [US5] Implement backup creation in docker_deployment_agent.py before Dockerfile/docker-compose generation (call backup.create_backup() before writing Docker configuration files) (Constitution Principle 6)
- [ ] T070 [US5] Implement agent creation in docker_deployment_agent.py using create_deep_agent() with Docker MCP tools
- [ ] T071 [US5] Load agent config from config/agents/deployment_agent.yaml in docker_deployment_agent.py
- [ ] T072 [US5] Load system prompt from config/prompts/docker/project_analysis.md (or similar)
- [ ] T073 [US5] Bind Docker MCP tools to LLM using llm.bind_tools(docker_tools)
- [ ] T074 [US5] Implement agent invocation with retry logic (same as T041-T043: backoff, tool validation, JSON check)
- [ ] T075 [US5] Store agent reasoning and tool calls in artifacts (same pattern as T044-T046)
- [ ] T076 [US5] Add deprecation warning to old src/workflows/docker_deployment.py
- [ ] T077 [US5] Update src/cli/commands/deploy.py to call run_docker_deployment_with_agent()
- [ ] T078 [US5] Add LangSmith tracing validation for Docker deployment workflow

**Validation**:
```bash
# Test: Run Docker deployment with agent
.venv/Scripts/python -m src.cli.main deploy docker --project-path /path/to/spring-petclinic
# Expected: LangSmith shows ≥3 LLM calls, agent detects JAR type, generates Dockerfile
```

**Checkpoint**: Docker deployment workflow uses real LLM agents. All 3 workflows migrated.

---

## Phase 7: User Story 3 - Agent Configuration Management (Priority: P3)

**Goal**: Enable non-developers to configure agent behavior through YAML files and Markdown templates without modifying code

**Independent Test**: Modify maven_maintenance_agent.yaml temperature and verify changes take effect on next workflow execution

**Unblocks**: CHK096, CHK101 from 001-testboost-core E2E checklist

### Tests for User Story 3 (REQUIRED)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [ ] T079 [P] [US3] Create tests/integration/test_agent_config_loading.py with test_yaml_config_loads()
- [ ] T080 [P] [US3] Add test_yaml_changes_take_effect() to tests/integration/test_agent_config_loading.py
- [ ] T081 [P] [US3] Add test_invalid_yaml_fails_startup() to tests/integration/test_agent_config_loading.py
- [ ] T082 [P] [US3] Add test_prompt_template_loads() to tests/integration/test_agent_config_loading.py
- [ ] T083 [P] [US3] Add test_config_reload_on_resume() to verify A3 (config reloaded if workflow resumed)

### Implementation for User Story 3

- [ ] T084 [US3] Add agent config validation to src/lib/startup_checks.py validate_agent_infrastructure()
- [ ] T085 [US3] Load and validate all 3 agent YAML configs at startup in validate_agent_infrastructure()
- [ ] T086 [US3] Add error handling for missing YAML files (raise ConfigurationError with file path)
- [ ] T087 [US3] Add error handling for malformed YAML (raise ValidationError with line number)
- [ ] T088 [US3] Add error handling for missing prompt templates (raise ConfigurationError with template path)
- [ ] T089 [US3] Call validate_agent_infrastructure() from startup event in src/api/main.py
- [ ] T090 [US3] Call validate_agent_infrastructure() from CLI callback in src/cli/main.py
- [ ] T091 [US3] Add structured logging for "agent_config_validated" with agent name and model
- [ ] T092 [US3] Update quickstart.md Scenario 3 with YAML modification example
- [ ] T093 [US3] Update quickstart.md Scenario 3 with prompt template modification example

**Validation**:
```bash
# Test 1: Modify YAML temperature
# Edit config/agents/maven_maintenance_agent.yaml: temperature: 0.1 → 0.7
.venv/Scripts/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# Expected: Logs show "agent_config_validated" with new temperature

# Test 2: Invalid YAML
# Edit config/agents/maven_maintenance_agent.yaml: introduce syntax error
.venv/Scripts/python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
# Expected: Fails with "Invalid agent config: YAML syntax error at line X"

# Test 3: Run integration tests
pytest tests/integration/test_agent_config_loading.py -v
# Expected: All 5 tests pass (including config reload test)
```

**Checkpoint**: Agent configs validated at startup, YAML changes take effect. CHK096, CHK101 now pass.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories and final validation

- [ ] T094 [P] Update README.md with agent requirements section (Python 3.11+, DeepAgents 0.2.7, LLM API keys)
- [ ] T095 [P] Add troubleshooting section to README.md for LLM connection errors and edge cases
- [ ] T096 [P] Update 001-testboost-core/checklists/e2e-acceptance.md to mark unblocked checks as passing
- [ ] T097 Run full E2E test suite from 001-testboost-core checklist to validate all 9 unblocked checks
- [ ] T098 [P] Performance testing: Measure all 3 workflows duration with agents vs without (target <2min for Maven)
- [ ] T099 [P] Cost analysis: Log LLM token usage and estimate costs for Gemini/Claude/GPT-4o across all workflows
- [ ] T100 Add migration guide to quickstart.md for transitioning from old workflows to agent-based workflows
- [ ] T101 [P] Code review: Ensure no direct system calls (all via MCP tools per Constitution Principle 2)
- [ ] T101a [P] Security audit: Grep logs/testboost.log and test output for API key patterns (regex: 'sk-[A-Za-z0-9]{32,}', 'AIza[A-Za-z0-9]{35}'), verify zero matches (Constitution Principle 7)
- [ ] T102 Validate LangSmith tracing works for all 3 providers (Gemini, Claude, GPT-4o) across all 3 workflows
- [ ] T103 Run quickstart.md validation: Test all 4 scenarios (Developer, CLI User, Administrator, Tester)
- [ ] T104 [P] Document edge case handling in README.md (A1-A6: rate limits, missing tools, config reload, retry, JSON validation)
- [ ] T105 Validate all 3 workflows respect "Zéro Complaisance" (fail-fast, no silent degradation, real LLM calls)

**Validation**:
```bash
# Run full E2E suite for all workflows
pytest tests/e2e/ -v --langsmith
# Expected: All tests pass, LangSmith shows traces for Maven, test gen, and deployment

# Validate checklist unblocked
cat specs/001-testboost-core/checklists/e2e-acceptance.md | grep "CHK\(003\|020\|090\|097\|095\|082\|084\|096\|101\)"
# Expected: All 9 checks now marked as passing (not blocked)
```

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - **US1 (P1)**: Must complete first (startup validation blocks all workflows)
  - **US2, US4, US5 (P2)**: Can proceed in parallel after US1 (independent workflows)
  - **US3 (P3)**: Can start after Foundational, run in parallel with US2/US4/US5
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Depends on User Story 1 completion (needs LLM connectivity check)
- **User Story 4 (P2)**: Depends on User Story 1 completion (needs LLM connectivity check)
- **User Story 5 (P2)**: Depends on User Story 1 completion (needs LLM connectivity check)
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent of workflows

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Registry/infrastructure before workflow implementation
- Workflow implementation before CLI integration
- Implementation before validation
- Story complete before moving to next priority

### Parallel Opportunities

- **Phase 1**: T002-T006 can run in parallel (verification tasks)
- **Phase 2**: T009, T011 can run in parallel (different files)
- **User Story 1 Tests**: T012-T014 can run in parallel
- **User Story 2 Tests**: T024-T028 can run in parallel
- **User Story 2 MCP Tools**: T030-T033 can run in parallel (different MCP servers)
- **User Story 4 Tests**: T050-T053 can run in parallel
- **User Story 5 Tests**: T065-T068 can run in parallel
- **User Story 3 Tests**: T079-T083 can run in parallel
- **Workflows US2/US4/US5**: Can be implemented in parallel after US1 (different files)
- **Phase 8 Polish**: T094-T096, T098-T099, T101, T104 can run in parallel

**Critical Path**: Setup → Foundational → US1 (startup) → US2 (Maven) → US4 (Test Gen) → US5 (Deployment) → US3 (Config) → Polish

**Optimal Path (Parallel)**: Setup → Foundational → US1 → [US2 + US4 + US5 in parallel] → US3 → Polish

---

## Parallel Example: Phase 4 (US2/US4/US5)

```bash
# After US1 completion, launch all 3 workflow implementations in parallel:

# Team Member A: Maven workflow (T024-T049)
Task: "Create src/workflows/maven_maintenance_agent.py"

# Team Member B: Test generation workflow (T050-T064)
Task: "Create src/workflows/test_generation_agent.py"

# Team Member C: Docker deployment workflow (T065-T078)
Task: "Create src/workflows/docker_deployment_agent.py"

# All share same foundational infrastructure (registry, startup checks)
# All follow same pattern (tests → implementation → CLI integration)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (verify environment)
2. Complete Phase 2: Foundational (LLM connectivity check, MCP registry) - **CRITICAL**
3. Complete Phase 3: User Story 1 (startup validation)
4. **STOP and VALIDATE**: Test startup with invalid/valid API keys
5. Validate CHK003, CHK020, CHK090 now pass
6. **Constitutional Compliance Check**: Confirm application refuses to start without LLM

**MVP Deliverable**: TestBoost application that respects "Zéro Complaisance" - never executes workflows without agents

### Incremental Delivery (Recommended)

1. **Setup + Foundational** → LLM connectivity infrastructure ready
2. **Add User Story 1** → Startup validation → **Deploy/Demo (MVP!)** → Fixes constitutional violation
3. **Add User Story 2** → Maven with agents → Deploy/Demo → Real AI in Maven workflow
4. **Add User Story 4** → Test gen with agents → Deploy/Demo → Real AI in test generation
5. **Add User Story 5** → Deployment with agents → Deploy/Demo → All 3 workflows use agents
6. **Add User Story 3** → Config management → Deploy/Demo → Non-developers can tune agents
7. **Polish** → Documentation, performance, E2E validation → Production-ready

Each story adds value without breaking previous stories.

### Parallel Team Strategy (Maximum Efficiency)

1. **Week 1**: Team completes Setup + Foundational + US1 together (T001-T023)
2. **Week 2**: Once US1 done, split team:
   - Developer A: User Story 2 (Maven) - T024-T049
   - Developer B: User Story 4 (Test Gen) - T050-T064
   - Developer C: User Story 5 (Deployment) - T065-T078
   - Developer D: User Story 3 (Config) - T079-T093 (can start with US1 complete)
3. **Week 3**: All converge on Polish tasks (T094-T105)

**Timeline**: 3 weeks with 4 developers vs 5-6 weeks single developer

---

## Notes

- **[P] tasks** = different files, no dependencies, can run in parallel
- **[Story] label** maps task to specific user story for traceability
- **Each user story independently testable**: US1 (startup), US2 (Maven), US3 (config), US4 (test gen), US5 (deployment)
- **E2E tests are REQUIRED**: This feature explicitly validates real LLM calls vs mocks for ALL workflows
- **Verify tests fail before implementing**: TDD approach ensures we're testing the right behavior
- **Commit after each task**: Small, atomic commits for easier rollback
- **Stop at checkpoints**: Validate story independently before proceeding
- **Constitutional alignment**: Every task respects "Zéro Complaisance" - no fake agents, no silent fallbacks
- **Unblocking 001**: This feature unblocks 9 critical checks from 001-testboost-core E2E checklist
- **Edge cases handled**: A1-A6 addressed in implementation (rate limits, tool validation, config reload, retry, JSON parsing)
- **Verification tasks**: U1 (retry check), U2 (MCP tools check) in Phase 1

---

## Checklist Unblocking Map

| User Story | Tasks | Unblocks Checks | Validation |
|------------|-------|-----------------|------------|
| US1 (P1) | T012-T023 | CHK003, CHK020, CHK090 | App fails if no LLM |
| US2 (P2) | T024-T049 | CHK097, CHK095, CHK082, CHK084 | LangSmith shows ≥3 LLM calls (Maven) |
| US4 (P2) | T050-T064 | CHK097, CHK082, CHK084 | LangSmith shows ≥3 LLM calls (Test Gen) |
| US5 (P2) | T065-T078 | CHK097, CHK082, CHK084 | LangSmith shows ≥3 LLM calls (Deployment) |
| US3 (P3) | T079-T093 | CHK096, CHK101 | YAML changes take effect |

**Total**: 105 tasks, 9 checks unblocked, 5 user stories, 3 workflows migrated

---

## Success Metrics

After implementation:

- ✅ **SC-001**: Application startup fails within 5 seconds if LLM provider not accessible (US1)
- ✅ **SC-002**: Every workflow (Maven, test gen, deployment) results in ≥3 LLM API calls (US2, US4, US5)
- ✅ **SC-003**: LLM agents use reasoning from Markdown prompts (US2, US4, US5)
- ✅ **SC-004**: Switching LLM provider requires zero code changes (US3 - YAML edit only)
- ✅ **SC-005**: 100% of agent tool calls traced in LangSmith (US2, US4, US5)
- ✅ **SC-006**: YAML config changes take effect on next workflow execution (US3, A3)
- ✅ **SC-007**: All three workflows (Maven, test gen, deployment) use LLM agents (US2, US4, US5)
- ✅ **SC-008**: Zero workflows execute without LLM invocation (US1 blocks execution)
- ✅ **SC-009**: LLM metrics logged for every workflow execution (US2, US4, US5)
- ✅ **SC-010**: Agent failure rate under 5% with retry logic (A4, A5 - retry implementation)

All success criteria mapped to specific user stories and tasks.

---

## Edge Case Coverage

| Edge Case | Decision | Implementation Tasks | Validation |
|-----------|----------|---------------------|------------|
| **A1**: Rate limits | Fail immediately with clear error | T020 | Error message shows retry-after duration |
| **A2**: Missing tool calls | Retry with modified prompt (max 3) | T043, T028 | Test T028 verifies retry logic |
| **A3**: Config changes during pause | Reload config on resume | T037, T083 | Test T083 verifies reload |
| **A4**: Intermittent connectivity | Retry with exponential backoff | T019, T041 | Tests T014, T019 verify retry |
| **A5**: Malformed JSON | Validate and retry (max 3) | T042 | Logs show JSONDecodeError, retry attempts |
| **A6**: Context window | Trust DeepAgents auto-summarization | T099 (monitor tokens) | Cost analysis logs token counts |

All edge cases addressed with concrete tasks and validation methods.
