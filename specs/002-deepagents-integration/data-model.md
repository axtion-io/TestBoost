# Data Model: DeepAgents LLM Integration

**Feature**: 002-deepagents-integration
**Date**: 2025-11-28
**Status**: Complete

## Overview

This document describes the data entities and relationships for integrating DeepAgents LLM framework into TestBoost workflows. **Critical note**: This feature requires **NO database schema changes**. All agent data reuses the existing `artifacts` JSONB field in the Session model.

---

## Entity Diagram

```
┌─────────────────────┐
│  AgentConfiguration │ (YAML file)
│  config/agents/*.yaml│
└──────────┬──────────┘
           │ loads into
           ▼
┌─────────────────────┐      ┌──────────────────┐
│     LLM Agent       │◄─────┤ System Prompt    │ (Markdown file)
│  (Runtime Object)   │      │ config/prompts/* │
└──────────┬──────────┘      └──────────────────┘
           │
           │ uses
           ▼
┌─────────────────────┐      ┌──────────────────┐
│  MCP Tool Binding   │◄─────┤  MCP Servers     │
│  (Runtime Object)   │      │  src/mcp_servers/│
└─────────────────────┘      └──────────────────┘
           │
           │ executes within
           ▼
┌─────────────────────┐      ┌──────────────────┐
│   Agent Session     │─────►│   Artifact       │ (existing)
│  (Database: Session)│ 1:N  │ (Database: JSON) │
└─────────────────────┘      └──────────────────┘
```

---

## Entity Definitions

### 1. LLM Agent

**Type**: Runtime construct (not persisted to database)

**Purpose**: Represents a configured AI agent created via DeepAgents `create_deep_agent()` function.

**Attributes**:
- `model`: LangChain LLM instance (e.g., ChatGoogleGenerativeAI)
- `tools`: List of bound MCP tools (LangChain BaseTool instances)
- `system_prompt`: Loaded Markdown prompt template
- `middleware`: DeepAgents middleware stack (TodoList, Filesystem, SubAgent)
- `checkpointer`: PostgreSQL checkpointer for pause/resume
- `streaming`: Boolean for streaming responses (future)

**Lifecycle**:
1. Created at workflow start via `create_deep_agent()`
2. Executes tool calls via MCP servers
3. Generates reasoning stored in artifacts
4. Destroyed at workflow end

**Relationships**:
- Created from: AgentConfiguration (YAML)
- Uses: System Prompt (Markdown)
- Uses: MCP Tool Binding (runtime)
- Executes within: Agent Session (database)

**Implementation Reference**:
```python
# src/workflows/maven_maintenance_agent.py
from deepagents import create_deep_agent
from src.lib.llm import get_llm
from src.agents.loader import AgentLoader

loader = AgentLoader("config/agents")
config = loader.load_agent("maven_maintenance_agent")

agent = create_deep_agent(
    model=get_llm(),
    system_prompt=config.system_prompt,  # Loaded from Markdown
    tools=mcp_tools,  # From registry
    checkpointer=postgres_checkpointer
)
```

---

### 2. Agent Configuration

**Type**: YAML file (loaded at runtime, validated at startup)

**Source**: `config/agents/*.yaml`

**Purpose**: Defines agent identity, LLM settings, tools, workflow reference, error handling.

**Schema** (existing, defined by `src/agents/loader.py`):
```yaml
name: "maven_maintenance_agent"
identity:
  role: "Maven Dependency Maintenance Specialist"
  persona: "Thorough, security-conscious, risk-aware"

llm:
  provider: "google-genai"  # google-genai | anthropic | openai
  model: "gemini-2.5-flash-preview-09-2025"
  temperature: 0.3
  max_tokens: 8192

tools:
  mcp_servers:
    - "maven-maintenance"
    - "git-maintenance"

prompts:
  system: "config/prompts/maven/dependency_update.md"

workflow:
  graph_name: "maven_maintenance"
  node_name: "analyze_dependencies"

error_handling:
  max_retries: 3
  timeout_seconds: 120
```

