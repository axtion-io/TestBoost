# Quickstart Guide: DeepAgents LLM Integration

**Feature**: 002-deepagents-integration
**Date**: 2025-11-28
**Audience**: Developers, Administrators, Testers

## Overview

This guide demonstrates how to integrate, configure, and validate LLM agents in TestBoost workflows after implementing the 002-deepagents-integration feature. It covers four key integration scenarios with step-by-step examples.

---

## Prerequisites

Before starting, ensure:

1. **DeepAgents installed**: `pip install deepagents==0.2.7`
2. **LLM Provider configured**: Valid API key for Google Gemini, Anthropic Claude, or OpenAI
3. **TestBoost installed**: Core implementation (001-testboost-core) complete
4. **Database running**: PostgreSQL 15+ on port 5433

**Environment Variables**:
```bash
# Required: At least one LLM provider
GOOGLE_API_KEY=your_gemini_api_key
# OR
ANTHROPIC_API_KEY=your_claude_api_key
# OR
OPENAI_API_KEY=your_gpt_api_key

# Optional: LangSmith tracing
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=testboost-dev
```

---

## Scenario 1: Testing LLM Connectivity (Developer)

**Goal**: Verify LLM provider is accessible before running workflows

### Step 1: Start API Server

```bash
cd /path/to/TestBoost
poetry run uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

**Expected Output** (success):
```json
{
  "timestamp": "2025-11-28T10:00:00Z",
  "level": "INFO",
  "message": "llm_connection_ok",
  "model": "gemini-2.5-flash-preview-09-2025",
  "provider": "google-genai"
}
```

**Expected Output** (failure):
```json
{
  "timestamp": "2025-11-28T10:00:00Z",
  "level": "ERROR",
  "message": "llm_connection_failed",
  "error": "GOOGLE_API_KEY not configured"
}
```

**Startup should fail** with exit code 1 if LLM unavailable.

### Step 2: Test CLI Startup

```bash
.venv\Scripts\python -m src.cli.main --help
```

**Expected Behavior**:
- If LLM unavailable: CLI exits immediately with error
- If LLM available: Shows help menu

### Step 3: Validate Startup Check

```python
# tests/integration/test_llm_connectivity.py
import pytest
from src.lib.startup_checks import check_llm_connection
from src.lib.exceptions import LLMProviderError

@pytest.mark.asyncio
async def test_llm_connection_success():
    """Test successful LLM connection."""
    # Requires valid GOOGLE_API_KEY in environment
    result = await check_llm_connection()
    assert result is True

@pytest.mark.asyncio
async def test_llm_connection_failure(monkeypatch):
    """Test LLM connection failure."""
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(LLMProviderError, match="GOOGLE_API_KEY not configured"):
        await check_llm_connection()
```

**Run Test**:
```bash
pytest tests/integration/test_llm_connectivity.py -v
```

**Validation**: CHK003, CHK020 (from 001-testboost-core checklist)

---

## Scenario 2: Running Maven Maintenance with Agents (CLI User)

**Goal**: Execute Maven dependency maintenance using LLM agent reasoning

### Step 1: Prepare Test Project

```bash
# Clone a sample Java project
git clone https://github.com/spring-projects/spring-petclinic.git
cd spring-petclinic
```

### Step 2: Run Maven Maintenance

```bash
.venv\Scripts\python -m src.cli.main maintenance maven \
  --project-path "C:\path\to\spring-petclinic" \
  --mode interactive
```

**Expected Workflow**:

1. **Agent loads** from `config/agents/maven_maintenance_agent.yaml`
2. **Prompt loaded** from `config/prompts/maven/dependency_update.md`
3. **Tools bound** from MCP registry (analyze-dependencies, update-dependencies, validate-build)
4. **LLM analyzes** dependencies using MCP tool calls
5. **Agent reasons** about update priorities (security, breaking changes)
6. **User approves** updates (interactive mode)
7. **Agent applies** updates and validates build

**Example Agent Output**:
```
[INFO] agent_loaded | name=maven_maintenance_agent | model=gemini-2.5-flash
[INFO] llm_tool_call | tool=analyze-dependencies | duration=1234ms
[INFO] agent_reasoning | Analyzing 47 dependencies...
       Found 5 outdated, 2 with security vulnerabilities.

