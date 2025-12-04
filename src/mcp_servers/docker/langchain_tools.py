"""LangChain BaseTool wrappers for Docker Deployment MCP tools."""

from langchain_core.tools import BaseTool, tool

# Import existing MCP tool implementations
from src.mcp_servers.docker.tools.dockerfile import create_dockerfile
from src.mcp_servers.docker.tools.compose import create_compose
from src.mcp_servers.docker.tools.deploy import deploy_compose
from src.mcp_servers.docker.tools.health import health_check
from src.mcp_servers.docker.tools.logs import collect_logs


@tool
async def docker_create_dockerfile(
    project_path: str,
    java_version: str = "",
    base_image: str = "",
    output_path: str = ""
) -> str:
    """
    Generate a Dockerfile for a Java project based on detected configuration.

    Use this tool to:
    - Auto-detect Java version from pom.xml or build.gradle
    - Select appropriate base image (Eclipse Temurin, Amazon Corretto, etc.)
    - Generate optimized multi-stage build
    - Configure JVM arguments and heap settings

    Args:
        project_path: Path to the Java project root directory
        java_version: Java version to use (auto-detected if not specified)
        base_image: Base Docker image to use (auto-selected if not specified)
        output_path: Path to write the Dockerfile (defaults to project_path/Dockerfile)

    Returns:
        Generated Dockerfile content and file path
    """
    return await create_dockerfile(
        project_path=project_path,
        java_version=java_version,
        base_image=base_image,
        output_path=output_path
    )


@tool
async def docker_create_compose(
    project_path: str,
    service_name: str = "app",
    dependencies: list[str] | None = None,
    expose_ports: bool = True,
    output_path: str = ""
) -> str:
    """
    Generate a docker-compose.yml file with application and dependencies.

    Use this tool to:
    - Create compose file with app service and dependencies
    - Auto-configure database services (PostgreSQL, MySQL, MongoDB, etc.)
    - Setup networking and volume mounts
    - Configure health checks and restart policies

    Args:
        project_path: Path to the Java project root directory
        service_name: Name for the main application service (default: "app")
        dependencies: Additional services (postgres, mysql, redis, mongodb, rabbitmq, kafka)
        expose_ports: Expose service ports to host (default: True)
        output_path: Path to write docker-compose.yml (defaults to project_path/docker-compose.yml)

    Returns:
        Generated docker-compose.yml content and file path
    """
    return await create_compose(
        project_path=project_path,
        service_name=service_name,
        dependencies=dependencies or [],
        expose_ports=expose_ports,
        output_path=output_path
    )


@tool
async def docker_deploy_compose(
    compose_path: str,
    project_name: str = "",
    build: bool = True,
    detach: bool = True,
    force_recreate: bool = False
) -> str:
    """
    Deploy containers using docker-compose.

    Use this tool to:
    - Build Docker images from Dockerfiles
    - Start all services defined in docker-compose.yml
    - Create networks and volumes
    - Monitor deployment progress

    Args:
        compose_path: Path to docker-compose.yml file
        project_name: Project name for compose (auto-generated if not specified)
        build: Build images before starting (default: True)
        detach: Run in detached mode (default: True)
        force_recreate: Force recreation of containers (default: False)

    Returns:
        Deployment status with container IDs and network info
    """
    return await deploy_compose(
        compose_path=compose_path,
        project_name=project_name,
        build=build,
        detach=detach,
        force_recreate=force_recreate
    )


@tool
async def docker_health_check(
    compose_path: str,
    project_name: str = "",
    timeout: int = 120,
    check_interval: int = 5,
    endpoints: list[dict] | None = None
) -> str:
    """
    Check health status of deployed containers with wait logic.

    Use this tool to:
    - Wait for containers to become healthy
    - Check Docker health status
    - Validate HTTP endpoints are responding
    - Monitor startup progress with retries

    Args:
        compose_path: Path to docker-compose.yml file
        project_name: Project name for compose (auto-detected if not specified)
        timeout: Timeout in seconds to wait for healthy status (default: 120)
        check_interval: Interval in seconds between health checks (default: 5)
        endpoints: HTTP endpoints to check [{"url": "...", "method": "GET", "expected_status": 200}]

    Returns:
        Health status for all containers and endpoints
    """
    return await health_check(
        compose_path=compose_path,
        project_name=project_name,
        timeout=timeout,
        check_interval=check_interval,
        endpoints=endpoints or []
    )


@tool
async def docker_collect_logs(
    compose_path: str,
    project_name: str = "",
    services: list[str] | None = None,
    tail: int = 100,
    since: str = "",
    follow: bool = False
) -> str:
    """
    Collect logs from deployed containers.

    Use this tool to:
    - Retrieve container logs for debugging
    - Monitor application startup
    - Diagnose deployment failures
    - Stream logs in real-time

    Args:
        compose_path: Path to docker-compose.yml file
        project_name: Project name for compose (auto-detected if not specified)
        services: Services to collect logs from (empty for all services)
        tail: Number of lines to show from the end (default: 100)
        since: Show logs since timestamp (e.g., '10m', '1h') (optional)
        follow: Follow log output in real-time (default: False)

    Returns:
        Container logs with timestamps and service names
    """
    return await collect_logs(
        compose_path=compose_path,
        project_name=project_name,
        services=services or [],
        tail=tail,
        since=since,
        follow=follow
    )


def get_docker_tools() -> list[BaseTool]:
    """
    Get all Docker deployment tools as BaseTool instances.

    Returns:
        List of 5 Docker deployment tools:
        - docker_create_dockerfile: Generate Dockerfile
        - docker_create_compose: Generate docker-compose.yml
        - docker_deploy_compose: Deploy with docker-compose
        - docker_health_check: Check container health
        - docker_collect_logs: Collect container logs
    """
    return [
        docker_create_dockerfile,
        docker_create_compose,
        docker_deploy_compose,
        docker_health_check,
        docker_collect_logs,
    ]


__all__ = [
    "get_docker_tools",
    "docker_create_dockerfile",
    "docker_create_compose",
    "docker_deploy_compose",
    "docker_health_check",
    "docker_collect_logs",
]
