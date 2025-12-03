# Implementation Plan: DeepAgents LLM Integration

**Branch**: `002-deepagents-integration` | **Date**: 2025-11-28 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/002-deepagents-integration/spec.md`

## Summary

Integrate DeepAgents LLM framework into TestBoost workflows to enable real AI agent reasoning and decision-making. Replace current deterministic workflow logic (direct MCP tool calls) with LLM-powered agents that use YAML configurations and Markdown prompts. Critical to fix constitutional violation of "Zéro Complaisance" where workflows execute without agents, giving false impression of AI functionality.

**Technical Approach**: Implement LLM connectivity check at startup (P1), refactor Maven maintenance workflow to use `create_deep_agent()` with MCP tool binding (P2), and load agent configs from existing YAML/Markdown files (P3). Migration strategy is incremental, preserving existing MCP servers and database schema.

## Technical Context

**Language/Version**: Python 3.11+ (already required by DeepAgents 0.2.7)
**Primary Dependencies**: DeepAgents 0.2.7, LangChain Core 1.1+, LangGraph 1.0+, FastAPI 0.121
**Storage**: PostgreSQL 15 on port 5433 (existing, no schema changes needed)
**Testing**: pytest 8.2 with real LLM API calls (no mocks), LangSmith tracing validation
**Target Platform**: Windows 11 (primary), Linux server (secondary)
**Project Type**: Single backend application (CLI + REST API)
**Environment Variables**:
- LLM Provider: `LLM_PROVIDER=google|anthropic|openai` (default: google)
- API Keys: `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (at least one required)
- LangSmith (optional): `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`
- Database: `DATABASE_URL=postgresql://user:pass@localhost:5433/testboost` (default from .env)
**Performance Goals**: LLM connectivity check <5s, Maven workflow with agents <2min for simple projects
**Constraints**: No breaking changes to existing API/CLI interfaces, must coexist with StateGraph during migration
**Scale/Scope**: 3 workflows to migrate (Maven, test gen, deployment), 3 agent YAML configs, 4 MCP servers (maven_maintenance, git_maintenance, docker, test_generator), 1 Markdown prompt template (Maven dependency_update.md - test gen and deployment prompts deferred to future work)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### 1. Zéro Complaisance ✅

**Current Status**: ❌ VIOLATED in 001-testboost-core
**Fix**: FR-001, FR-002, FR-010 - LLM connectivity check at startup, fail if unavailable
**Validation**: CHK020, CHK090, CHK097 - App plantes if no agents, zero workflows without LLM

### 2. Outils via MCP Exclusivement ✅

**Compliance**: FR-006, FR-014 - Agents use MCP tools, no direct system calls
**Validation**: Existing MCP servers reused, tool calls traced in LangSmith

### 3. Pas de Mocks en Production Utilisateur ✅

**Compliance**: FR-007, SC-002, SC-005 - Real LLM calls, LangSmith tracing
**Validation**: CHK097 - ≥3 real LLM API calls per workflow

### 4. Automatisation avec Contrôle Utilisateur ✅

**Compliance**: Existing modes (interactive/autonomous) preserved
**Validation**: No changes to user control mechanisms

### 5. Traçabilité Complète ✅

**Compliance**: FR-007, FR-008, FR-015 - LangSmith logging, session artifacts
**Validation**: CHK082, CHK084 - Agent decisions documented, traces in LangSmith

### 6-13. All Other Principles ✅

**Compliance**: No changes to validation, isolation, modularity, transparency, robustness, performance, standards respect, or simplicity
**Validation**: Existing implementations preserved

**GATE RESULT**: ✅ **PASS** - Feature fixes existing constitutional violation and respects all principles

## Project Structure

### Documentation (this feature)