Risk Assessment: HIGH
- spring-security-core: CVE-2024-XXXX (CRITICAL)
- jackson-databind: CVE-2024-YYYY (HIGH)

Update Strategy:
1. Priority 1: spring-security-core 5.7.1 → 5.7.11 (security patch)
2. Priority 2: jackson-databind 2.13.0 → 2.13.5 (security patch)
3. Priority 3: junit-jupiter 5.8.2 → 5.9.3 (feature update)

Approve updates? [y/N]:
```

### Step 3: Verify LangSmith Traces

1. Go to https://smith.langchain.com/
2. Navigate to your project (`testboost-dev`)
3. Find the Maven maintenance run
4. Verify:
   - **Agent invocations**: ≥3 LLM API calls
   - **Tool calls**: analyze-dependencies, update-dependencies, validate-build
   - **Token usage**: Prompt tokens, completion tokens
   - **Duration**: End-to-end workflow time

**Example Trace**:
```
Run: maven_maintenance_2025-11-28_10-30-00
├─ LLM Call 1: Analyze dependencies (1523 tokens, 1.2s)
│  └─ Tool: analyze-dependencies → {outdated: 5, vulnerable: 2}
├─ LLM Call 2: Prioritize updates (487 tokens, 0.8s)
│  └─ Reasoning: "Security patches must be applied first..."
└─ LLM Call 3: Generate rollback plan (312 tokens, 0.6s)
   └─ Tool: validate-build → {status: "passed", duration: 45s}
```

**Validation**: CHK097, CHK084, CHK082 (from 001-testboost-core checklist)

### Step 4: Check Session Artifacts

```bash
# Query database for agent reasoning
.venv\Scripts\python -m src.cli.main sessions show <session_id> --artifacts
```

**Expected Artifacts**:
```json
[
  {
    "artifact_type": "agent_reasoning",
    "content": {
      "agent": "maven_maintenance_agent",
      "reasoning": "Analyzing 47 dependencies...",
      "model": "gemini-2.5-flash",
      "timestamp": "2025-11-28T10:30:00Z"
    }
  },
  {
    "artifact_type": "llm_tool_call",
    "content": {
      "tool_name": "analyze-dependencies",
      "arguments": {"project_path": "C:\\path\\to\\spring-petclinic"},
      "result": {"outdated_count": 5, "vulnerable_count": 2},
      "duration_ms": 1234
    }
  },
  {
    "artifact_type": "llm_metrics",
    "content": {
      "prompt_tokens": 1523,
      "completion_tokens": 487,
      "total_tokens": 2010,
      "cost_estimate_usd": 0.0003
    }
  }
]
```

---

## Scenario 3: Configuring Agent Behavior (Administrator)

**Goal**: Customize agent behavior through YAML configuration without code changes

### Step 1: Update Agent Configuration

Edit `config/agents/maven_maintenance_agent.yaml`:

```yaml
name: "maven_maintenance_agent"
identity:
  role: "Maven Dependency Maintenance Specialist"
  persona: "Thorough, security-conscious, risk-aware"

llm:
  provider: "anthropic"  # Changed from google-genai
  model: "claude-sonnet-4-5"  # Changed from gemini-2.5-flash
  temperature: 0.1  # Changed from 0.3 (more deterministic)
  max_tokens: 16384  # Changed from 8192 (longer responses)

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
  max_retries: 5  # Changed from 3 (more resilient)
  timeout_seconds: 180  # Changed from 120 (longer timeout)
```

**Changes Made**:
1. Switched LLM provider from Google Gemini to Anthropic Claude
2. Reduced temperature for more consistent outputs
3. Increased max_tokens for longer dependency analyses
4. Increased retry count and timeout for slower models

### Step 2: Update System Prompt

Edit `config/prompts/maven/dependency_update.md`:

```markdown
# Maven Dependency Update Agent

