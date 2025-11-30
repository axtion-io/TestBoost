# Phase 2 Findings: Foundational Infrastructure

**Feature**: 002-deepagents-integration
**Date**: 2025-11-30
**Tasks**: T007-T011

---

## T007: LLM Connectivity and Provider Configuration

### ✅ Status: COMPLETE

### Installed Packages

```
deepagents                   0.2.8
langchain                    1.0.8
langchain-core               1.1.0
langchain-anthropic          1.2.0
langchain-google-genai       2.1.12
langchain-openai             1.1.0
anthropic                    0.74.1
google-ai-generativelanguage 0.9.0
```

### Supported LLM Providers

**File**: `src/lib/llm.py`

#### Provider Support Matrix

| Provider | Package | Status | Model Format |
|----------|---------|--------|--------------|
| Google GenAI | `langchain-google-genai` | ✅ | `google-genai/gemini-2.5-flash-preview-09-2025` |
| Anthropic | `langchain-anthropic` | ✅ | `anthropic/claude-sonnet-4-5-20250929` |
| OpenAI | `langchain-openai` | ✅ | `openai/gpt-4` |

### Environment Configuration

**File**: `.env.example`

```env
# LLM Providers
MODEL=google-genai/gemini-2.5-flash-preview-09-2025
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key

# LangSmith Observability
LANGSMITH_API_KEY=your-langsmith-api-key
LANGSMITH_PROJECT=testboost
LANGSMITH_TRACING=true
```

### LLM Factory Function

```python
# src/lib/llm.py
def get_llm(
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Get an LLM instance based on the model identifier.

    Supports:
    - OpenAI: openai/gpt-4, openai/gpt-3.5-turbo
    - Anthropic: anthropic/claude-3-opus, anthropic/claude-3-sonnet
    - Google: google-genai/gemini-pro, google-genai/gemini-2.5-flash-preview-09-2025

    Args:
        model: Model identifier (provider/model-name format)
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured LLM instance
    """
```

### Retry Logic (A4 Edge Case)

```python
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT, max=MAX_WAIT),
    retry=retry_if_exception_type((TimeoutError, ConnectionError)),
    reraise=True,
)
async def invoke_with_retry(
    llm: BaseChatModel,
    messages: list[BaseMessage],
    timeout: int = DEFAULT_TIMEOUT,
) -> BaseMessage:
    """
    Invoke LLM with retry and timeout handling.
    """
```

**Constants**:
- `MAX_RETRIES = 3`
- `MIN_WAIT = 1` (second)
- `MAX_WAIT = 10` (seconds)

**Matches spec requirement**: A4 edge case (intermittent connectivity → exponential backoff)

### LangSmith Tracing

```python
def configure_langsmith_tracing() -> None:
    """Configure LangSmith tracing for observability."""
    if settings.langsmith_api_key and settings.langsmith_tracing:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
```

**Status**: Already implemented (SC-005 success criterion)

### Conclusion

**All LLM infrastructure exists**. No implementation needed for T007.

- ✅ Multi-provider support (Google, Anthropic, OpenAI)
- ✅ Retry with exponential backoff
- ✅ LangSmith tracing ready
- ✅ Environment-based configuration

---

## T008: DeepAgents MCP Adapter Investigation

### ✅ Status: COMPLETE (No adapter needed)

### DeepAgents Tool Binding

**File**: `.venv/Lib/site-packages/deepagents/graph.py`

```python
def create_deep_agent(
    model: str | BaseChatModel | None = None,
    tools: Sequence[BaseTool | Callable | dict[str, Any]] | None = None,
    *,
    system_prompt: str | None = None,
    middleware: Sequence[AgentMiddleware] = (),
    subagents: list[SubAgent | CompiledSubAgent] | None = None,
    response_format: ResponseFormat | None = None,
    checkpointer: Checkpointer | None = None,
    **kwargs
) -> CompiledStateGraph:
    """Create a deep agent.

    This agent will by default have access to a tool to write todos (write_todos),
    seven file and execution tools: ls, read_file, write_file, edit_file, glob, grep, execute,
    and a tool to call subagents.

    Args:
        model: The model to use. Defaults to Claude Sonnet 4.
        tools: The tools the agent should have access to.  # <-- ACCEPTS BaseTool
        system_prompt: The additional instructions the agent should have.
        ...
    """
```

