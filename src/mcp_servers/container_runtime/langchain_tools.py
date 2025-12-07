"""LangChain BaseTool wrappers for Container Runtime MCP tools."""

from langchain_core.tools import BaseTool, tool

from src.mcp_servers.container_runtime.tools.destroy import destroy_container
from src.mcp_servers.container_runtime.tools.execute import execute_in_container

# Import existing MCP tool implementations
from src.mcp_servers.container_runtime.tools.maven import create_maven_container


@tool
async def container_create_maven(
    project_path: str,
    java_version: str = "17",
    maven_version: str = "3.9.5",
    container_name: str = "testboost-maven",
    memory_limit: str = "2g"
) -> str:
    """
    Create a Docker container for Maven builds.

    Use this tool to:
    - Create containerized Maven build environment
    - Auto-configure Java and Maven versions
    - Mount project directory for builds
    - Set resource limits (memory, CPU)

    Args:
        project_path: Path to the Maven project to mount
        java_version: Java version to use (e.g., '11', '17', '21')
        maven_version: Maven version to use (e.g., '3.9.5')
        container_name: Name for the container (default: 'testboost-maven')
        memory_limit: Memory limit (default: '2g')

    Returns:
        Container creation status with ID and configuration details
    """
    return await create_maven_container(
        project_path=project_path,
        java_version=java_version,
        maven_version=maven_version,
        container_name=container_name,
        memory_limit=memory_limit
    )


@tool
async def container_execute(
    container_id: str,
    command: list[str],
    workdir: str = "/project",
    timeout: int = 300
) -> str:
    """
    Execute a command inside a running Docker container.

    Use this tool to:
    - Run Maven commands (mvn clean install, mvn test)
    - Execute build scripts
    - Run validation commands
    - Collect build outputs

    Args:
        container_id: Container ID or name
        command: Command and arguments to execute (e.g., ['mvn', 'clean', 'install'])
        workdir: Working directory inside container (default: '/project')
        timeout: Timeout in seconds (default: 300)

    Returns:
        Execution results with stdout, stderr, and exit code
    """
    return await execute_in_container(
        container_id=container_id,
        command=command,
        workdir=workdir,
        timeout=timeout
    )


@tool
async def container_destroy(
    container_id: str,
    force: bool = False,
    remove_volumes: bool = False
) -> str:
    """
    Stop and remove a Docker container.

    Use this tool to:
    - Clean up after builds
    - Remove stopped containers
    - Free up resources
    - Remove associated volumes

    Args:
        container_id: Container ID or name
        force: Force removal of running container (default: False)
        remove_volumes: Remove associated volumes (default: False)

    Returns:
        Destruction status with cleanup details
    """
    return await destroy_container(
        container_id=container_id,
        force=force,
        remove_volumes=remove_volumes
    )


def get_container_runtime_tools() -> list[BaseTool]:
    """
    Get all Container Runtime tools as BaseTool instances.

    Returns:
        List of 3 Container Runtime tools:
        - container_create_maven: Create Maven build container
        - container_execute: Execute commands in container
        - container_destroy: Stop and remove container
    """
    return [
        container_create_maven,
        container_execute,
        container_destroy,
    ]


__all__ = [
    "get_container_runtime_tools",
    "container_create_maven",
    "container_execute",
    "container_destroy",
]