## Role
You are a Maven dependency maintenance specialist focused on security-first updates.

## Objectives
1. **SECURITY FIRST**: Always prioritize CVE fixes over feature updates
2. Analyze project dependencies for vulnerabilities using NIST NVD database
3. Assess breaking change risk based on semantic versioning
4. Recommend update strategy with detailed rollback plan

## New Validation Rules
- NEVER update dependencies with active CVEs to lower-patched versions
- ALWAYS separate security patches from feature updates
- MUST validate build AND run tests after each update
- REQUIRE explicit approval for major version changes (X.0.0)

## Response Format
Provide analysis in this structure:
1. **Security Summary**: CVE count by severity (CRITICAL/HIGH/MEDIUM/LOW)
2. **Risk Assessment**: Breaking change likelihood with justification
3. **Phased Update Plan**: Security patches first, then features
4. **Rollback Procedure**: Exact commands to revert changes
```

### Step 3: Restart and Validate

```bash
# Restart API server to reload configs
# Ctrl+C to stop, then:
.venv\Scripts\python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

**Expected Startup Logs**:
```json
{
  "timestamp": "2025-11-28T11:00:00Z",
  "level": "INFO",
  "message": "agent_config_validated",
  "name": "maven_maintenance_agent",
  "provider": "anthropic",
  "model": "claude-sonnet-4-5"
}
```

### Step 4: Run Workflow with New Config

```bash
.venv\Scripts\python -m src.cli.main maintenance maven \
  --project-path "C:\path\to\spring-petclinic" \
  --mode autonomous
```

**Expected Behavior**:
- Agent uses Claude Sonnet instead of Gemini
- Lower temperature produces more consistent reasoning
- New prompt rules enforced (security-first, phased updates)
- Longer responses due to increased max_tokens

**Validation**: CHK095, CHK096 (from 001-testboost-core checklist)

---

## Scenario 4: Validating LangSmith Traces (Tester)

**Goal**: Verify all agent tool calls are traced and auditable

### Step 1: Enable LangSmith Tracing

```bash
# Set environment variables
export LANGSMITH_API_KEY=your_langsmith_key
export LANGSMITH_TRACING=true
export LANGSMITH_PROJECT=testboost-e2e-tests
```

### Step 2: Run E2E Test Suite

```bash
pytest tests/e2e/test_real_llm_invocation.py -v --langsmith
```

**Test Code**:
```python
# tests/e2e/test_real_llm_invocation.py
import pytest
from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

@pytest.mark.e2e
@pytest.mark.asyncio
async def test_maven_workflow_llm_calls(sample_java_project):
    """
    Verify Maven workflow invokes real LLM agent.

    Validates:
    - At least 3 LLM API calls
    - Tool calls traced in LangSmith
    - Agent reasoning stored in artifacts
    """
    result = await run_maven_maintenance_with_agent(
        project_path=sample_java_project,
        user_approved=True  # Autonomous mode
    )

    # Check workflow completed
    assert result["status"] == "completed"

    # Check artifacts contain agent data
    artifacts = result["artifacts"]
    reasoning_artifacts = [a for a in artifacts if a["type"] == "agent_reasoning"]
    tool_call_artifacts = [a for a in artifacts if a["type"] == "llm_tool_call"]

    assert len(reasoning_artifacts) >= 1, "No agent reasoning found"
    assert len(tool_call_artifacts) >= 3, "Less than 3 tool calls"

    # Check LangSmith trace exists
    session_id = result["session_id"]
    trace = await get_langsmith_trace(session_id)

    assert trace is not None, "No LangSmith trace found"
    assert trace["llm_calls"] >= 3, "Less than 3 LLM calls"
    assert len(trace["tool_calls"]) >= 3, "Less than 3 tool calls traced"
```

### Step 3: Analyze LangSmith Dashboard

1. Go to https://smith.langchain.com/
2. Select project `testboost-e2e-tests`
3. Filter by date range (today)
4. Sort by token usage (descending)

