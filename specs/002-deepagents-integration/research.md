# Research & Technical Decisions: DeepAgents LLM Integration

**Feature**: 002-deepagents-integration
**Date**: 2025-11-28
**Status**: Complete

## Overview

This document consolidates technical research performed during the architectural analysis of 001-testboost-core (see parent feature investigation) and documents key technical decisions for implementing LLM agent integration.

---

## Decision 1: Agent Framework Selection

**Question**: Use DeepAgents `create_deep_agent()` directly or implement custom `AgentAdapter`?

**Decision**: **DeepAgents `create_deep_agent()` directly** (Option A)

**Rationale**:
- Reduces custom code maintenance (~200 lines saved)
- Built-in middleware: TodoListMiddleware, FilesystemMiddleware, SubAgentMiddleware
- Automatic summarization for long contexts (170k tokens threshold)
- Prompt caching support (Anthropic)
- Battle-tested by Anthropic team

**Alternatives Considered**:
1. **Custom AgentAdapter** (src/agents/adapter.py exists but unused)
   - Pro: More control over agent behavior
   - Con: Maintenance burden, missing middleware features
   - **Rejected**: Overhead not justified

2. **LangGraph StateGraph without agents**
   - Pro: Current implementation (deterministic)
   - Con: Violates "Zéro Complaisance" - no real AI reasoning
   - **Rejected**: Constitutional violation

**Implementation**:
```python
from deepagents import create_deep_agent

agent = create_deep_agent(
    model=llm,  # From src.lib.llm.get_llm()
    system_prompt=prompt_template,  # From config/prompts/
    tools=mcp_tools,  # From MCP servers
    checkpointer=postgres_checkpointer  # For pause/resume
)
```

**References**:
- `.venv/Lib/site-packages/deepagents/graph.py:39-146`
- Analysis: `specs/001-testboost-core/plan.md` (if created with analysis)

---

## Decision 2: Migration Strategy

**Question**: Migrate all workflows at once (big bang) or incrementally?

**Decision**: **Incremental Migration** (Maven → Test Gen → Deployment)

**Rationale**:
- Lower risk: Can validate each workflow independently
- Easier rollback: Old workflow code remains during migration
- Better testing: Focus E2E validation on one workflow at a time
- User flexibility: Gradual adoption with deprecation warnings

**Alternatives Considered**:
1. **Big Bang Migration**
   - Pro: Clean cutover, no duplicate code
   - Con: High risk, all-or-nothing testing, hard to debug
   - **Rejected**: Too risky for production system

2. **Parallel Implementation (no deprecation)**
   - Pro: Both versions always available
   - Con: Permanent code duplication, confusion
   - **Rejected**: Maintenance nightmare

**Implementation Timeline**:
1. **Phase 1**: Maven maintenance workflow → `maven_maintenance_agent.py`
2. **Phase 2** (optional): Test generation → `test_generation_agent.py`
3. **Phase 3** (optional): Docker deployment → `docker_deployment_agent.py`
4. **Cleanup**: Remove old workflows after 2-4 weeks validation

**Deprecation Strategy**:
```python
# src/workflows/maven_maintenance.py
import warnings

warnings.warn(
    "maven_maintenance.run_maven_maintenance() is deprecated. "
    "Use maven_maintenance_agent.run_maven_maintenance_with_agent() instead.",
    DeprecationWarning,
    stacklevel=2
)
```

---

## Decision 3: LLM Connectivity Check Timing

**Question**: Validate LLM connectivity at startup or on-demand per workflow?

**Decision**: **Startup Validation** (fail-fast approach)

**Rationale**:
- Respects "Zéro Complaisance": No workflows execute with fake agents
- Better UX: User knows immediately if config is wrong
- Faster debugging: Don't wait for workflow to fail mid-execution
- Aligns with SC-001: "Startup fails within 5 seconds if LLM unavailable"

**Alternatives Considered**:
1. **On-Demand Validation** (check before each workflow)
   - Pro: Handles transient API key changes
   - Con: Delayed error discovery, violates fail-fast
   - **Rejected**: Poor UX, violates constitution

2. **No Validation** (let workflows fail naturally)
   - Pro: Minimal code
   - Con: Violates "Zéro Complaisance" - workflows might run without agents
   - **Rejected**: Constitutional violation

