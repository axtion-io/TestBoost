"""
MCP Server for Maven Maintenance operations.

Provides tools for analyzing dependencies, compiling tests, running tests,
and packaging Maven projects.
"""

from mcp.server import Server
from mcp.types import Tool

from .tools.analyze import analyze_dependencies
from .tools.compile import compile_tests
from .tools.package import package_project
from .tools.run_tests import run_tests

# Create the MCP server instance
server = Server("maven-maintenance")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Maven maintenance tools."""
    return [
        Tool(
            name="analyze-dependencies",
            description="Analyze Maven project dependencies for updates, vulnerabilities, and compatibility issues",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Maven project root directory",
                    },
                    "include_snapshots": {
                        "type": "boolean",
                        "description": "Include SNAPSHOT versions in analysis",
                        "default": False,
                    },
                    "check_vulnerabilities": {
                        "type": "boolean",
                        "description": "Check for known security vulnerabilities",
                        "default": True,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="compile-tests",
            description="Compile test sources for a Maven project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Maven project root directory",
                    },
                    "profiles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Maven profiles to activate",
                        "default": [],
                    },
                    "skip_main": {
                        "type": "boolean",
                        "description": "Skip main source compilation",
                        "default": False,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="run-tests",
            description="Execute tests for a Maven project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Maven project root directory",
                    },
                    "test_pattern": {
                        "type": "string",
                        "description": "Pattern to match test classes",
                        "default": "**/Test*.java",
                    },
                    "profiles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Maven profiles to activate",
                        "default": [],
                    },
                    "parallel": {
                        "type": "boolean",
                        "description": "Run tests in parallel",
                        "default": False,
                    },
                    "fail_fast": {
                        "type": "boolean",
                        "description": "Stop on first failure",
                        "default": False,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="package",
            description="Package a Maven project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Maven project root directory",
                    },
                    "skip_tests": {
                        "type": "boolean",
                        "description": "Skip test execution during packaging",
                        "default": False,
                    },
                    "profiles": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Maven profiles to activate",
                        "default": [],
                    },
                },
                "required": ["project_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Route tool calls to appropriate handlers."""
    if name == "analyze-dependencies":
        return await analyze_dependencies(**arguments)
    elif name == "compile-tests":
        return await compile_tests(**arguments)
    elif name == "run-tests":
        return await run_tests(**arguments)
    elif name == "package":
        return await package_project(**arguments)
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