**Metrics to Validate**:
- **Total Runs**: Should match test count
- **Success Rate**: ≥95%
- **Average Latency**: <5s for Gemini, <10s for Claude
- **Token Usage**: Should be within budget (1500 free/day for Gemini)
- **Tool Calls**: All MCP tools traced with args/results

**Example Dashboard**:
```
Project: testboost-e2e-tests
Date: 2025-11-28

Runs: 12
├─ Successful: 11 (91.7%)
├─ Failed: 1 (8.3%)
└─ Average Duration: 4.2s

Token Usage:
├─ Prompt Tokens: 18,234
├─ Completion Tokens: 5,876
└─ Total: 24,110

Tool Calls: 37
├─ analyze-dependencies: 12
├─ update-dependencies: 11
├─ validate-build: 12
└─ git-commit: 2
```

**Validation**: CHK084, CHK097 (from 001-testboost-core checklist)

---

## Troubleshooting

### Issue 1: Startup Fails with "LLM not available"

**Symptoms**:
```
ERROR | llm_connection_failed | error=GOOGLE_API_KEY not configured
```

**Solutions**:
1. Verify environment variable is set: `echo %GOOGLE_API_KEY%` (Windows) or `echo $GOOGLE_API_KEY` (Linux)
2. Check API key validity: Test with curl to Gemini API
3. Try alternative provider: Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY`
4. Check firewall: Ensure outbound HTTPS to `generativelanguage.googleapis.com` allowed

### Issue 2: Agent Config Validation Fails

**Symptoms**:
```
ERROR | agent_config_invalid | error=Field 'llm.model' is required
```

**Solutions**:
1. Validate YAML syntax: Use online YAML validator
2. Check required fields: Compare with `src/agents/loader.py` schema
3. Verify file path: Ensure `config/agents/maven_maintenance_agent.yaml` exists
4. Check indentation: YAML is whitespace-sensitive (use spaces, not tabs)

### Issue 3: LangSmith Traces Not Appearing

**Symptoms**:
- Workflow runs successfully
- No traces in LangSmith dashboard

**Solutions**:
1. Verify tracing enabled: `echo %LANGSMITH_TRACING%` should be `true`
2. Check API key: Validate `LANGSMITH_API_KEY` in LangSmith settings
3. Verify project name: Ensure `LANGSMITH_PROJECT` matches dashboard
4. Check network: Ensure outbound HTTPS to `api.smith.langchain.com` allowed
5. Review startup logs: Should see `langsmith_tracing_enabled`

### Issue 4: Agent Not Calling MCP Tools

**Symptoms**:
- Agent responds without using tools
- LangSmith shows LLM calls but no tool calls

**Solutions**:
1. Verify tool binding: Check logs for `mcp_tools_validated`
2. Check prompt clarity: Ensure system prompt instructs tool usage
3. Review model capabilities: Some models better at tool calling (Claude > GPT-4 > Gemini)
4. Increase temperature: Very low temperatures may reduce tool usage creativity
5. Check tool descriptions: MCP tools must have clear docstrings for LLM discovery

### Issue 5: High LLM Costs

**Symptoms**:
- API bills higher than expected
- Token usage exceeding budget

**Solutions**:
1. Switch to faster model: Gemini Flash (free tier) instead of Claude Sonnet
2. Reduce max_tokens: Lower `llm.max_tokens` in YAML config
3. Enable prompt caching: Use Anthropic with DeepAgents caching middleware
4. Optimize prompts: Remove verbose examples, use concise language
5. Add rate limiting: Implement per-user quotas in API

---

## Migration Guide: From Old Workflows to Agent-Based Workflows

**Audience**: Existing TestBoost users upgrading from 001-testboost-core

### Overview

The 002-deepagents-integration feature introduces **agent-powered workflows** alongside existing deterministic workflows. This migration is **100% backward compatible** - all existing code, CLI commands, and API endpoints continue to work unchanged.

### What's Changing?

| Aspect | Old Approach (001) | New Approach (002) | Breaking Changes? |
|--------|-------------------|-------------------|-------------------|
| **Execution** | Deterministic scripts | LLM agent reasoning | **NO** - Old functions still callable |
| **Decision Making** | Hardcoded rules | Dynamic LLM analysis | **NO** - Opt-in via `--mode` flag |
| **Configuration** | Python code | YAML + Markdown prompts | **NO** - New configs added, old ignored |
| **Dependencies** | Maven/Git tools only | + DeepAgents 0.2.8 | **NO** - Additive only |
| **API Keys** | None required | LLM provider required | **NO** - Validation at startup only |
| **Tool Execution** | Direct function calls | MCP server tool calls | **NO** - Old functions wrapped |
| **Observability** | Basic logging | LangSmith tracing + artifacts | **NO** - Old logs still work |
| **Error Handling** | Manual retry logic | Auto-retry with edge cases (A1-A6) | **NO** - Additive enhancement |

### API Interface Compatibility

The following API endpoints and request/response models remain **100% backward compatible**:

**Unchanged Endpoints**:
- `POST /api/testboost/maintenance/maven` - MaintenanceRequest/MaintenanceResponse
- `POST /api/testboost/analyze` - AnalyzeRequest/AnalyzeResponse
- `POST /api/testboost/tests/generate` - TestGenerateRequest/TestGenerateResponse

**New Endpoints** (additive, non-breaking):
- `GET /api/health` - Enhanced health check with LLM status
- `GET /api/v2/sessions/{session_id}/artifacts` - View agent reasoning artifacts

### Function Migration Reference

| Previous Function | New Function | Changes |
|------------------|--------------|---------|
| `run_maven_maintenance()` | `run_maven_maintenance_with_agent()` | Now uses DeepAgents LLM with MCP tools |
| `run_test_generation()` | `run_test_generation_with_agent()` | Added `db_session` parameter for artifact storage |
| `run_docker_deployment()` | `run_docker_deployment_with_agent()` | Adds checkpointer for pause/resume |

**Note**: Old functions still work and log deprecation warnings.

### Exception Hierarchy Changes

Previous exceptions are still available, with new agent-specific additions:

```python
# Still available (backward compatible)
from src.lib.llm import LLMError, LLMProviderError, LLMTimeoutError