**Implementation**:
```python
# src/lib/startup_checks.py
async def check_llm_connection() -> bool:
    """Ping LLM provider with minimal request."""
    try:
        llm = get_llm()  # Configured model
        await llm.ainvoke([HumanMessage(content="ping")])
        logger.info("llm_connection_ok", model=settings.model)
        return True
    except Exception as e:
        logger.error("llm_connection_failed", error=str(e))
        raise LLMProviderError(f"LLM not available: {e}")

# src/api/main.py
@app.on_event("startup")
async def startup():
    await check_llm_connection()  # Blocks startup if fails

# src/cli/main.py
@app.callback()
def main():
    asyncio.run(check_llm_connection())  # Blocks CLI if fails
```

**Validation**: CHK003, CHK020, CHK090

---

## Decision 4: MCP Tool Registry Architecture

**Question**: Load MCP tools centrally or per-agent?

**Decision**: **Centralized MCP Tool Registry**

**Rationale**:
- Single source of truth for tool availability
- Easier testing (mock registry vs individual tools)
- Consistent tool bindings across agents
- Facilitates tool versioning and upgrades

**Alternatives Considered**:
1. **Per-Agent Tool Loading** (each agent imports its MCP servers)
   - Pro: Isolation, agent-specific tools
   - Con: Code duplication, inconsistent bindings
   - **Rejected**: DRY violation

2. **Dynamic Discovery** (scan MCP servers at runtime)
   - Pro: Auto-discovery of new servers
   - Con: Startup overhead, unpredictable failures
   - **Rejected**: Violates fail-fast principle

**Implementation**:
```python
# src/mcp_servers/registry.py (NEW)
from langchain_core.tools import BaseTool

def get_mcp_tool_registry() -> dict[str, list[BaseTool]]:
    """
    Get all MCP tools organized by server.

    Returns:
        Dict mapping server name to list of LangChain tools
    """
    from src.mcp_servers.maven_maintenance import get_tools as get_maven
    from src.mcp_servers.git_maintenance import get_tools as get_git
    from src.mcp_servers.docker import get_tools as get_docker
    from src.mcp_servers.test_generator import get_tools as get_test_gen

    return {
        "maven-maintenance": get_maven(),
        "git-maintenance": get_git(),
        "docker-deployment": get_docker(),
        "test-generator": get_test_gen(),
    }

# Usage in agent creation
registry = get_mcp_tool_registry()
maven_tools = registry["maven-maintenance"]
agent = create_deep_agent(model=llm, tools=maven_tools, ...)
```

**Note**: MCP servers must expose `get_tools() -> list[BaseTool]` function (may require implementation).

---

## Decision 5: Agent Configuration Validation

**Question**: Validate YAML configs at startup or on-demand?

**Decision**: **Startup Validation** (consistent with LLM check)

**Rationale**:
- Fail-fast: User knows immediately if YAML is malformed
- Prevents runtime surprises mid-workflow
- Aligns with "Zéro Complaisance"

**Implementation**:
```python
# src/api/main.py / src/cli/main.py
@app.on_event("startup")
async def startup():
    await check_llm_connection()

    # Validate agent configs
    loader = AgentLoader("config/agents")
    try:
        loader.load_agent("maven_maintenance_agent")
        loader.load_agent("test_gen_agent")
        loader.load_agent("deployment_agent")
        logger.info("agent_configs_validated", count=3)
    except ValidationError as e:
        logger.error("agent_config_invalid", error=str(e))
        raise ConfigurationError(f"Invalid agent config: {e}")
```

**Validation**: CHK095, CHK096

---

## Decision 6: LangSmith Integration

**Question**: Make LangSmith required or optional?

**Decision**: **Optional with Graceful Degradation**

**Rationale**:
- Not all users have LangSmith API keys
- Tracing is useful but not critical for functionality
- Can still validate LLM calls via logs if LangSmith unavailable

**Implementation**:
```python
# src/lib/llm.py (already implemented)
if settings.langsmith_api_key and settings.langsmith_tracing:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
    logger.info("langsmith_tracing_enabled")
else:
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    logger.warning("langsmith_tracing_disabled")
```

**Alternative**: Could require LangSmith for E2E tests but make optional for production.

**Validation**: CHK084 (skipped if LangSmith not configured)

---

## Decision 7: Error Handling for LLM Failures

**Question**: Retry strategy for LLM API errors?

**Decision**: **3 Retries with Exponential Backoff** (existing pattern)