### Key Finding

**`tools` parameter accepts**: `Sequence[BaseTool | Callable | dict[str, Any]]`

This means we can pass LangChain `BaseTool` instances **directly** to `create_deep_agent()`.

### No MCP Adapter Required

**Original concern** (from verification-report.md):
- MCP servers use `@server.list_tools()` decorator (MCP SDK pattern)
- Need to convert to LangChain `BaseTool` instances

**Solution**:
- Create wrapper `BaseTool` classes for each MCP tool
- MCP servers continue to use MCP SDK (no changes needed)
- Tool registry will provide `BaseTool` instances to DeepAgents

### Implementation Pattern

```python
# src/mcp_servers/registry.py (NEW FILE - T011)
from langchain_core.tools import BaseTool, tool
from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

@tool
async def maven_analyze_dependencies_tool(
    project_path: str,
    include_snapshots: bool = False,
    check_vulnerabilities: bool = True
) -> str:
    """Analyze Maven project dependencies for updates and vulnerabilities."""
    return await analyze_dependencies(
        project_path=project_path,
        include_snapshots=include_snapshots,
        check_vulnerabilities=check_vulnerabilities
    )

def get_maven_maintenance_tools() -> list[BaseTool]:
    """Get all Maven maintenance tools as BaseTool instances."""
    return [
        maven_analyze_dependencies_tool,
        maven_compile_tests_tool,
        maven_run_tests_tool,
        maven_package_tool,
    ]
```

### Conclusion

**No adapter needed**. DeepAgents natively accepts `BaseTool` instances.

**T011 will create**:
- `src/mcp_servers/registry.py` - Centralized tool registry
- `BaseTool` wrappers for each MCP tool using `@tool` decorator
- `get_{server}_tools()` functions returning `list[BaseTool]`

---

## T009: Prompt Templates Verification

### ✅ Status: COMPLETE

### Existing Prompt Templates

```
config/prompts/
├── common/
│   └── java_expert.md ✅
├── maven/
│   └── dependency_update.md ✅
├── testing/
│   ├── unit_test_strategy.md ✅
│   ├── integration_strategy.md ✅
│   └── snapshot_strategy.md ✅
└── deployment/
    └── docker_guidelines.md ✅
```

### Mapping to Spec Requirements

| Workflow | Spec Reference | File Path | Status |
|----------|----------------|-----------|--------|
| Maven Maintenance | `config/prompts/maven/dependency_update.md` | ✅ Exists | Match |
| Test Generation | (Not specified in spec) | ✅ 3 files exist | Extra |
| Docker Deployment | (Not specified in spec) | ✅ Exists | Extra |

### Sample Prompt Content

**File**: `config/prompts/maven/dependency_update.md`

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

### Agent Loader Integration

**File**: `src/agents/loader.py` (already exists)

```python
def load_prompt(self, name: str, category: str = "common") -> str:
    """Load a prompt template.

    Args:
        name: Prompt name (without .md extension)
        category: Prompt category subdirectory

    Returns:
        Prompt content

    Raises:
        FileNotFoundError: If prompt file not found
    """
    file_path = self.config_dir.parent / "prompts" / category / f"{name}.md"

    if not file_path.exists():
        raise FileNotFoundError(f"Prompt not found: {file_path}")

    with open(file_path, encoding="utf-8") as f:
        return f.read()
```

### Conclusion

**All prompt templates exist and loadable**. No implementation needed for T009.

---

## T010: YAML Schema Reconciliation

### ⚠️ Status: IN PROGRESS (Requires decision)

### Issue Summary

**Existing YAML configs** (3 files) use a **different schema** than specified in `spec.md`.