# New in v2 (additive, non-breaking)
from src.lib.llm import LLMRateLimitError  # A1 edge case handling
from src.lib.startup_checks import StartupCheckError, LLMConnectionError, AgentConfigError
from src.workflows.maven_maintenance_agent import MavenAgentError, ToolCallError, AgentTimeoutError
from src.workflows.test_generation_agent import TestGenerationError, CompilationError
```

### Migration Path: Choose Your Approach

#### Option 1: Gradual Migration (Recommended)

**Who**: Teams wanting to test agents on non-critical workflows first

**Steps**:
1. **Add LLM API key** to `.env` (keeps old workflows unchanged)
2. **Test agent workflows** on sample projects (not production)
3. **Compare results** between old and new approaches
4. **Switch production workflows** one at a time

**Example**:
```bash
# Week 1: Test agents on sample project
.venv\Scripts\python -m src.cli.main maintenance maven \
  --project-path "C:\test\spring-petclinic" \
  --mode autonomous  # NEW: Agent-powered

# Week 2: Run old workflow on same project for comparison
.venv\Scripts\python -m src.cli.main maintenance maven \
  --project-path "C:\test\spring-petclinic" \
  --mode deterministic  # OLD: Rule-based (still works!)

# Week 3+: Gradually switch production workflows
```

#### Option 2: Immediate Switch (All-In)

**Who**: New deployments or teams confident in LLM agents

**Steps**:
1. **Set `GOOGLE_API_KEY`** in `.env`
2. **Update CLI scripts** to use `--mode autonomous` by default
3. **Monitor LangSmith traces** for first 48 hours
4. **Rollback** to old workflows if issues (change `--mode` flag)

### Configuration Migration

**No migration needed!** Old configs coexist with new agent configs.

**Step 1**: Create agent YAML config (if not exists)

```yaml
# config/agents/maven_maintenance_agent.yaml
name: "maven_maintenance_agent"
llm:
  provider: "anthropic"  # or "google-genai", "openai"
  model: "claude-sonnet-4-5-20250929"
  temperature: 0.3