**Attributes**:
- `name`: Unique agent identifier
- `identity`: Role and persona for LLM context
- `llm`: Provider, model, parameters
- `tools.mcp_servers`: List of MCP server names to bind
- `prompts.system`: Path to Markdown prompt template
- `workflow`: Integration points in LangGraph
- `error_handling`: Retry and timeout config

**Lifecycle**:
1. Loaded by `AgentLoader` at application startup
2. Validated against Pydantic schema
3. Used to create LLM Agent instances per workflow execution
4. Reloaded if file changes (requires restart)

**Validation**:
- Validated at startup via `src/lib/startup_checks.py`
- Application fails to start if YAML is malformed
- Pydantic model ensures required fields present

**Relationships**:
- Loaded by: AgentLoader (Python)
- Creates: LLM Agent (runtime)
- References: System Prompt (Markdown file path)
- References: MCP Servers (via tool list)

---

### 3. Agent Session

**Type**: Database entity (extends existing Session model)

**Purpose**: Tracks workflow execution with agent invocations, tool calls, reasoning steps.

**Database Table**: `sessions` (existing, NO schema changes)

**Relevant Fields**:
- `id`: UUID (primary key)
- `workflow_type`: Enum (e.g., "maven_maintenance")
- `status`: Enum (pending, running, completed, failed)
- `created_at`: Timestamp
- `updated_at`: Timestamp
- `metadata`: JSONB (existing, optional extra data)

**New Data Pattern** (stored in related Artifact records):

Instead of modifying the Session schema, agent data is stored as Artifacts linked to the session:

```python
# New artifact types for agent integration
artifact_types = [
    "agent_reasoning",    # LLM reasoning text
    "llm_tool_call",      # Tool call with args/results
    "llm_response",       # Raw LLM response
    "llm_metrics"         # Tokens, duration, cost estimate
]
```

**Example Artifact Storage**:
```python
# src/workflows/maven_maintenance_agent.py
from src.db.crud import create_artifact

# Store agent reasoning
await create_artifact(
    session_id=session.id,
    artifact_type="agent_reasoning",
    content={
        "agent": "maven_maintenance_agent",
        "reasoning": response.content,
        "model": "gemini-2.5-flash",
        "timestamp": "2025-11-28T10:30:00Z"
    }
)

# Store tool call
await create_artifact(
    session_id=session.id,
    artifact_type="llm_tool_call",
    content={
        "tool_name": "analyze-dependencies",
        "arguments": {"project_path": "/path/to/project"},
        "result": {"outdated_count": 5, "vulnerable_count": 2},
        "duration_ms": 1234
    }
)

# Store LLM metrics
await create_artifact(
    session_id=session.id,
    artifact_type="llm_metrics",
    content={
        "prompt_tokens": 1523,
        "completion_tokens": 487,
        "total_tokens": 2010,
        "duration_ms": 1876,
        "cost_estimate_usd": 0.0003
    }
)
```

**Relationships**:
- Session 1:N Artifacts (existing relationship)
- Session references Workflow Type (enum)
- Artifacts contain agent reasoning, tool calls, metrics

**Lifecycle**:
1. Session created when workflow starts
2. Artifacts created during agent execution
3. Session marked completed/failed at workflow end
4. Artifacts retained for audit/analysis

**Migration Impact**: **NONE** - Reuses existing schema

---

### 4. MCP Tool Binding

**Type**: Runtime construct (not persisted)

**Purpose**: Connects LLM agents to MCP tools, enabling tool discovery and invocation.

**Creation Pattern**:
```python
# src/mcp_servers/registry.py (NEW)
from langchain_core.tools import BaseTool
from src.mcp_servers.maven_maintenance import get_tools as get_maven_tools
from src.mcp_servers.git_maintenance import get_tools as get_git_tools

def get_mcp_tool_registry() -> dict[str, list[BaseTool]]:
    """
    Centralized registry of all MCP tools.

    Returns:
        Dict mapping server name to list of LangChain-compatible tools
    """
    return {
        "maven-maintenance": get_maven_tools(),
        "git-maintenance": get_git_tools(),
        "docker-deployment": get_docker_tools(),
        "test-generator": get_test_gen_tools(),
    }

# Usage in agent creation
registry = get_mcp_tool_registry()
maven_tools = registry["maven-maintenance"]

# Bind tools to LLM
llm = get_llm()
llm_with_tools = llm.bind_tools(maven_tools)

# Create agent with bound tools
agent = create_deep_agent(
    model=llm_with_tools,
    system_prompt=prompt,
    tools=maven_tools
)
```

