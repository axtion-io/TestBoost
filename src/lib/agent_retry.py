"""Agent retry utilities for LangGraph workflows.

Provides shared retry logic for agent invocations with proper error handling
for transient failures, rate limits, and authentication errors.
"""

import asyncio
import json
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.lib.llm import LLMError
from src.lib.logging import get_logger

logger = get_logger(__name__)


class AgentInvocationError(Exception):
    """Base exception for agent invocation errors."""

    def __init__(self, message: str = "Agent invocation failed"):
        super().__init__(message)


class ToolCallError(AgentInvocationError):
    """Raised when agent fails to call expected tools."""

    def __init__(
        self,
        message: str = "Agent failed to call expected tools",
        expected_tools: list[str] | None = None,
    ):
        if expected_tools:
            message = f"{message}. Expected tools: {', '.join(expected_tools)}"
        super().__init__(message)
        self.expected_tools = expected_tools


class AgentTimeoutError(AgentInvocationError):
    """Raised when agent invocation times out."""

    def __init__(
        self,
        message: str = "Agent invocation timed out",
        timeout_seconds: float | None = None,
    ):
        if timeout_seconds:
            message = f"{message} after {timeout_seconds}s"
        super().__init__(message)
        self.timeout_seconds = timeout_seconds


def _is_rate_limit_error(error_msg: str) -> bool:
    """Check if error message indicates a rate limit."""
    error_lower = error_msg.lower()
    return "429" in error_msg or "rate limit" in error_lower


def _is_auth_error(error_msg: str) -> bool:
    """Check if error message indicates an authentication error."""
    error_lower = error_msg.lower()
    return "401" in error_msg or "403" in error_msg or "unauthorized" in error_lower


def _extract_ai_message(response: Any) -> AIMessage:
    """Extract AIMessage from agent response (dict or AIMessage)."""
    if isinstance(response, dict) and "messages" in response:
        agent_messages = response["messages"]
        if agent_messages:
            return agent_messages[-1]
        raise AgentInvocationError("Agent returned empty messages list")
    elif isinstance(response, AIMessage):
        return response
    else:
        raise AgentInvocationError(f"Unexpected agent response type: {type(response)}")


def _get_called_tools(ai_message: AIMessage) -> list[str]:
    """Extract list of called tool names from an AI message."""
    if not hasattr(ai_message, "tool_calls") or not ai_message.tool_calls:
        return []
    return [tc.get("name") or tc.get("tool") for tc in ai_message.tool_calls]


async def invoke_agent_with_retry(
    agent: Any,
    input_data: dict[str, Any] | list[BaseMessage],
    max_retries: int = 3,
    expected_tools: list[str] | None = None,
    recursion_limit: int = 100,
) -> AIMessage:
    """
    Invoke agent with retry logic for transient failures.

    Handles:
    - Connection errors with exponential backoff
    - JSON decode errors with retry
    - Tool call validation with prompt modification
    - Rate limit and auth errors (no retry)

    Args:
        agent: LangGraph agent instance
        input_data: Input messages or dict
        max_retries: Maximum retry attempts
        expected_tools: List of tool names that should be called (for validation)
        recursion_limit: LangGraph recursion limit

    Returns:
        AIMessage with agent response

    Raises:
        ToolCallError: If expected tools not called after retries
        LLMError: If invocation fails after retries
        AgentTimeoutError: If invocation times out
    """
    last_error: Exception | None = None

    if isinstance(input_data, list):
        messages = input_data
    else:
        messages = [HumanMessage(content=str(input_data))]

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "agent_invoke_attempt",
                attempt=attempt,
                max_retries=max_retries,
                message_count=len(messages),
            )

            config = {"recursion_limit": recursion_limit}
            response = await agent.ainvoke({"messages": messages}, config)

            ai_message = _extract_ai_message(response)

            # Validate expected tools if specified
            if expected_tools:
                called_tools = _get_called_tools(ai_message)
                missing_tools = set(expected_tools) - set(called_tools)

                if missing_tools:
                    logger.warning(
                        "agent_missing_tool_calls",
                        attempt=attempt,
                        expected=expected_tools,
                        called=called_tools,
                        missing=list(missing_tools),
                    )

                    if attempt < max_retries:
                        retry_message = HumanMessage(
                            content=(
                                f"You must use these tools: {', '.join(expected_tools)}. "
                                "Please analyze the project and call the required tools."
                            )
                        )
                        messages.append(retry_message)
                        continue
                    else:
                        raise ToolCallError(
                            f"Agent failed to call expected tools after {max_retries} attempts",
                            expected_tools=expected_tools,
                        )

            logger.info("agent_invoke_success", attempt=attempt)
            return ai_message

        except ToolCallError:
            # Re-raise ToolCallError without wrapping
            raise

        except json.JSONDecodeError as e:
            logger.warning("agent_json_error", attempt=attempt, error=str(e))
            last_error = e
            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), 10)
                await asyncio.sleep(wait_time)
                continue
            raise AgentInvocationError(
                f"Agent returned malformed JSON after {max_retries} attempts: {e}"
            ) from e

        except ConnectionError as e:
            logger.warning("agent_connection_error", attempt=attempt, error=str(e))
            last_error = e
            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), 10)
                await asyncio.sleep(wait_time)
                continue
            raise LLMError(f"Agent connection failed after {max_retries} attempts: {e}") from e

        except Exception as e:
            error_msg = str(e)

            # Rate limit - do NOT retry
            if _is_rate_limit_error(error_msg):
                logger.error("agent_rate_limited", error=error_msg)
                raise LLMError(f"LLM rate limit exceeded: {e}") from e

            # Auth error - do NOT retry
            if _is_auth_error(error_msg):
                logger.error("agent_auth_failed", error=error_msg)
                raise LLMError(f"LLM authentication failed: {e}") from e

            # Unknown error - retry with backoff
            logger.error(
                "agent_invoke_error",
                attempt=attempt,
                error=error_msg,
                error_type=type(e).__name__,
            )
            last_error = e

            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), 10)
                await asyncio.sleep(wait_time)
                continue

            raise AgentInvocationError(
                f"Agent invocation failed after {max_retries} attempts: {e}"
            ) from e

    # Should not reach here
    raise AgentInvocationError(f"Agent invocation failed: {last_error}") from last_error


__all__ = [
    "invoke_agent_with_retry",
    "AgentInvocationError",
    "ToolCallError",
    "AgentTimeoutError",
]
