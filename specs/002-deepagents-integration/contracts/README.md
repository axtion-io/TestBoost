# API Contracts: DeepAgents LLM Integration

**Feature**: 002-deepagents-integration

## Overview

This feature introduces **NO new REST API endpoints**. All changes are internal to workflow execution. This document defines internal Python contracts for the new agent infrastructure.

---

## Internal Contracts

### 1. Startup Validation Contract

**Module**: `src/lib/startup_checks.py`

```python
async def check_llm_connection() -> bool:
    """
    Verify configured LLM provider is accessible.

    Returns:
        True if connection successful

    Raises:
        LLMProviderError: If LLM provider not configured or unreachable
        AuthenticationError: If API key invalid
        NetworkError: If network connectivity issues

    Example:
        >>> await check_llm_connection()
        True  # Gemini API accessible

        >>> await check_llm_connection()
        LLMProviderError: GOOGLE_API_KEY not configured
    """
```

**Contract Guarantees**:
- Called during application startup (API and CLI)
- Blocks startup if LLM unavailable
- Logs clear error messages with actionable guidance
- Returns within 5 seconds or raises timeout

---

### 2. Agent Workflow Contract

**Module**: `src/workflows/maven_maintenance_agent.py`

```python
async def run_maven_maintenance_with_agent(
    project_path: str,
    user_approved: bool = False
) -> dict:
    """
    Run Maven dependency maintenance using DeepAgents LLM agent.

    Args:
        project_path: Absolute path to Maven project root (must contain pom.xml)
        user_approved: Auto-approve all updates (autonomous mode). Default: False (interactive)

    Returns:
        Workflow result dict with keys:
        - session_id: UUID of workflow session
        - status: "completed" | "failed" | "cancelled"
        - messages: List of user-facing messages
        - artifacts: List of artifact dicts (reasoning, tool calls, metrics)
        - completed: ISO8601 timestamp
        - errors: List of error messages (empty if successful)

    Raises:
        LLMError: If LLM invocation fails after retries
        MCPToolError: If MCP tool execution fails
        ValidationError: If project_path invalid or pom.xml missing
        ConfigurationError: If agent config invalid

    Example:
        >>> result = await run_maven_maintenance_with_agent(
        ...     project_path="/path/to/spring-petclinic",
        ...     user_approved=True
        ... )
        >>> result["status"]
        "completed"
        >>> len(result["artifacts"])
        8  # 3 reasoning + 3 tool calls + 2 metrics

    Side Effects:
        - Creates session record in database
        - Creates artifact records (agent_reasoning, llm_tool_call, llm_metrics)
        - Sends traces to LangSmith (if enabled)
        - May modify pom.xml if updates approved
        - May create Git commits (if Git MCP tool used)
    """
```

**Contract Guarantees**:
- At least 3 LLM API calls per execution (SC-002)
- All tool calls traced to LangSmith when enabled (SC-005)
- Agent reasoning stored in artifacts (FR-008)
- Retry logic for transient failures (FR-009)
- Workflow fails if LLM unavailable (FR-010)

---

### 3. MCP Tool Registry Contract

**Module**: `src/mcp_servers/registry.py`

```python
def get_mcp_tool_registry() -> dict[str, list[BaseTool]]:
    """
    Get all MCP tools organized by server.

    Returns:
        Dict mapping server name to list of LangChain BaseTool instances:
        {
            "maven-maintenance": [AnalyzeDependenciesTool, UpdateDependenciesTool, ...],
            "git-maintenance": [GitCommitTool, GitPushTool, ...],
            "docker-deployment": [DockerBuildTool, DockerRunTool, ...],
            "test-generator": [GenerateTestTool, ValidateTestTool, ...]
        }

    Raises:
        MCPToolError: If any MCP server missing or tools invalid

    Example:
        >>> registry = get_mcp_tool_registry()
        >>> maven_tools = registry["maven-maintenance"]
        >>> len(maven_tools)
        3  # analyze-dependencies, update-dependencies, validate-build

    Caching:
        Tools are loaded once at startup and cached in memory.
        Changes to MCP servers require application restart.
    """
```

**Contract Guarantees**:
- All MCP servers expose `get_tools() -> list[BaseTool]` function
- Tools are LangChain-compatible (inherit from BaseTool)
- Registry validated at startup (FR-014)
- Centralized source of truth for tool availability

---

### 4. Agent Configuration Loader Contract

**Module**: `src/agents/loader.py` (existing, no changes)

```python
class AgentLoader:
    """Load and validate agent configurations from YAML files."""

    def load_agent(self, agent_name: str) -> AgentConfig:
        """
        Load agent configuration from YAML file.

        Args:
            agent_name: Name of agent config file (without .yaml extension)

        Returns:
            Validated AgentConfig object with fields:
            - name: str
            - identity: IdentityConfig (role, persona)
            - llm: LLMConfig (provider, model, temperature, max_tokens)
            - tools: ToolsConfig (mcp_servers list)
            - prompts: PromptsConfig (system prompt path)
            - workflow: WorkflowConfig (graph_name, node_name)
            - error_handling: ErrorConfig (max_retries, timeout_seconds)

        Raises:
            FileNotFoundError: If config file not found
            ValidationError: If YAML schema invalid
            ConfigurationError: If referenced files missing (prompt templates)

        Example:
            >>> loader = AgentLoader("config/agents")
            >>> config = loader.load_agent("maven_maintenance_agent")
            >>> config.llm.model
            "gemini-2.5-flash-preview-09-2025"
            >>> config.llm.temperature
            0.3
        """

    def load_prompt_template(self, path: str) -> str:
        """
        Load Markdown prompt template from config directory.

        Args:
            path: Relative path from project root to Markdown file

        Returns:
            Markdown content as string

        Raises:
            FileNotFoundError: If template file not found
            UnicodeDecodeError: If file encoding invalid

        Example:
            >>> config = loader.load_agent("maven_maintenance_agent")
            >>> prompt = loader.load_prompt_template(config.prompts.system)
            >>> "Maven Dependency Update Agent" in prompt
            True
        """
```

