"""LangGraph agent adapter for DeepAgents configurations."""

from collections.abc import Awaitable, Callable
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from src.agents.loader import AgentConfig
from src.lib.llm import get_llm
from src.lib.logging import get_logger
from src.workflows.state import WorkflowState

logger = get_logger(__name__)


class AgentAdapter:
    """Adapt DeepAgents configuration to LangGraph nodes."""

    def __init__(self, mcp_tool_registry: dict[str, list[BaseTool]] | None = None) -> None:
        """Initialize adapter with optional MCP tool registry.

        Args:
            mcp_tool_registry: Mapping of MCP server names to their tools
        """
        self.mcp_tool_registry = mcp_tool_registry or {}

    def create_node(
        self,
        config: AgentConfig,
        system_prompt: str,
        input_mapper: Callable[[WorkflowState], str] | None = None,
        output_mapper: Callable[[str, WorkflowState], WorkflowState] | None = None,
    ) -> Callable[[WorkflowState], Awaitable[WorkflowState]]:
        """Convert agent config to a LangGraph node function.

        Args:
            config: Agent configuration
            system_prompt: System prompt content for the agent
            input_mapper: Function to convert state to LLM input
            output_mapper: Function to process LLM output into state updates

        Returns:
            Node function for LangGraph
        """
        # Get LLM instance
        llm = get_llm(
            model=config.llm.model,
            temperature=config.llm.temperature,
            max_tokens=config.llm.max_tokens,
        )

        # Collect tools from MCP servers
        tools: list[BaseTool] = []
        for server_name in config.tools.mcp_servers:
            if server_name in self.mcp_tool_registry:
                tools.extend(self.mcp_tool_registry[server_name])
            else:
                logger.warning(
                    "mcp_server_not_found",
                    agent=config.name,
                    server=server_name,
                )

        # Bind tools to LLM if available
        if tools:
            llm = llm.bind_tools(tools)
            logger.info(
                "tools_bound",
                agent=config.name,
                tool_count=len(tools),
            )

        async def node(state: WorkflowState) -> WorkflowState:
            """Execute agent node."""
            logger.info(
                "agent_node_started",
                agent=config.name,
                session_id=str(state.get("session_id")),
            )

            # Build messages
            messages = [
                SystemMessage(content=system_prompt),
            ]

            # Map input from state
            if input_mapper:
                user_input = input_mapper(state)
            else:
                # Default: use input_data or create summary
                input_data = state.get("input_data", {})
                user_input = _default_input_mapper(input_data)

            messages.append(HumanMessage(content=user_input))

            # Invoke LLM
            try:
                response = await llm.ainvoke(messages)
                response_text = response.content if hasattr(response, "content") else str(response)

                logger.info(
                    "agent_node_completed",
                    agent=config.name,
                    response_length=len(response_text),
                )

                # Map output to state
                if output_mapper:
                    return output_mapper(response_text, state)
                else:
                    return _default_output_mapper(response_text, state)

            except Exception as e:
                logger.error(
                    "agent_node_error",
                    agent=config.name,
                    error=str(e),
                )
                # Update state with error
                return {
                    **state,
                    "error": str(e),
                    "error_step": config.name,
                }

        return node

    def create_tool_node(
        self,
        tools: list[BaseTool],
    ) -> Callable[[WorkflowState], Awaitable[WorkflowState]]:
        """Create a tool execution node.

        Args:
            tools: List of tools to make available

        Returns:
            Tool node function
        """
        from langgraph.prebuilt import ToolNode

        tool_node = ToolNode(tools)

        async def node(state: WorkflowState) -> WorkflowState:
            """Execute tool calls from messages."""
            # ToolNode expects messages in state
            result = await tool_node.ainvoke(state)
            return {**state, **result}

        return node


def _default_input_mapper(input_data: dict[str, Any]) -> str:
    """Default mapping from input_data to user message."""
    if not input_data:
        return "Process the current workflow state."

    # Format as key-value pairs
    parts: list[str] = []
    for key, value in input_data.items():
        if isinstance(value, (dict, list)):
            import json

            value = json.dumps(value, indent=2)
        parts.append(f"{key}: {value}")

    return "\n".join(parts)


def _default_output_mapper(response: str, state: WorkflowState) -> WorkflowState:
    """Default mapping from LLM response to state updates."""
    output_data: dict[str, Any] = state.get("output_data", {}).copy()
    output_data["last_response"] = response

    results: list[dict[str, Any]] = state.get("results", []).copy()
    results.append(
        {
            "step": state.get("current_step"),
            "response": response,
        }
    )

    return {
        **state,
        "output_data": output_data,
        "results": results,
    }


__all__ = ["AgentAdapter"]