tools:
  mcp_servers:
    - "maven-maintenance"
    - "git-maintenance"
prompts:
  system: "config/prompts/maven/dependency_update.md"
error_handling:
  max_retries: 3
```

**Old Configuration** (still used by deterministic workflows):
```python
# src/config.py - Unchanged, still works
MAVEN_UPDATE_POLICY = "security-first"
MAX_DEPENDENCY_AGE_DAYS = 180
```

**Step 2**: Update environment variables

```bash
# Required: At least one LLM provider
ANTHROPIC_API_KEY=your_key_here
# OR
GOOGLE_API_KEY=your_key_here
# OR
OPENAI_API_KEY=your_key_here

# Recommended: Enable tracing
LANGSMITH_API_KEY=your_langsmith_key
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=testboost
```

**Step 3**: Verify startup

```bash
.venv\Scripts\python -m src.cli.main --help
# Should see: llm_connection_ok in logs
```

### Breaking Changes

1. **Startup Check Required**: Application now validates LLM connectivity at startup. If no valid API key is configured, the application will not start (Zéro Complaisance principle).

2. **Agent Config Required**: All three required agents must have valid YAML configurations:
   - `maven_maintenance_agent.yaml`
   - `test_gen_agent.yaml`
   - `deployment_agent.yaml`

3. **Database Session for Test Gen**: `run_test_generation_with_agent()` now requires a `db_session` parameter for artifact storage.

### Testing Your Migration

**Step 1: Verify Old Workflows Still Work**

Create regression tests to ensure backward compatibility:

```python
# tests/regression/test_old_workflows.py
import pytest
from src.workflows.maven_maintenance import run_maven_maintenance

def test_old_maven_workflow_still_callable():
    """Ensure old workflow function still exists and works."""
    result = run_maven_maintenance("tests/fixtures/spring-petclinic")
    assert result is not None
    assert "updated_count" in result

def test_old_workflow_logs_deprecation_warning(caplog):
    """Ensure old workflows log deprecation warnings."""
    run_maven_maintenance("tests/fixtures/spring-petclinic")
    assert "DEPRECATED" in caplog.text
    assert "run_maven_maintenance_with_agent" in caplog.text
```

Run the regression test suite:

```bash
.venv\Scripts\python -m pytest tests/regression/test_old_workflows.py -v
```

All tests should pass, confirming:
- Workflow function signatures unchanged
- Exception classes available
- API models backward compatible
- Library imports working

**Step 2: Compare Results**

Run both workflows on the same project:

```bash
# Run old workflow, save output
.venv\Scripts\python -m src.cli.main maintenance maven \
  --project-path "C:\test\spring-petclinic" \
  --mode deterministic \
  --output old_result.json

# Run new workflow, save output
.venv\Scripts\python -m src.cli.main maintenance maven \
  --project-path "C:\test\spring-petclinic" \
  --mode autonomous \
  --output new_result.json

# Compare results
diff old_result.json new_result.json
```

**Expected Differences**:
- **Agent reasoning**: New workflow includes LLM analysis text
- **Update count**: May differ (agents consider more factors)
- **Execution time**: Agents slower (LLM API calls) but more thorough

### Rollback Plan

If agent workflows cause issues:

**Immediate Rollback** (reverts to old workflows):
```bash
# Option 1: Remove LLM API key (forces old workflow usage)
# In .env file:
# GOOGLE_API_KEY=  # Remove or comment out

# Option 2: Change CLI default mode
# In src/cli/commands/maintenance.py:
# default_mode = "deterministic"  # Instead of "autonomous"

