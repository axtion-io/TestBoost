"""Centralized registry of MCP tools as LangChain BaseTool instances."""

from typing import Callable

from langchain_core.tools import BaseTool


# Tool registry will be populated after importing tool modules
TOOL_REGISTRY: dict[str, Callable[[], list[BaseTool]]] = {}


def register_tools(server_name: str, getter: Callable[[], list[BaseTool]]) -> None:
    """
    Register tools for an MCP server.

    Args:
        server_name: MCP server identifier (e.g., "maven-maintenance")
        getter: Function that returns list of BaseTool instances
    """
    TOOL_REGISTRY[server_name] = getter


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
            available = ", ".join(TOOL_REGISTRY.keys())
            raise ValueError(
                f"MCP server '{server_name}' not found in registry. "
                f"Available servers: {available}"
            )
        tools.extend(getter())
    return tools


def list_available_servers() -> list[str]:
    """Get list of all registered MCP server names."""
    return list(TOOL_REGISTRY.keys())


# Import and register all MCP tool modules
# This happens at module import time
def _initialize_registry() -> None:
    """Initialize the tool registry with all MCP servers."""
    # Import after registry is defined to avoid circular imports
    from src.mcp_servers.maven_maintenance.langchain_tools import get_maven_tools
    from src.mcp_servers.test_generator.langchain_tools import get_test_gen_tools
    from src.mcp_servers.docker.langchain_tools import get_docker_tools
    from src.mcp_servers.git_maintenance.langchain_tools import get_git_tools

    register_tools("maven-maintenance", get_maven_tools)
    register_tools("test-generator", get_test_gen_tools)
    register_tools("docker-deployment", get_docker_tools)
    register_tools("git-maintenance", get_git_tools)


# Initialize on module import
_initialize_registry()


__all__ = [
    "get_tools_for_servers",
    "list_available_servers",
    "register_tools",
    "TOOL_REGISTRY",
]