**Attributes**:
- `server_name`: MCP server identifier (e.g., "maven-maintenance")
- `tools`: List of LangChain BaseTool instances
- `llm`: LLM instance with tools bound

**Lifecycle**:
1. Registry loaded at application startup (optional validation)
2. Tools retrieved from registry per workflow
3. Tools bound to LLM via `llm.bind_tools()`
4. Agent uses bound tools during execution
5. Tool calls traced to LangSmith/artifacts

**Relationships**:
- Uses: MCP Servers (source of tools)
- Used by: LLM Agent (receives bound tools)
- Referenced by: AgentConfiguration (tool list)

**MCP Server Requirements**:

Each MCP server must expose a `get_tools()` function returning LangChain-compatible tools:

```python
# src/mcp_servers/maven_maintenance/__init__.py
from langchain_core.tools import BaseTool

def get_tools() -> list[BaseTool]:
    """
    Get all Maven maintenance MCP tools.

    Returns:
        List of LangChain BaseTool instances
    """
    return [
        AnalyzeDependenciesTool(),
        UpdateDependenciesTool(),
        ValidateBuildTool(),
    ]
```

---

### 5. System Prompt

**Type**: Markdown file (loaded at runtime)

**Source**: `config/prompts/**/*.md`

**Purpose**: Defines agent behavior, response format, validation rules, reasoning patterns.

**Example Structure**:
```markdown
# Maven Dependency Update Agent

## Role
You are a Maven dependency maintenance specialist...

## Objectives
1. Analyze project dependencies for security vulnerabilities
2. Prioritize updates based on risk and breaking changes
3. Recommend update strategy with rollback plan

## Tools Available
- analyze-dependencies: Get outdated and vulnerable dependencies
- update-dependencies: Apply version updates to pom.xml
- validate-build: Run tests after updates

## Response Format
Provide analysis in this structure:
1. **Risk Assessment**: HIGH/MEDIUM/LOW with justification
2. **Update Strategy**: Prioritized list of changes
3. **Rollback Plan**: Steps to revert if issues occur

## Validation Rules
- NEVER update major versions without user approval
- ALWAYS prioritize security patches
- MUST validate build after each update
```

**Attributes**:
- `file_path`: Location in config/prompts/
- `content`: Markdown text loaded at runtime
- `variables`: Optional template variables (e.g., `{project_path}`)

**Lifecycle**:
1. Loaded by AgentLoader when creating agent
2. Variables interpolated (if any)
3. Injected as system prompt to LLM
4. Changes require workflow restart

**Relationships**:
- Referenced by: AgentConfiguration (prompts.system field)
- Used by: LLM Agent (system_prompt parameter)

**Loading Pattern**:
```python
# src/agents/loader.py (existing)
def load_prompt_template(self, path: str) -> str:
    """Load Markdown prompt template from config."""
    full_path = Path(path)
    if not full_path.exists():
        raise ConfigurationError(f"Prompt template not found: {path}")
    return full_path.read_text(encoding="utf-8")

# Usage
config = loader.load_agent("maven_maintenance_agent")
prompt = loader.load_prompt_template(config.prompts.system)
agent = create_deep_agent(system_prompt=prompt, ...)
```

---

## Data Flow

### Workflow Execution Flow

```
1. Application Startup
   ├─ Load AgentConfiguration (YAML) → Validate
   ├─ Check LLM connectivity → Fail if unavailable
   └─ Load MCP Tool Registry → Validate tools exist

2. Workflow Start (e.g., Maven Maintenance)
   ├─ Create Session record (database)
   ├─ Load System Prompt (Markdown)
   ├─ Get MCP tools from registry
   ├─ Create LLM Agent (runtime)
   │  ├─ Bind tools to LLM
   │  ├─ Inject system prompt
   │  └─ Configure middleware
   └─ Start LangGraph execution

3. Agent Execution
   ├─ LLM receives user request
   ├─ Generates tool calls
   ├─ Invokes MCP tools
   ├─ Stores tool results in Artifacts
   ├─ Generates reasoning
   └─ Stores reasoning in Artifacts

4. Workflow End
   ├─ Store final metrics in Artifacts
   ├─ Update Session status (completed/failed)
   ├─ Trace to LangSmith (if enabled)
   └─ Destroy LLM Agent (cleanup)
```