# Option 3: Use old workflow functions directly (still available)
```

```python
from src.workflows.maven_maintenance import run_maven_maintenance
# Instead of: from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
```

**Partial Rollback** (use agents for some workflows only):
```yaml
# config/feature_flags.yaml
workflows:
  maven_maintenance:
    use_agent: false  # Rollback Maven to old workflow
  test_generation:
    use_agent: true   # Keep test gen on agent
  docker_deployment:
    use_agent: true   # Keep deployment on agent
```

**Development-Only Option**:
```bash
# Set SKIP_LLM_CHECK=true (not recommended for production)
SKIP_LLM_CHECK=true .venv\Scripts\python -m src.cli.main --help
```

### Troubleshooting Migration Issues

**Issue**: "Old workflow no longer works after upgrade"

**Solution**: This should never happen! If it does:
1. Check Python imports: Ensure `from src.workflows.maven_maintenance import run_maven_maintenance` still works
2. Verify function signature unchanged: Compare with 001-testboost-core version
3. Report bug: This violates backward compatibility guarantee

**Issue**: "Agent workflow too slow for CI/CD pipeline"

**Solution**:
1. Use old deterministic workflow for CI: `--mode deterministic`
2. Or use faster LLM: Switch from Claude to Gemini Flash in YAML config
3. Or cache LLM responses: Enable Anthropic prompt caching

**Issue**: "Unexpected LLM costs"

**Solution**:
1. Monitor costs first week: Check LangSmith dashboard daily
2. Set budget alerts: Configure in Google Cloud Console / Anthropic dashboard
3. Use free tier: Gemini Flash has generous free tier (1500 requests/day)
4. Switch to deterministic: Old workflows have zero LLM costs

### When to Use Which Workflow?

| Scenario | Recommended Workflow | Reasoning |
|----------|---------------------|-----------|
| **CI/CD pipelines** | Deterministic (old) | Faster, predictable, no API costs |
| **Production critical** | Deterministic (old) | No external LLM dependency |
| **Complex projects** | Agent-powered (new) | Better analysis, context-aware decisions |
| **Security-focused** | Agent-powered (new) | Understands CVE severity, risk assessment |
| **Large codebases** | Agent-powered (new) | Handles complexity better than rules |
| **Offline environments** | Deterministic (old) | No internet required |

### Summary: Migration Checklist

- [ ] **Add LLM API key** to `.env` file
- [ ] **Test agent workflows** on non-production projects
- [ ] **Compare results** between old and new approaches
- [ ] **Update documentation** (internal wikis, runbooks)
- [ ] **Configure monitoring** (LangSmith traces, cost alerts)
- [ ] **Train team** on new YAML/Markdown config approach
- [ ] **Plan rollback** strategy if issues arise
- [ ] **Monitor first week** closely for unexpected behavior
- [ ] **Gradually migrate** production workflows one at a time
- [ ] **Deprecate old workflows** after 6 months (optional)

---

## Next Steps

After completing integration:

1. **Migrate Additional Workflows**: Apply same pattern to test generation and deployment workflows
2. **Monitor Production**: Track LLM costs, latency, success rates via LangSmith
3. **Tune Agent Behavior**: Iterate on YAML configs and Markdown prompts based on user feedback
4. **Add Custom Tools**: Create new MCP servers for domain-specific operations
5. **Implement Streaming**: Enable streaming responses for long-running workflows (future)

---

## References

- **DeepAgents Documentation**: https://github.com/anthropics/deepagents
- **LangSmith Dashboard**: https://smith.langchain.com/
- **MCP Protocol**: https://modelcontextprotocol.io/
- **Agent Loader Code**: [src/agents/loader.py](../../src/agents/loader.py)
- **Maven Workflow Example**: [src/workflows/maven_maintenance_agent.py](../../src/workflows/maven_maintenance_agent.py)
- **E2E Tests**: [tests/e2e/test_real_llm_invocation.py](../../tests/e2e/test_real_llm_invocation.py)

---

**Status**: Complete - Ready for implementation
**Next Phase**: Run `/speckit.tasks` to generate implementation task list
