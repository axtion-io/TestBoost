"""
Maven Maintenance Workflow using DeepAgents LLM framework.

Implements US2: Maven maintenance with real LLM agent reasoning and MCP tool calls.
Replaces deterministic workflow logic with AI-powered decision making.
"""

import json
from datetime import datetime
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agents.loader import AgentLoader
from src.lib.agent_retry import (
    AgentTimeoutError as BaseAgentTimeoutError,
)
from src.lib.agent_retry import (
    ToolCallError as BaseToolCallError,
)
from src.lib.agent_retry import (
    invoke_agent_with_retry,
)
from src.lib.config import get_settings
from src.lib.llm import get_llm
from src.lib.logging import get_logger
from src.mcp_servers.registry import get_tools_for_servers

logger = get_logger(__name__)
settings = get_settings()

# NOTE: Windows path support for DeepAgents is patched in tests/conftest.py
# The patch is applied at test startup to avoid Windows absolute path rejection


class MavenAgentError(Exception):
    """Base exception for Maven agent workflow errors."""

    def __init__(self, message: str = "Maven agent workflow failed"):
        super().__init__(message)


class ToolCallError(MavenAgentError, BaseToolCallError):
    """Raised when agent fails to call expected tools (Maven-specific wrapper)."""

    def __init__(
        self,
        message: str = "Agent failed to call expected tools",
        expected_tools: list[str] | None = None,
    ):
        if expected_tools:
            message = f"{message}. Expected tools: {', '.join(expected_tools)}"
        MavenAgentError.__init__(self, message)
        self.expected_tools = expected_tools


class AgentTimeoutError(MavenAgentError, BaseAgentTimeoutError):
    """Raised when agent invocation times out (Maven-specific wrapper)."""

    def __init__(
        self,
        message: str = "Agent invocation timed out",
        timeout_seconds: float | None = None,
    ):
        if timeout_seconds:
            message = f"{message} after {timeout_seconds}s"
        MavenAgentError.__init__(self, message)
        self.timeout_seconds = timeout_seconds