**Contract Guarantees**:
- YAML configs validated at startup (FR-004, SC-006)
- Pydantic schema enforcement for required fields
- Clear error messages for malformed configs
- Prompt templates loaded with UTF-8 encoding

---

## REST API Changes

**Summary**: No new endpoints, no breaking changes to existing endpoints.

**Affected Endpoints**: None

**Database Schema Changes**: None (reuse existing `artifacts` JSONB field)

---

## CLI Changes

**Summary**: No new commands, internal execution behavior changes only.

**Affected Commands**:
- `testboost maintenance maven` - Now uses agent workflow instead of deterministic StateGraph
- `testboost test generate` - Will use agent workflow (future, Phase 2/3)
- `testboost deploy docker` - Will use agent workflow (future, Phase 2/3)

**User-Visible Changes**:
- Logs will show agent reasoning steps
- LangSmith traces available (if enabled)
- Startup may fail with LLM connectivity errors (new behavior)

**Backward Compatibility**: Old workflows deprecated with warnings, removed after 2-4 weeks

---

## Error Response Format

**New Errors Introduced**:

### LLMProviderError

```python
class LLMProviderError(Exception):
    """Raised when LLM provider not accessible."""

# Example response (startup failure)
{
    "error": "LLMProviderError",
    "message": "LLM not available: GOOGLE_API_KEY not configured",
    "remediation": "Set GOOGLE_API_KEY environment variable or use alternative provider (ANTHROPIC_API_KEY, OPENAI_API_KEY)",
    "timestamp": "2025-11-28T10:00:00Z"
}
```

### AgentExecutionError

```python
class AgentExecutionError(Exception):
    """Raised when agent workflow fails."""

# Example response (workflow failure)
{
    "error": "AgentExecutionError",
    "message": "Agent execution failed after 3 retries",
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "llm_calls": 2,  # Number of successful LLM calls before failure
    "last_error": "RateLimitError: 429 Too Many Requests",
    "timestamp": "2025-11-28T10:05:00Z"
}
```

---

## Data Contracts

### Artifact Types

**New artifact_type values** stored in `artifacts` table:

```python
# Agent reasoning text
{
    "artifact_type": "agent_reasoning",
    "content": {
        "agent": "maven_maintenance_agent",
        "reasoning": "Analyzing 47 dependencies. Found 5 outdated...",
        "model": "gemini-2.5-flash",
        "timestamp": "2025-11-28T10:30:00Z"
    }
}

# Tool call with arguments and results
{
    "artifact_type": "llm_tool_call",
    "content": {
        "tool_name": "analyze-dependencies",
        "arguments": {"project_path": "/path/to/project"},
        "result": {"outdated_count": 5, "vulnerable_count": 2},
        "duration_ms": 1234
    }
}

# Raw LLM response
{
    "artifact_type": "llm_response",
    "content": {
        "role": "assistant",
        "content": "I've analyzed the project dependencies...",
        "model": "gemini-2.5-flash",
        "finish_reason": "stop"
    }
}

# LLM metrics
{
    "artifact_type": "llm_metrics",
    "content": {
        "prompt_tokens": 1523,
        "completion_tokens": 487,
        "total_tokens": 2010,
        "duration_ms": 1876,
        "cost_estimate_usd": 0.0003,
        "model": "gemini-2.5-flash"
    }
}
```

**Backward Compatibility**: Old artifact types unchanged, queries must filter by `artifact_type`

---

## Testing Contracts

### Integration Test Contract

```python
# tests/integration/test_llm_connectivity.py
@pytest.mark.integration
@pytest.mark.asyncio
async def test_llm_connection_success():
    """
    Test successful LLM connection.

    Preconditions:
        - Valid GOOGLE_API_KEY in environment
        - Network connectivity to generativelanguage.googleapis.com

    Postconditions:
        - Returns True
        - Logs "llm_connection_ok" message
        - Completes within 5 seconds
    """
```

### E2E Test Contract

```python
# tests/e2e/test_real_llm_invocation.py
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_maven_workflow_llm_calls(sample_java_project):
    """
    Verify Maven workflow invokes real LLM agent.

    Preconditions:
        - Valid LLM API key
        - Sample Java project with pom.xml
        - LangSmith tracing enabled

    Postconditions:
        - Workflow status "completed"
        - ≥3 LLM API calls
        - ≥3 tool calls traced in LangSmith
        - Agent reasoning stored in artifacts
        - Session record created
    """
```

---

## Version Compatibility

| Component | Minimum Version | Tested Version |
|-----------|----------------|----------------|
| DeepAgents | 0.2.7 | 0.2.7 |
| LangChain Core | 1.1.0 | 1.1.7 |
| LangGraph | 1.0.0 | 1.0.12 |
| Python | 3.11 | 3.11.9 |
| PostgreSQL | 15.0 | 15.8 |

---

## References

- **DeepAgents API**: `.venv/Lib/site-packages/deepagents/graph.py`
- **Agent Loader**: `src/agents/loader.py`
- **MCP Tool Base**: `langchain_core.tools.BaseTool`
- **Session Model**: `src/db/models.py`
- **Error Definitions**: `src/lib/exceptions.py`

---

**Status**: Complete - No external API contracts required (all internal)
**Next Step**: Phase 1.5 (update agent context)