```text
specs/002-deepagents-integration/
├── spec.md                      # Feature specification (DONE)
├── plan.md                      # This file
├── agent-checklist-mapping.md  # Mapping to 001 E2E checks (DONE)
├── research.md                  # Phase 0: Technical decisions
├── data-model.md                # Phase 1: Entities and relationships
├── quickstart.md                # Phase 1: Integration guide
├── contracts/                   # Phase 1: API contracts (if needed)
└── tasks.md                     # Phase 2: Implementation tasks
```

### Source Code (repository root)

**NO NEW FILES** - This feature modifies existing codebase:

```text
src/
├── lib/
│   ├── startup_checks.py        # NEW - LLM connectivity validation
│   ├── llm.py                   # MODIFY - Add check_llm_connection()
│   └── config.py                # No changes (LLM config exists)
│
├── api/
│   └── main.py                  # MODIFY - Add startup event for LLM check
│
├── cli/
│   └── main.py                  # MODIFY - Add callback for LLM check
│
├── workflows/
│   ├── maven_maintenance.py            # KEEP (deprecated)
│   ├── maven_maintenance_agent.py      # NEW - Agent-based version
│   ├── test_generation.py              # KEEP (may migrate in P2)
│   └── docker_deployment.py            # KEEP (may migrate in P2)
│
├── agents/
│   ├── loader.py               # EXISTS - Load agent configs from YAML (call load_agent() in workflows)
│   ├── adapter.py              # EXISTS - May need adjustments
│   └── __init__.py             # EXISTS
│
└── mcp_servers/
    ├── maven_maintenance/      # EXISTS - Used as tools (REQUIRED)
    ├── git_maintenance/        # EXISTS - Used as tools (REQUIRED)
    ├── docker/                 # EXISTS - Used as tools (REQUIRED)
    ├── test_generator/         # EXISTS - Used as tools (REQUIRED)
    ├── pit_recommendations/    # EXISTS - Not used in this feature
    └── container_runtime/      # EXISTS - Not used in this feature

config/
├── agents/
│   ├── maven_maintenance_agent.yaml    # EXISTS - Use as-is
│   ├── test_gen_agent.yaml            # EXISTS
│   └── deployment_agent.yaml          # EXISTS
└── prompts/
    ├── maven/
    │   └── dependency_update.md        # EXISTS - Use for Maven workflow
    ├── test_generation/                 # FUTURE - Prompts deferred (use inline prompts in tasks for now)
    └── docker/                          # FUTURE - Prompts deferred (use inline prompts in tasks for now)

tests/
├── integration/
│   ├── test_llm_connectivity.py       # NEW - Test P1
│   ├── test_maven_agent_workflow.py   # NEW - Test P2
│   └── test_agent_config_loading.py   # NEW - Test P3
└── e2e/
    └── test_real_llm_invocation.py    # NEW - LangSmith validation
```

**Structure Decision**: Modify existing single-project structure. Agent infrastructure (`src/agents/`) already exists from 001 implementation but was never used. This feature connects existing pieces rather than creating new architecture.

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

**No violations** - Feature fixes existing violation rather than creating new ones.

## Phase 0: Research & Technical Decisions

### Research Questions

Based on analysis from [001-testboost-core investigation](../001-testboost-core/analysis-deepagents-integration.md), key decisions are **already resolved**:

1. **Agent Framework Choice**: DeepAgents `create_deep_agent()` vs Custom `AgentAdapter`
   - **Decision**: Use DeepAgents directly (Option A from analysis)
   - **Rationale**: Reduces custom code, includes middleware (TodoList, Filesystem), leverages library features
   - **Alternative**: AgentAdapter was considered but adds maintenance burden

2. **Migration Strategy**: Big Bang vs Incremental
   - **Decision**: Incremental (Maven → Test Gen → Deployment)
   - **Rationale**: Lower risk, allows validation per workflow
   - **Alternative**: Big bang rejected due to high testing burden