#### Existing YAML Structure

**File**: `config/agents/maven_maintenance_agent.yaml`

```yaml
name: maven_maintenance_agent
version: "1.0.0"
description: Agent for automated Maven dependency maintenance

identity:
  role: dependency_maintainer
  goal: "Safely update Maven dependencies..."
  backstory: "You are an expert DevOps engineer..."

llm:
  model: claude-sonnet-4-5-20250929  # <-- Anthropic Claude
  temperature: 0.1
  max_tokens: 4096

tools:
  - name: analyze-dependencies
    server: maven-maintenance
  - name: compile-tests
    server: maven-maintenance
  # ... (11 tools total)

mcp_servers:
  - name: maven-maintenance
    command: python
    args: ["-m", "src.mcp_servers.maven_maintenance"]
    env:
      PYTHONPATH: "${workspaceFolder}"

workflow:
  type: langgraph
  graph: src.workflows.maven_maintenance.maven_maintenance_graph
  steps:
    - name: validate_project
      timeout: 30s
    # ... (12 steps total)

error_handling:
  retry:
    max_attempts: 3
    backoff: exponential
    initial_delay: 1s

observability:
  tracing:
    enabled: true
    service_name: maven-maintenance-agent

resources:
  max_memory: 2Gi
  max_cpu: 2
  timeout: 30m

security:
  allow_network: true
  allowed_paths: ["${project_path}"]
  blocked_commands: ["rm -rf /", "sudo"]
```

**Total fields**: 13 top-level sections (name, version, description, identity, llm, tools, mcp_servers, workflow, error_handling, notifications, resources, security, observability)

#### Spec.md YAML Schema

**File**: `specs/002-deepagents-integration/data-model.md` (lines 100-128)

