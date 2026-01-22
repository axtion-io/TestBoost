"""
MCP Server for Container Runtime operations.

Provides tools for creating and managing Docker containers for Maven builds.
"""

from typing import Any

from mcp.server import Server
from mcp.types import Tool

from .tools.destroy import destroy_container
from .tools.execute import execute_in_container
from .tools.maven import create_maven_container

# Create the MCP server instance
server = Server("container-runtime")


@server.list_tools()  # type: ignore
async def list_tools() -> list[Tool]:
    """List all available container runtime tools."""
    return [
        Tool(
            name="create-maven-container",
            description="Create a Docker container for Maven builds",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Maven project to mount",
                    },
                    "java_version": {
                        "type": "string",
                        "description": "Java version to use (e.g., '11', '17', '21')",
                        "default": "17",
                    },
                    "maven_version": {
                        "type": "string",
                        "description": "Maven version to use (e.g., '3.9.5')",
                        "default": "3.9.5",
                    },
                    "container_name": {
                        "type": "string",
                        "description": "Name for the container",
                        "default": "testboost-maven",
                    },
                    "memory_limit": {
                        "type": "string",
                        "description": "Memory limit (e.g., '2g')",
                        "default": "2g",
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="execute-in-container",
            description="Execute a command inside a running container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"},
                    "command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command and arguments to execute",
                    },
                    "workdir": {
                        "type": "string",
                        "description": "Working directory inside container",
                        "default": "/project",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 300,
                    },
                },
                "required": ["container_id", "command"],
            },
        ),
        Tool(
            name="destroy-container",
            description="Stop and remove a container",
            inputSchema={
                "type": "object",
                "properties": {
                    "container_id": {"type": "string", "description": "Container ID or name"},
                    "force": {
                        "type": "boolean",
                        "description": "Force removal of running container",
                        "default": False,
                    },
                    "remove_volumes": {
                        "type": "boolean",
                        "description": "Remove associated volumes",
                        "default": False,
                    },
                },
                "required": ["container_id"],
            },
        ),
    ]


@server.call_tool()  # type: ignore
async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Route tool calls to appropriate handlers."""
    if name == "create-maven-container":
        return await create_maven_container(**arguments)
    elif name == "execute-in-container":
        return await execute_in_container(**arguments)
    elif name == "destroy-container":
        return await destroy_container(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
