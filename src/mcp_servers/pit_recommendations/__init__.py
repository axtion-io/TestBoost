"""
MCP Server for PIT Mutation Testing Recommendations.

Provides tools for analyzing mutation testing results and
recommending test improvements to increase mutation score.
"""

from mcp.server import Server
from mcp.types import Tool

from .tools.analyze import analyze_hard_mutants
from .tools.prioritize import prioritize_test_efforts
from .tools.recommend import recommend_test_improvements

# Create the MCP server instance
server = Server("pit-recommendations")


@server.list_tools()
async def list_tools() -> list[Tool]:
    """List all available PIT recommendation tools."""
    return [
        Tool(
            name="analyze-hard-mutants",
            description="Analyze mutation testing results to identify hard-to-kill mutants",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "report_path": {
                        "type": "string",
                        "description": "Path to PIT mutation report directory",
                    },
                    "group_by": {
                        "type": "string",
                        "enum": ["mutator", "class", "method"],
                        "description": "How to group hard-to-kill mutants",
                        "default": "mutator",
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="recommend-test-improvements",
            description="Generate specific recommendations for improving test effectiveness",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "mutation_analysis": {
                        "type": "object",
                        "description": "Results from analyze-hard-mutants",
                    },
                    "target_score": {
                        "type": "number",
                        "description": "Target mutation score percentage",
                        "default": 80,
                    },
                    "max_recommendations": {
                        "type": "integer",
                        "description": "Maximum number of recommendations",
                        "default": 20,
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="prioritize-test-efforts",
            description="Prioritize test improvement efforts based on impact and effort",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {
                        "type": "string",
                        "description": "Path to the Java project root directory",
                    },
                    "recommendations": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": "List of test improvement recommendations",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["quick_wins", "high_impact", "balanced"],
                        "description": "Prioritization strategy",
                        "default": "balanced",
                    },
                },
                "required": ["project_path"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> str:
    """Route tool calls to appropriate handlers."""
    if name == "analyze-hard-mutants":
        return await analyze_hard_mutants(**arguments)
    elif name == "recommend-test-improvements":
        return await recommend_test_improvements(**arguments)
    elif name == "prioritize-test-efforts":
        return await prioritize_test_efforts(**arguments)
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
