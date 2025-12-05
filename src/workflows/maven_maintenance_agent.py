"""
Maven Maintenance Workflow using DeepAgents LLM framework.

Implements US2: Maven maintenance with real LLM agent reasoning and MCP tool calls.
Replaces deterministic workflow logic with AI-powered decision making.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any
from pathlib import Path

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.agents.loader import AgentLoader
from src.lib.config import get_settings
from src.lib.llm import LLMError, get_llm
from src.lib.logging import get_logger
from src.mcp_servers.registry import get_tools_for_servers

logger = get_logger(__name__)
settings = get_settings()

# NOTE: Windows path support for DeepAgents is patched in tests/conftest.py
# The patch is applied at test startup to avoid Windows absolute path rejection


class MavenAgentError(Exception):
    """Base exception for Maven agent workflow errors."""
    pass


class ToolCallError(MavenAgentError):
    """Raised when agent fails to call expected tools."""
    pass


class AgentTimeoutError(MavenAgentError):
    """Raised when agent invocation times out."""
    pass


async def _invoke_agent_with_retry(
    agent: Any,
    input_data: dict | list[BaseMessage],
    max_retries: int = 3,
    expected_tools: list[str] | None = None
) -> AIMessage:
    """
    Invoke agent with retry logic for transient failures.

    Implements:
    - A2: Retry if no tools called (max 3 attempts with modified prompt)
    - A4: Retry on intermittent connectivity (exponential backoff)
    - A5: Retry on malformed JSON (max 3 attempts)

    Args:
        agent: DeepAgents agent instance
        input_data: Input messages or dict
        max_retries: Maximum retry attempts
        expected_tools: List of tool names that should be called (for A2 validation)

    Returns:
        AIMessage with agent response

    Raises:
        ToolCallError: If expected tools not called after retries
        LLMError: If invocation fails after retries
        AgentTimeoutError: If invocation times out
    """
    last_error: Exception | None = None
    messages = input_data if isinstance(input_data, list) else [HumanMessage(content=str(input_data))]

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("agent_invoke_attempt", attempt=attempt, max_retries=max_retries)

            # Log what we're sending to the LLM
            logger.info(
                "llm_request_details",
                attempt=attempt,
                message_count=len(messages),
                messages=[{"role": m.type if hasattr(m, 'type') else 'unknown', "content_length": len(str(m.content))} for m in messages],
                first_message_preview=str(messages[0].content)[:500] if messages else ""
            )

            start_time = time.time()

            # Invoke agent
            response = await agent.ainvoke({"messages": messages})  # type: ignore[arg-type]

            duration_ms = int((time.time() - start_time) * 1000)
            logger.info("agent_invoke_success", attempt=attempt, duration_ms=duration_ms)

            # Log the raw response
            logger.debug(
                "llm_raw_response",
                attempt=attempt,
                response_type=type(response).__name__,
                response_keys=list(response.keys()) if isinstance(response, dict) else "not_dict"  # type: ignore[arg-type]
            )

            # Extract AIMessage from response
            if isinstance(response, dict) and "messages" in response:
                # DeepAgents returns dict with messages list
                agent_messages = response["messages"]
                if agent_messages:
                    ai_message = agent_messages[-1]
                else:
                    raise MavenAgentError("Agent returned empty messages list")
            elif isinstance(response, AIMessage):
                ai_message = response
            else:
                raise MavenAgentError(f"Unexpected agent response type: {type(response)}")

            # Log the AI message details
            logger.info(
                "llm_response_content",
                attempt=attempt,
                content_preview=str(ai_message.content)[:500] if hasattr(ai_message, 'content') else "no_content",  # type: ignore[attr-defined]
                has_tool_calls=hasattr(ai_message, "tool_calls") and bool(ai_message.tool_calls),  # type: ignore[attr-defined]
                tool_calls_count=len(ai_message.tool_calls) if hasattr(ai_message, "tool_calls") and ai_message.tool_calls else 0  # type: ignore[attr-defined]
            )

            # A2 Edge Case: Verify expected tools were called
            if expected_tools:
                called_tools = []
                if hasattr(ai_message, "tool_calls") and ai_message.tool_calls:  # type: ignore[attr-defined]
                    called_tools = [tc.get("name") or tc.get("tool") for tc in ai_message.tool_calls]  # type: ignore[attr-defined,union-attr]
                    logger.info(
                        "llm_tool_calls_detected",
                        attempt=attempt,
                        called_tools=called_tools,
                        tool_calls_raw=[{k: v for k, v in tc.items() if k in ['name', 'tool', 'id']} for tc in ai_message.tool_calls]
                    )

                missing_tools = set(expected_tools) - set(called_tools)
                if missing_tools:
                    logger.warning(
                        "agent_missing_tool_calls",
                        attempt=attempt,
                        expected=expected_tools,
                        called=called_tools,
                        missing=list(missing_tools)
                    )

                    if attempt < max_retries:
                        # Retry with modified prompt instructing tool use
                        retry_message = HumanMessage(
                            content=f"You must use these tools: {', '.join(expected_tools)}. "
                            f"Please analyze the project and call the required tools."
                        )
                        messages.append(retry_message)
                        logger.info("agent_retry_with_tool_prompt", missing_tools=list(missing_tools))
                        continue
                    else:
                        raise ToolCallError(
                            f"Agent failed to call expected tools after {max_retries} attempts. "
                            f"Expected: {expected_tools}, Called: {called_tools}"
                        )

            return ai_message

        except json.JSONDecodeError as e:
            # A5 Edge Case: Malformed JSON
            logger.warning("agent_json_error", attempt=attempt, error=str(e))
            last_error = e

            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), 10)
                logger.info("agent_retry_json_error", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise MavenAgentError(f"Agent returned malformed JSON after {max_retries} attempts: {e}") from e

        except ConnectionError as e:
            # A4 Edge Case: Intermittent connectivity
            logger.warning("agent_connection_error", attempt=attempt, error=str(e))
            last_error = e

            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), 10)
                logger.info("agent_retry_connection_error", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise LLMError(f"Agent connection failed after {max_retries} attempts: {e}") from e

        except Exception as e:
            # Check if it's a rate limit error (A1 - should NOT retry)
            error_msg = str(e).lower()
            if "429" in error_msg or "rate limit" in error_msg:
                logger.error("agent_rate_limited", error=str(e))
                raise LLMError(f"LLM rate limit exceeded: {e}") from e

            # Check if it's an auth error (should NOT retry)
            if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg:
                logger.error("agent_auth_failed", error=str(e))
                raise LLMError(f"LLM authentication failed: {e}") from e

            # Unknown error - log and retry
            logger.error("agent_invoke_error", attempt=attempt, error=str(e), error_type=type(e).__name__)
            last_error = e

            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), 10)
                logger.info("agent_retry_unknown_error", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise MavenAgentError(f"Agent invocation failed after {max_retries} attempts: {e}") from e

    # Should not reach here, but raise last error if we do
    raise MavenAgentError(f"Agent invocation failed: {last_error}") from last_error


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
            model=f"{config.llm.provider}/{config.llm.model}",
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
            model=f"{config.llm.provider}/{config.llm.model}",
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens
        )

        # T039: Bind tools to LLM
        llm_with_tools = llm.bind_tools(tools)

        logger.info(
            "agent_llm_ready",
            model=config.llm.model,
            tools_bound=len(tools),
            tool_names=[t.name for t in tools],
            tool_details=[{"name": t.name, "description": t.description[:100] if hasattr(t, 'description') and t.description else "no_desc"} for t in tools[:3]]  # First 3 tools
        )

        # T035: Create DeepAgents agent
        # Note: PostgreSQL checkpointer (T032) will be added when pause/resume is needed
        # IMPORTANT: Pass backend=None to disable filesystem middleware that rejects Windows paths
        # We don't need DeepAgents' filesystem tools since we have our own MCP tools
        agent = create_deep_agent(
            model=llm_with_tools,
            system_prompt=system_prompt,
            tools=tools,
            backend=None,  # Disable filesystem middleware for Windows path compatibility
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
        response = await _invoke_agent_with_retry(
            agent=agent,
            input_data=[HumanMessage(content=user_input)],
            max_retries=config.error_handling.max_retries,
            expected_tools=None  # Let DeepAgents manage tool execution via graph
        )

        # T044: Store agent reasoning in session result
        agent_reasoning = {
            "agent": config.name,
            "reasoning": response.content,  # type: ignore[attr-defined]
            "model": config.llm.model,
            "timestamp": datetime.utcnow().isoformat(),
            "tool_calls": []
        }

        # T045: Store tool calls
        if hasattr(response, "tool_calls") and response.tool_calls:  # type: ignore[attr-defined]
            for tool_call in response.tool_calls:  # type: ignore[attr-defined]
                tool_call_data = {
                    "tool_name": tool_call.get("name") or tool_call.get("tool"),  # type: ignore[union-attr]
                    "arguments": tool_call.get("args") or tool_call.get("arguments", {}),  # type: ignore[union-attr]
                    "id": tool_call.get("id"),  # type: ignore[union-attr]
                    "timestamp": datetime.utcnow().isoformat()
                }
                agent_reasoning["tool_calls"].append(tool_call_data)

                logger.info(
                    "agent_tool_call",
                    tool=tool_call_data["tool_name"],
                    args=tool_call_data["arguments"]
                )

        # T046: Add LLM metrics (estimated - real metrics come from LangSmith)
        agent_reasoning["llm_metrics"] = {
            "estimated_tokens": len(response.content.split()) * 1.3,  # type: ignore[attr-defined] # Rough estimate
            "model": config.llm.model,
            "provider": config.llm.provider
        }

        logger.info(
            "maven_agent_workflow_complete",
            session_id=session_id,
            tool_calls_count=len(agent_reasoning["tool_calls"]),
            response_length=len(response.content)  # type: ignore[attr-defined,arg-type]
        )

        # Return both the reasoning and the structured data
        # The calling code will store this in session.result JSONB field
        return json.dumps({
            "success": True,
            "analysis": response.content,  # type: ignore[attr-defined]
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


__all__ = [
    "run_maven_maintenance_with_agent",
    "MavenAgentError",
    "ToolCallError",
    "AgentTimeoutError",
]