async def run_maven_maintenance_with_agent(
    project_path: str,
    session_id: str,
    mode: str = "autonomous"
) -> str:
    """
    Run Maven maintenance workflow using DeepAgents LLM agent.

    Implements:
    - T034-T049: Maven maintenance with real LLM agent
    - Agent configuration loading from YAML
    - System prompt loading from Markdown
    - MCP tool binding
    - Agent invocation with retry logic
    - Artifact storage (reasoning, tool calls, metrics)

    Args:
        project_path: Path to Maven project
        session_id: Session ID for tracking
        mode: Execution mode (autonomous, interactive, analysis_only)

    Returns:
        Agent analysis and recommendations

    Raises:
        MavenAgentError: If workflow fails
        LLMError: If LLM invocation fails
    """

    logger.info(
        "maven_agent_workflow_start",
        session_id=session_id,
        project_path=project_path,
        mode=mode
    )

    try:
        # T036: Load agent configuration from YAML
        loader = AgentLoader("config/agents")
        config = loader.load_agent("maven_maintenance_agent")

        logger.info(
            "agent_config_loaded",
            agent=config.name,
            provider=config.llm.provider,
            model=config.llm.model,
            temperature=config.llm.temperature
        )

        # T038: Load system prompt from Markdown
        system_prompt = loader.load_prompt("system_agent", category="maven")

        # Interpolate variables in prompt
        project_name = Path(project_path).name
        system_prompt = system_prompt.replace("{project_name}", project_name)
        system_prompt = system_prompt.replace("{project_path}", project_path)

        logger.info(
            "agent_prompt_loaded",
            prompt_length=len(system_prompt),
            prompt_preview=system_prompt[:300]
        )

        # T035: Get MCP tools for agent
        tools = get_tools_for_servers(config.tools.mcp_servers)

        logger.info(
            "agent_tools_loaded",
            servers=config.tools.mcp_servers,
            tool_count=len(tools),
            tool_names=[t.name for t in tools]
        )

        # T035: Create LLM instance
        llm = get_llm(
            provider=config.llm.provider,
            model=config.llm.model,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens
        )

        # Log tools configuration
        logger.info(
            "agent_llm_ready",
            model=config.llm.model,
            tools_count=len(tools),
            tool_names=[t.name for t in tools],
            tool_details=[{"name": t.name, "description": t.description[:100] if hasattr(t, 'description') and t.description else "no_desc"} for t in tools[:3]]  # First 3 tools
        )

        # T035: Create LangGraph ReAct agent
        # Note: Don't call bind_tools - create_react_agent handles tool binding internally
        # PostgreSQL checkpointer (T032) will be added when pause/resume is needed
        agent = create_react_agent(
            model=llm,
            tools=tools,
            prompt=system_prompt,
            # checkpointer will be added for pause/resume support
        )

        logger.info("agent_created", agent_type=type(agent).__name__)

        # Prepare input for agent
        user_input = f"""Analyze the Maven project at: {project_path}

IMPORTANT: You MUST start by calling the maven_analyze_dependencies tool with the project path.

Step-by-step instructions:
1. FIRST: Call maven_analyze_dependencies tool with project_path="{project_path}"
2. THEN: Analyze the results for outdated packages and security vulnerabilities
3. Prioritize updates based on risk (HIGH/MEDIUM/LOW)
4. Provide a recommended update strategy
5. Include rollback plan if updates fail

Remember: You have access to these tools:
- maven_analyze_dependencies (use this FIRST)
- maven_compile_tests
- maven_run_tests
- maven_package
- git_create_maintenance_branch
- git_commit_changes
- git_get_status
"""

        # T040: Invoke agent with retry logic (A2, A4, A5 edge cases)
        # Note: DeepAgents executes tools via the graph workflow, so we don't verify
        # expected_tools in the AI message. MCP tool logging confirms execution.
        response = await invoke_agent_with_retry(
            agent=agent,
            input_data=[HumanMessage(content=user_input)],
            max_retries=config.error_handling.max_retries,
            expected_tools=None,  # Let DeepAgents manage tool execution via graph
        )

        # T044: Store agent reasoning in session result
        agent_reasoning = {
            "agent": config.name,
            "reasoning": response.content,
            "model": config.llm.model,
            "timestamp": datetime.utcnow().isoformat(),
            "tool_calls": []
        }

        # T045: Store tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:
            for tool_call in response.tool_calls:
                tool_call_data = {
                    "tool_name": tool_call.get("name") or tool_call.get("tool"),
                    "arguments": tool_call.get("args") or tool_call.get("arguments", {}),
                    "id": tool_call.get("id"),
                    "timestamp": datetime.utcnow().isoformat()
                }
                agent_reasoning["tool_calls"].append(tool_call_data)  # type: ignore[union-attr]

                logger.info(
                    "agent_tool_call",
                    tool=tool_call_data["tool_name"],
                    args=tool_call_data["arguments"]
                )

        # T046: Add LLM metrics (estimated - real metrics come from LangSmith)
        agent_reasoning["llm_metrics"] = {  # type: ignore[assignment]
            "estimated_tokens": len(str(response.content).split()) * 1.3,  # Rough estimate
            "model": config.llm.model,
            "provider": config.llm.provider
        }

        logger.info(
            "maven_agent_workflow_complete",
            session_id=session_id,
            tool_calls_count=len(agent_reasoning["tool_calls"]),
            response_length=len(response.content)
        )

        # Return both the reasoning and the structured data
        # The calling code will store this in session.result JSONB field
        return json.dumps({
            "success": True,
            "analysis": response.content,
            "agent_reasoning": agent_reasoning,
            "session_id": session_id
        }, indent=2)

    except Exception as e:
        logger.error(
            "maven_agent_workflow_failed",
            session_id=session_id,
            error=str(e),
            error_type=type(e).__name__
        )
        raise MavenAgentError(f"Maven maintenance workflow failed: {e}") from e


# Re-export for backward compatibility
_invoke_agent_with_retry = invoke_agent_with_retry


__all__ = [
    "run_maven_maintenance_with_agent",
    "MavenAgentError",
    "ToolCallError",
    "AgentTimeoutError",
    # Backward compatibility export
    "_invoke_agent_with_retry",
]