**Rationale**:
- Handles transient failures (network, rate limits)
- Already implemented in `src.lib.llm.invoke_with_retry`
- Aligns with Constitution §10 (Robustesse)

**Retry Config**:
```python
# src/lib/llm.py (already implemented)
MAX_RETRIES = 3
MIN_WAIT = 1  # seconds
MAX_WAIT = 10  # seconds

@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT, max=MAX_WAIT),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
)
async def invoke_with_retry(llm, messages, timeout=120):
    ...
```

**Non-Retryable Errors**:
- Invalid API key (403) → Fail immediately
- Quota exceeded (429) → Log clear error, suggest waiting
- Model not found (404) → Configuration error, fail immediately

**Validation**: SC-010 (failure rate <5% with retry)

---

## Decision 8: Session Artifact Storage

**Question**: Create new database tables for agent reasoning or reuse existing artifacts?

**Decision**: **Reuse Existing `artifacts` JSONB Field**

**Rationale**:
- No schema migration required (avoids complexity)
- `artifacts` JSONB is flexible enough for agent data
- Session model already has artifact relationship
- Easier rollback if agents don't work out

**Artifact Types**:
```python
# New artifact types (stored in artifacts.artifact_type)
- "agent_reasoning": LLM reasoning text
- "llm_tool_call": Tool call with args/results
- "llm_response": Raw LLM response
- "llm_metrics": Tokens, duration, cost estimate
```

**Alternatives Considered**:
1. **New `agent_executions` Table**
   - Pro: Structured schema, easier queries
   - Con: Migration complexity, overkill for JSON data
   - **Rejected**: Over-engineering

**Implementation**:
```python
# Store agent reasoning
await create_artifact(
    session_id=session.id,
    artifact_type="agent_reasoning",
    content={
        "agent": "maven_maintenance_agent",
        "reasoning": response.content,
        "tool_calls": [{"name": "analyze-dependencies", "args": {...}}]
    }
)
```

**Validation**: CHK082 (agent decisions documented)

---

## Decision 9: Performance Optimization

**Question**: How to minimize LLM call latency impact?

**Decision**: **Use Fast Model + Parallel Tool Calls**

**Rationale**:
- Gemini Flash: ~500ms latency vs Claude Sonnet ~2s
- 1500 free requests/day (adequate for testing)
- Parallel tool calls when possible

**Model Selection**:
- **Primary**: `google-genai/gemini-2.5-flash-preview-09-2025` (fast, cheap)
- **Alternative**: `anthropic/claude-sonnet-4-5` (better reasoning, slower)
- **Testing**: `openai/gpt-4o` (balanced)

**Optimization Techniques**:
```python
# Use streaming for long responses (future)
agent = create_deep_agent(..., streaming=True)

# Parallel tool calls (DeepAgents supports natively)
# Agent will call multiple tools concurrently if independent

# Prompt caching (Anthropic only)
# DeepAgents includes AnthropicPromptCachingMiddleware
```

**Validation**: P2 (Maven workflow <2min for simple projects)

---

## Decision 10: Backward Compatibility

**Question**: How long to keep old workflows?

**Decision**: **2-4 Weeks Deprecation Period**

**Rationale**:
- Gives users time to test new agent workflows
- Allows rollback if critical issues found
- Deprecation warnings educate users

**Timeline**:
1. **Week 1-2**: Both workflows available, old one shows deprecation warning
2. **Week 3-4**: Monitor usage, fix issues in agent workflow
3. **Week 5+**: Remove old workflows if adoption successful

**Rollback Plan**:
- Keep old workflow files until agent version validated
- Document migration path in README
- CLI flag to force old workflow: `--no-agent` (if needed)

---

## Research Summary

All technical decisions are **resolved and documented**. No remaining "NEEDS CLARIFICATION" items.

**Key Takeaways**:
1. Use DeepAgents `create_deep_agent()` directly (not custom adapter)
2. Validate LLM + YAML configs at startup (fail-fast)
3. Centralized MCP tool registry for consistency
4. Incremental migration (Maven first)
5. Optional LangSmith, required functionality without it
6. Reuse existing artifacts table (no schema changes)
7. Gemini Flash for speed, Anthropic for quality
8. 2-4 week deprecation period for old workflows

**Next Phase**: Generate data-model.md, contracts/, and quickstart.md
