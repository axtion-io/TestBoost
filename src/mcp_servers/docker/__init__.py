"""
MCP Server for Docker Deployment operations.

Provides tools for creating Dockerfiles, docker-compose configurations,
deploying containers, and managing container health and logs.
"""

from typing import Any

from mcp.server import Server
from mcp.types import Tool

from .tools.compose import create_compose
from .tools.deploy import deploy_compose
from .tools.dockerfile import create_dockerfile
from .tools.health import health_check
from .tools.logs import collect_logs

# Create the MCP server instance
server = Server("docker-deployment")


@server.list_tools()  # type: ignore[untyped-decorator]
async def list_tools() -> list[Tool]:
    """List all available Docker deployment tools."""
    return [
        Tool(
            name="create-dockerfile",
            description="Generate a Dockerfile for a Java project based on detected configuration",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "description": "Path to the Java project"},
                    "java_version": {
                        "type": "string",
                        "description": "Java version to use (auto-detected if not specified)",
                        "default": "",
                    },
                    "base_image": {
                        "type": "string",
                        "description": "Base Docker image to use",
                        "default": "",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to write the Dockerfile",
                        "default": "",
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="create-compose",
            description="Generate a docker-compose.yml file with application and dependencies",
            inputSchema={
                "type": "object",
                "properties": {
                    "project_path": {"type": "string", "description": "Path to the Java project"},
                    "service_name": {
                        "type": "string",
                        "description": "Name for the main service",
                        "default": "app",
                    },
                    "dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Additional services (postgres, mysql, redis, mongodb, rabbitmq, kafka)",
                        "default": [],
                    },
                    "expose_ports": {
                        "type": "boolean",
                        "description": "Expose service ports to host",
                        "default": True,
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Path to write docker-compose.yml",
                        "default": "",
                    },
                },
                "required": ["project_path"],
            },
        ),
        Tool(
            name="deploy-compose",
            description="Deploy containers using docker-compose",
            inputSchema={
                "type": "object",
                "properties": {
                    "compose_path": {
                        "type": "string",
                        "description": "Path to docker-compose.yml file",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project name for compose",
                        "default": "",
                    },
                    "build": {
                        "type": "boolean",
                        "description": "Build images before starting",
                        "default": True,
                    },
                    "detach": {
                        "type": "boolean",
                        "description": "Run in detached mode",
                        "default": True,
                    },
                    "force_recreate": {
                        "type": "boolean",
                        "description": "Force recreation of containers",
                        "default": False,
                    },
                },
                "required": ["compose_path"],
            },
        ),
        Tool(
            name="health-check",
            description="Check health status of deployed containers with wait logic",
            inputSchema={
                "type": "object",
                "properties": {
                    "compose_path": {
                        "type": "string",
                        "description": "Path to docker-compose.yml file",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project name for compose",
                        "default": "",
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds to wait for healthy status",
                        "default": 120,
                    },
                    "check_interval": {
                        "type": "integer",
                        "description": "Interval in seconds between health checks",
                        "default": 5,
                    },
                    "endpoints": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "url": {"type": "string"},
                                "method": {"type": "string", "default": "GET"},
                                "expected_status": {"type": "integer", "default": 200},
                            },
                        },
                        "description": "HTTP endpoints to check for health",
                        "default": [],
                    },
                },
                "required": ["compose_path"],
            },
        ),
        Tool(
            name="collect-logs",
            description="Collect logs from deployed containers",
            inputSchema={
                "type": "object",
                "properties": {
                    "compose_path": {
                        "type": "string",
                        "description": "Path to docker-compose.yml file",
                    },
                    "project_name": {
                        "type": "string",
                        "description": "Project name for compose",
                        "default": "",
                    },
                    "services": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Services to collect logs from (empty for all)",
                        "default": [],
                    },
                    "tail": {
                        "type": "integer",
                        "description": "Number of lines to show from the end",
                        "default": 100,
                    },
                    "since": {
                        "type": "string",
                        "description": "Show logs since timestamp (e.g., '10m', '1h')",
                        "default": "",
                    },
                    "follow": {
                        "type": "boolean",
                        "description": "Follow log output",
                        "default": False,
                    },
                },
                "required": ["compose_path"],
            },
        ),
    ]


@server.call_tool()  # type: ignore[untyped-decorator]
async def call_tool(name: str, arguments: dict[str, Any]) -> str:
    """Route tool calls to appropriate handlers."""
    if name == "create-dockerfile":
        return await create_dockerfile(**arguments)  # type: ignore[no-untyped-call]
    elif name == "create-compose":
        return await create_compose(**arguments)  # type: ignore[no-untyped-call]
    elif name == "deploy-compose":
        return await deploy_compose(**arguments)  # type: ignore[no-untyped-call]
    elif name == "health-check":
        return await health_check(**arguments)  # type: ignore[no-untyped-call]
    elif name == "collect-logs":
        return await collect_logs(**arguments)  # type: ignore[no-untyped-call]
    else:
        raise ValueError(f"Unknown tool: {name}")


async def main() -> None:
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())  # type: ignore[no-untyped-call]


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
