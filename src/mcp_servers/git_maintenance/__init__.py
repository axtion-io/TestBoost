"""
MCP Server for Git Maintenance operations.

Provides tools for managing git branches, commits, and status
during maintenance workflows.
"""

from typing import Any

from mcp.server import Server
from mcp.types import Tool

from .tools.branch import create_maintenance_branch
from .tools.commit import commit_changes
from .tools.status import get_status

# Create the MCP server instance
server = Server("git-maintenance")


@server.list_tools()  # type: ignore
async def list_tools() -> list[Tool]:
    """List all available Git maintenance tools."""
    return [
        Tool(
            name="create-maintenance-branch",
            description="Create a new branch for maintenance work",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository"},
                    "branch_name": {
                        "type": "string",
                        "description": "Name for the new maintenance branch",
                    },
                    "base_branch": {
                        "type": "string",
                        "description": "Base branch to create from",
                        "default": "main",
                    },
                },
                "required": ["repo_path", "branch_name"],
            },
        ),
        Tool(
            name="commit-changes",
            description="Commit staged changes with a descriptive message",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository"},
                    "message": {"type": "string", "description": "Commit message"},
                    "files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific files to commit (empty for all staged)",
                    },
                },
                "required": ["repo_path", "message"],
            },
        ),
        Tool(
            name="get-status",
            description="Get the current git status of the repository",
            inputSchema={
                "type": "object",
                "properties": {
                    "repo_path": {"type": "string", "description": "Path to the git repository"},
                    "include_untracked": {
                        "type": "boolean",
                        "description": "Include untracked files in status",
                        "default": True,
                    },
                },
                "required": ["repo_path"],
            },
        ),
    ]


@server.call_tool()  # type: ignore
async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Route tool calls to appropriate handlers."""
    if name == "create-maintenance-branch":
        return await create_maintenance_branch(**arguments)
    elif name == "commit-changes":
        return await commit_changes(**arguments)
    elif name == "get-status":
        return await get_status(**arguments)
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