3. **LangGraph Coexistence**: Keep old workflows during migration?
   - **Decision**: Yes, with deprecation warnings
   - **Rationale**: Allows rollback, gradual user migration
   - **Alternative**: Immediate deletion rejected (too risky)

4. **YAML Config Loading**: Validate at startup or runtime?
   - **Decision**: Validate at startup (fail fast)
   - **Rationale**: Respects "Zéro Complaisance"
   - **Alternative**: Runtime validation deferred errors

5. **MCP Tool Registry**: Centralized vs per-agent?
   - **Decision**: Centralized registry (`src/mcp_servers/registry.py`)
   - **Rationale**: Single source of truth, easier testing
   - **Alternative**: Per-agent rejected (duplication)

### Research Artifacts

**Output**: `research.md` with sections:
- DeepAgents API exploration (already done in 001 analysis)
- MCP tool compatibility verification
- LangSmith integration patterns
- Error handling strategies for LLM failures
- Performance benchmarks (LLM call latency)

## Phase 1: Design Artifacts

### Data Model

**Output**: `data-model.md`

**Key Entities** (from spec):

1. **LLM Agent** (runtime construct, not persisted)
   - Fields: model, tools, system_prompt, middleware, checkpointer
   - Creation: From AgentConfig via `create_deep_agent()`
   - Lifecycle: Created per workflow execution

2. **Agent Configuration** (loaded from YAML)
   - Source: `config/agents/*.yaml`
   - Validation: Pydantic models in `src/agents/loader.py`
   - Fields: name, llm settings, tools list, workflow reference

3. **Agent Session** (extends existing Session model)
   - **No schema changes** - use existing `artifacts` JSONB field
   - New artifact types: `agent_reasoning`, `llm_tool_call`, `llm_response`
   - Relationships: Session 1→N Artifacts (already exists)

4. **MCP Tool Binding** (runtime construct)
   - Creation: `llm.bind_tools(mcp_tools)`
   - Lifecycle: Per agent creation
   - Tools: From MCP servers via registry

### API Contracts

**Output**: `contracts/` (minimal, mostly internal)

**No new REST endpoints** - Feature modifies internal workflow execution

**Internal Contracts**:

```python
# src/lib/startup_checks.py
async def check_llm_connection() -> bool:
    """
    Verify configured LLM provider is accessible.

    Returns:
        True if connection successful

    Raises:
        LLMProviderError: If connection fails
    """

# src/workflows/maven_maintenance_agent.py
async def run_maven_maintenance_with_agent(
    project_path: str,
    user_approved: bool = False
) -> dict:
    """
    Run Maven maintenance using DeepAgents LLM agent.

    Args:
        project_path: Path to Maven project
        user_approved: Auto-approve updates (autonomous mode)

    Returns:
        Workflow result dict with messages, artifacts, completed status

    Raises:
        LLMError: If agent execution fails
    """
```

### Quickstart Guide

**Output**: `quickstart.md`

**Integration Scenarios**:

1. **As a Developer**: Testing LLM connectivity before workflows
2. **As a CLI User**: Running Maven maintenance with agents
3. **As an Administrator**: Configuring agent behavior via YAML
4. **As a Tester**: Validating LangSmith traces

## Phase 1.5: Agent Context Update

*This phase runs automatically during planning*

**Action**: Run `.specify/scripts/powershell/update-agent-context.ps1 -AgentType claude`

**Expected Changes**:
- Add "DeepAgents 0.2.7" to technology list
- Add "LangSmith tracing" to features list
- Preserve manual additions between markers

## Phase 2: Implementation Tasks

**Output**: `tasks.md` (generated by `/speckit.tasks` command, NOT this plan)

**Task Categories** (preview):

1. **Setup** (P1)
   - Create `src/lib/startup_checks.py`
   - Modify `src/api/main.py` and `src/cli/main.py`

2. **Core** (P2)
   - Create `src/mcp_servers/registry.py`
   - Create `src/workflows/maven_maintenance_agent.py`
   - Update `src/cli/commands/maintenance.py` to use agent workflow

