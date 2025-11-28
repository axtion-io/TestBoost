"""
MCP Server for Test Generation operations.

Provides tools for analyzing projects, detecting test conventions,
generating various test types, and running mutation testing.
"""

from mcp.server import Server
from mcp.types import Tool

from .tools.analyze import analyze_project_context
from .tools.analyze_mutants import analyze_mutants
from .tools.conventions import detect_test_conventions
from .tools.generate_integration import generate_integration_tests
from .tools.generate_snapshot import generate_snapshot_tests
from .tools.generate_unit import generate_adaptive_tests
from .tools.killer_tests import generate_killer_tests
from .tools.mutation import run_mutation_testing

# Create the MCP server instance
server = Server("test-generator")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available test generation tools."""
    return [
        Tool(
            name="analyze-project-context",
            description="Analyze Java project structure, frameworks, and testing patterns",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "include_dependencies": {
                        "type": "boolean",
                        "description": "Include dependency analysis",
                        "default": True,
                    },
                    "scan_depth": {
                        "type": "integer",
                        "description": "Maximum directory depth to scan",
                        "default": 10,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="detect-test-conventions",
            description="Detect existing test conventions and patterns in the project",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "sample_size": {
                        "type": "integer",
                        "description": "Number of test files to sample for analysis",
                        "default": 20,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="generate-adaptive-tests",
            description="Generate unit tests adapted to project conventions and class type",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "source_file": {
                        "type": "string",
                        "description": "Path to the source file to generate tests for",
                    },
                    "class_type": {
                        "type": "string",
                        "enum": ["controller", "service", "repository", "utility", "model"],
                        "description": "Classification of the class",
                    },
                    "conventions": {"type": "object", "description": "Test conventions to follow"},
                    "coverage_target": {
                        "type": "number",
                        "description": "Target code coverage percentage",
                        "default": 80,
                    },
                },
                "required": ["project_path", "source_file"],
            },
        ),
        Tool(
            name="generate-integration-tests",
            description="Generate integration tests for service interactions and database operations",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "source_file": {
                        "type": "string",
                        "description": "Path to the source file to generate tests for",
                    },
                    "test_containers": {
                        "type": "boolean",
                        "description": "Use Testcontainers for database tests",
                        "default": True,
                    },
                    "mock_external": {
                        "type": "boolean",
                        "description": "Mock external service calls",
                        "default": True,
                    },
                },
                "required": ["project_path", "source_file"],
            },
        ),
        Tool(
            name="generate-snapshot-tests",
            description="Generate snapshot tests for API responses and serialization",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "source_file": {
                        "type": "string",
                        "description": "Path to the source file to generate tests for",
                    },
                    "snapshot_format": {
                        "type": "string",
                        "enum": ["json", "xml", "text"],
                        "description": "Format for snapshot files",
                        "default": "json",
                    },
                },
                "required": ["project_path", "source_file"],
            },
        ),
        Tool(
            name="run-mutation-testing",
            description="Run mutation testing using PIT to measure test effectiveness",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "target_classes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Classes to mutate (glob patterns)",
                    },
                    "target_tests": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Tests to run against mutants (glob patterns)",
                    },
                    "mutators": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Mutation operators to use",
                        "default": ["DEFAULTS"],
                    },
                    "timeout_factor": {
                        "type": "number",
                        "description": "Factor to multiply normal test timeout",
                        "default": 1.5,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="analyze-mutants",
            description="Analyze mutation testing results to identify hard-to-kill mutants",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "report_path": {"type": "string", "description": "Path to PIT mutation report"},
                    "min_score": {
                        "type": "number",
                        "description": "Minimum mutation score threshold",
                        "default": 80,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="generate-killer-tests",
            description="Generate tests specifically designed to kill surviving mutants",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "surviving_mutants": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of surviving mutants to target",
                    },
                    "source_file": {
                        "type": "string",
                        "description": "Path to the source file with surviving mutants",
                    },
                    "max_tests": {
                        "type": "integer",
                        "description": "Maximum number of killer tests to generate",
                        "default": 10,
                    },
                },
                "required": ["project_path", "surviving_mutants"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Route tool calls to appropriate handlers."""
    if name == "analyze-project-context":
        return await analyze_project_context(**arguments)
    elif name == "detect-test-conventions":
        return await detect_test_conventions(**arguments)
    elif name == "generate-adaptive-tests":
        return await generate_adaptive_tests(**arguments)
    elif name == "generate-integration-tests":
        return await generate_integration_tests(**arguments)
    elif name == "generate-snapshot-tests":
        return await generate_snapshot_tests(**arguments)
    elif name == "run-mutation-testing":
        return await run_mutation_testing(**arguments)
    elif name == "analyze-mutants":
        return await analyze_mutants(**arguments)
    elif name == "generate-killer-tests":
        return await generate_killer_tests(**arguments)
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