```yaml
name: "maven_maintenance_agent"
identity:
  role: "Maven Dependency Maintenance Specialist"
  persona: "Thorough, security-conscious, risk-aware"

llm:
  provider: "google-genai"  # <-- Google Gemini
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

**Total fields**: 7 top-level sections (name, identity, llm, tools, prompts, workflow, error_handling)

### Key Differences

| Field | Existing YAML | Spec YAML | Impact |
|-------|---------------|-----------|--------|
| `llm.model` | `claude-sonnet-4-5-20250929` | `gemini-2.5-flash-preview-09-2025` | HIGH: Different provider |
| `llm` structure | Direct model name | `provider` + `model` | MEDIUM: Schema mismatch |
| `tools` structure | List of tool objects | `mcp_servers` list | MEDIUM: Schema mismatch |
| `mcp_servers` | Server command configs | (Not present) | LOW: Extra info |
| `prompts.system` | (Not present) | Prompt file path | MEDIUM: Missing field |
| `workflow` | Full graph definition | Simple graph/node ref | MEDIUM: Schema mismatch |
| `version` | Present | Absent | LOW: Extra field |
| `observability` | Present | Absent | LOW: Extra field |
| `resources` | Present | Absent | LOW: Extra field |
| `security` | Present | Absent | LOW: Extra field |
| `notifications` | Present | Absent | LOW: Extra field |

### Root Cause

**Existing YAMLs** were created for **001-testboost-core** feature (before DeepAgents integration).

**Spec.md** was written for **002-deepagents-integration** with simpler schema.

### Options

#### Option A: Update Spec to Match Existing YAML (Recommended)

**Pros**:
- No code changes needed
- Preserves existing comprehensive configuration
- Richer feature set (resources, security, observability)

**Cons**:
- Spec becomes more complex
- Need to update data-model.md

**Implementation**:
1. Update `specs/002-deepagents-integration/data-model.md` lines 100-128
2. Keep existing YAML files unchanged
3. Update `AgentConfig` Pydantic model in `src/agents/loader.py` if needed

#### Option B: Migrate YAML to Match Spec (Breaking Change)

**Pros**:
- Simpler schema
- Matches spec documentation
- Forces minimal configuration

**Cons**:
- Need to rewrite 3 YAML files
- Lose observability/security/resources config
- Breaking change for existing workflows

**Implementation**:
1. Rewrite `config/agents/*.yaml` to match spec schema
2. Remove unused fields
3. Change Claude → Gemini
4. Update workflow references

#### Option C: Support Both Schemas (Adapter Pattern)

**Pros**:
- Backward compatible
- Gradual migration path
- No immediate breaking changes

**Cons**:
- Complex implementation
- Technical debt
- Confusing for users

**Implementation**:
1. Add schema version field to YAML
2. Create adapter in `AgentLoader` to normalize both formats
3. Deprecate old schema over time

### Recommendation

**Choose Option A**: Update spec to match existing YAML.

**Rationale**:
1. Existing YAMLs are comprehensive and production-ready
2. No breaking changes needed
3. Observability/security/resources fields are valuable
4. Simpler implementation path

**Changes required**:
- Update `specs/002-deepagents-integration/data-model.md` (lines 100-128)
- Update `specs/002-deepagents-integration/spec.md` (YAML example)
- Verify `AgentConfig` Pydantic model supports all fields

### LLM Provider Decision

**Existing YAMLs use**: `claude-sonnet-4-5-20250929` (Anthropic)
**Spec suggests**: `gemini-2.5-flash-preview-09-2025` (Google)
**`.env.example` default**: `google-genai/gemini-2.5-flash-preview-09-2025`

**Decision**: Keep Claude in YAMLs, but ensure both providers work.

**Rationale**:
- `src/lib/llm.py` already supports both
- User can override via environment variable
- No code changes needed

### Action Items (T010)

1. ✅ Document schema differences
2. ⏳ User decision: Option A, B, or C?
3. ⏳ If Option A: Update spec.md and data-model.md
4. ⏳ If Option B: Rewrite YAML files
5. ⏳ If Option C: Implement adapter

**Current status**: Awaiting user decision before proceeding.

---

## T011: MCP Tool Registry

### ⏳ Status: PENDING (Blocked by T010)

### Design

**File**: `src/mcp_servers/registry.py` (NEW)

#### Registry Structure

```python
"""Centralized registry of MCP tools as LangChain BaseTool instances."""

from langchain_core.tools import BaseTool
from typing import Callable

# Import tool wrappers (will be created)
from src.mcp_servers.maven_maintenance.langchain_tools import get_maven_tools
from src.mcp_servers.test_generator.langchain_tools import get_test_gen_tools
from src.mcp_servers.docker.langchain_tools import get_docker_tools
from src.mcp_servers.git_maintenance.langchain_tools import get_git_tools

# Tool registry mapping server name to tool getter function
TOOL_REGISTRY: dict[str, Callable[[], list[BaseTool]]] = {
    "maven-maintenance": get_maven_tools,
    "test-generator": get_test_gen_tools,
    "docker-deployment": get_docker_tools,
    "git-maintenance": get_git_tools,
}

def get_tools_for_servers(server_names: list[str]) -> list[BaseTool]:
    """
    Get all tools for the specified MCP servers.

    Args:
        server_names: List of MCP server names

    Returns:
        Combined list of BaseTool instances

    Raises:
        ValueError: If server not found in registry
    """
    tools: list[BaseTool] = []
    for server_name in server_names:
        getter = TOOL_REGISTRY.get(server_name)
        if not getter:
            raise ValueError(f"MCP server not found in registry: {server_name}")
        tools.extend(getter())
    return tools

def list_available_servers() -> list[str]:
    """Get list of all registered MCP server names."""
    return list(TOOL_REGISTRY.keys())
```

#### Tool Wrapper Pattern

**File**: `src/mcp_servers/maven_maintenance/langchain_tools.py` (NEW)

```python
"""LangChain BaseTool wrappers for Maven Maintenance MCP tools."""

from langchain_core.tools import BaseTool, tool

# Import existing MCP tool implementations
from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies
from src.mcp_servers.maven_maintenance.tools.compile import compile_tests
from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests
from src.mcp_servers.maven_maintenance.tools.package import package_project

@tool
async def maven_analyze_dependencies(
    project_path: str,
    include_snapshots: bool = False,
    check_vulnerabilities: bool = True
) -> str:
    """
    Analyze Maven project dependencies for updates, vulnerabilities, and compatibility issues.

    Args:
        project_path: Path to the Maven project root directory
        include_snapshots: Include SNAPSHOT versions in analysis
        check_vulnerabilities: Check for known security vulnerabilities

    Returns:
        JSON string with analysis results
    """
    return await analyze_dependencies(
        project_path=project_path,
        include_snapshots=include_snapshots,
        check_vulnerabilities=check_vulnerabilities
    )

@tool
async def maven_compile_tests(
    project_path: str,
    profiles: list[str] = None,
    skip_main: bool = False
) -> str:
    """
    Compile test sources for a Maven project.

    Args:
        project_path: Path to the Maven project root directory
        profiles: Maven profiles to activate
        skip_main: Skip main source compilation

    Returns:
        Compilation result message
    """
    return await compile_tests(
        project_path=project_path,
        profiles=profiles or [],
        skip_main=skip_main
    )

# ... (2 more tool wrappers)

def get_maven_tools() -> list[BaseTool]:
    """Get all Maven maintenance tools as BaseTool instances."""
    return [
        maven_analyze_dependencies,
        maven_compile_tests,
        maven_run_tests,
        maven_package,
    ]
```

#### Integration with Agent Creation

```python
# src/workflows/maven_maintenance_agent.py (WILL BE CREATED IN PHASE 4)
from deepagents import create_deep_agent
from src.lib.llm import get_llm
from src.agents.loader import AgentLoader
from src.mcp_servers.registry import get_tools_for_servers

# Load agent configuration
loader = AgentLoader("config/agents")
config = loader.load_agent("maven_maintenance_agent")

# Get tools from registry
tools = get_tools_for_servers(["maven-maintenance", "git-maintenance"])

# Load system prompt
prompt = loader.load_prompt("dependency_update", category="maven")

# Create agent
llm = get_llm(
    model=config.llm.model,
    temperature=config.llm.temperature,
    max_tokens=config.llm.max_tokens
)

agent = create_deep_agent(
    model=llm,
    system_prompt=prompt,
    tools=tools,
    checkpointer=postgres_checkpointer,  # From Phase 3
)
```

### Implementation Tasks (T011)

1. Create `src/mcp_servers/registry.py`
2. Create `src/mcp_servers/maven_maintenance/langchain_tools.py` (4 tools)
3. Create `src/mcp_servers/test_generator/langchain_tools.py` (8 tools)
4. Create `src/mcp_servers/docker/langchain_tools.py` (5 tools)
5. Create `src/mcp_servers/git_maintenance/langchain_tools.py` (3 tools, estimated)
6. Add unit tests for registry
7. Add unit tests for each tool wrapper

**Estimated LOC**: ~500 lines total

**Blocked by**: T010 decision (affects YAML schema for loading tools)

---

## Phase 2 Summary

| Task | Status | Outcome |
|------|--------|---------|
| T007 | ✅ Complete | LLM infrastructure verified |
| T008 | ✅ Complete | No MCP adapter needed |
| T009 | ✅ Complete | All prompts exist |
| T010 | ⏳ In Progress | Awaiting user decision on YAML schema |
| T011 | ⏳ Pending | Blocked by T010 |

### Blocker

**T010 requires user decision**: Option A (update spec) or Option B (rewrite YAMLs)?

**Recommendation**: Option A (simpler, no breaking changes)

---

## Next Steps

1. **Get user input on T010** (YAML schema decision)
2. **Complete T010**: Update spec.md or rewrite YAMLs
3. **Complete T011**: Create tool registry + wrappers
4. **Start Phase 3**: US1 Startup Validation (T012-T023)

---

**Phase 2 duration**: ~30 minutes
**Ready for Phase 3**: NO (blocked on T010 decision)