3. **Testing** (P1, P2, P3)
   - Integration tests for LLM connectivity
   - E2E tests with real LLM API calls
   - LangSmith trace validation

4. **Documentation**
   - Update README with agent requirements
   - Add troubleshooting for LLM connection errors

**Dependency Graph**:
```
P1 (LLM Check) → Must complete before P2
P2 (Maven Agent) → Depends on P1
P3 (Config Loading) → Can be parallel with P2
```

## Post-Phase-1 Constitution Re-Check

After design phase:

### 1. Zéro Complaisance ✅

**Design Compliance**:
- LLM check in `startup_checks.py` raises exception if fail
- No fallback to deterministic logic
- LangSmith tracing proves real LLM calls

### 2. Outils via MCP Exclusivement ✅

**Design Compliance**:
- `create_deep_agent()` receives MCP tools via `tools=` parameter
- Tool registry centralizes MCP server imports
- No direct tool calls in agent workflow

### 3. Pas de Mocks en Production ✅

**Design Compliance**:
- E2E tests use real LLM APIs
- Test suite requires valid API keys
- LangSmith validates real invocations

### All Other Principles ✅

**Design Compliance**: No changes to other principles

**GATE RESULT**: ✅ **PASS** - Design respects all constitutional principles

## Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| LLM cost exceeds budget | Medium | High | Use Gemini Flash (1500 free req/day), implement P1 first to fail fast |
| DeepAgents API breaking changes | Low | High | Pin version 0.2.7, monitor releases |
| LangSmith tracing unavailable | Low | Low | Make optional, log warning if missing |
| YAML config parsing errors | Medium | Medium | Validate at startup, clear error messages |
| MCP tools incompatible with LangChain | Low | High | Already tested in 001, BaseTool interface confirmed |
| Performance degradation (LLM latency) | High | Medium | Use fast model (Gemini Flash), parallel tool calls |
| User confusion (two workflows) | Medium | Low | Deprecation warnings, migration guide |

## Success Metrics

| Metric | Target | Validation Method |
|--------|--------|-------------------|
| Startup check coverage | 100% | All 3 providers tested (Gemini/Claude/GPT-4o) |
| LLM calls per workflow | ≥3 | LangSmith trace count |
| Agent config loading | 100% | All 3 YAML files loaded without errors |
| CHK checks unblocked | 9/9 | E2E checklist validation |
| Zero workflows without LLM | 100% | SC-008 validation |
| Constitution compliance | 13/13 | All principles respected |

## Timeline Estimate

**P1 (LLM Connectivity Check)**: 1-2 hours
- Create startup_checks.py
- Modify main.py files
- Write integration tests

**P2 (Maven Agent Workflow)**: 4-6 hours
- Create MCP tool registry
- Create agent workflow
- Update CLI command
- Write E2E tests with real LLM
- Validate LangSmith traces

**P3 (Agent Config)**: 1-2 hours
- Verify YAML loading
- Test prompt template injection
- Validate config changes

**Testing & Validation**: 2-3 hours
- Run full E2E suite
- Validate all 9 blocked checks
- Performance testing

**Total**: 8-13 hours (1-2 days)

## Next Steps

1. Run `/speckit.tasks` to generate detailed task breakdown
2. Implement P1 (LLM connectivity check) - highest priority
3. Validate P1 with CHK003, CHK020 tests
4. Implement P2 (Maven agent workflow)
5. Validate P2 with CHK097, CHK095 tests
6. Implement P3 (config loading)
7. Run full E2E suite from 001-testboost-core checklist
8. Update 001 checklist to mark unblocked

---

**Branch**: `002-deepagents-integration`
**Status**: Plan Complete - Ready for `/speckit.tasks`
**Dependencies**: None - All prerequisites from 001 already met
**Blockers**: None - All technical decisions resolved