### Data Persistence

**What gets persisted**:
- Session records (workflow metadata)
- Artifact records (agent reasoning, tool calls, metrics)
- LangSmith traces (external, optional)

**What is ephemeral**:
- LLM Agent instances (runtime only)
- MCP Tool Bindings (runtime only)
- Loaded YAML configs (cached in memory)
- Loaded Markdown prompts (cached in memory)

---

## Validation and Error Handling

### Startup Validation

```python
# src/lib/startup_checks.py (NEW)
async def validate_agent_infrastructure():
    """
    Validate all agent prerequisites at startup.

    Raises:
        ConfigurationError: If YAML configs invalid
        LLMProviderError: If LLM not accessible
        MCPToolError: If tools missing
    """
    # 1. Validate LLM connectivity
    await check_llm_connection()

    # 2. Validate agent YAML configs
    loader = AgentLoader("config/agents")
    for agent_name in ["maven_maintenance_agent", "test_gen_agent", "deployment_agent"]:
        config = loader.load_agent(agent_name)
        logger.info("agent_config_validated", name=agent_name)

    # 3. Validate MCP tool registry
    registry = get_mcp_tool_registry()
    if not registry:
        raise MCPToolError("MCP tool registry is empty")
    logger.info("mcp_tools_validated", count=len(registry))
```

### Runtime Error Handling

```python
# src/workflows/maven_maintenance_agent.py
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
)
async def invoke_agent_with_retry(agent, input_data):
    """
    Invoke agent with retry logic for transient failures.

    Retries on:
    - Network errors
    - Rate limit errors (429)
    - Timeout errors

    Does NOT retry on:
    - Invalid API key (403)
    - Model not found (404)
    - Malformed input (400)
    """
    try:
        return await agent.ainvoke(input_data)
    except RateLimitError as e:
        logger.warning("llm_rate_limited", retry_after=e.retry_after)
        raise  # Will retry
    except AuthenticationError as e:
        logger.error("llm_auth_failed", error=str(e))
        raise  # Will NOT retry (fail immediately)
```

---

## Success Criteria Mapping

| Entity | Success Criteria | Validation Method |
|--------|------------------|-------------------|
| LLM Agent | SC-002: ≥3 LLM calls per workflow | LangSmith trace count |
| Agent Configuration | SC-004: Zero code changes to switch provider | Edit YAML, restart, verify new model |
| Agent Session | SC-008: Zero workflows without LLM | Query sessions where artifacts empty |
| MCP Tool Binding | SC-005: 100% tool calls traced | LangSmith shows all tool invocations |
| System Prompt | SC-003: LLM uses reasoning from prompts | Response analysis matches prompt rules |

---

## Migration Impact

**Database Schema**: **NO CHANGES REQUIRED**

- Existing `sessions` table: No modifications
- Existing `artifacts` table: No modifications
- New artifact types stored in existing JSONB field

**Backward Compatibility**:

- Old workflows: Continue to work (deprecated with warnings)
- Old artifacts: Remain queryable (different artifact_type values)
- Rollback: Delete new artifact types, remove agent workflow files

**Migration Timeline**:

1. **Week 1-2**: Agent workflows coexist with old workflows
2. **Week 3-4**: Monitor adoption, fix issues
3. **Week 5+**: Remove old workflows if validation successful

---

## References

- **Agent Infrastructure**: `src/agents/loader.py` (existing)
- **MCP Servers**: `src/mcp_servers/*/` (existing)
- **Database Models**: `src/db/models.py` (existing)
- **LLM Configuration**: `src/lib/llm.py` (existing)
- **DeepAgents API**: `.venv/Lib/site-packages/deepagents/graph.py`

---

**Status**: Complete - Ready for implementation
**Next Artifact**: `quickstart.md` (integration scenarios)
