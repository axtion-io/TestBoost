"""LangChain BaseTool wrappers for Maven Maintenance MCP tools."""

from langchain_core.tools import BaseTool, tool

from src.lib.logging import get_logger

# Import existing MCP tool implementations
from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies
from src.mcp_servers.maven_maintenance.tools.compile import compile_tests
from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests
from src.mcp_servers.maven_maintenance.tools.package import package_project

logger = get_logger(__name__)


@tool
async def maven_analyze_dependencies(
    project_path: str,
    include_snapshots: bool = False,
    check_vulnerabilities: bool = True
) -> str:
    """
    Analyze Maven project dependencies for updates, vulnerabilities, and compatibility issues.

    Use this tool to:
    - Find outdated dependencies with available updates
    - Detect security vulnerabilities in dependencies
    - Check compatibility between dependency versions
    - Get recommended version upgrades

    Args:
        project_path: Path to the Maven project root directory (must contain pom.xml)
        include_snapshots: Include SNAPSHOT versions in analysis (default: False)
        check_vulnerabilities: Check for known security vulnerabilities (default: True)

    Returns:
        JSON string with analysis results including outdated dependencies,
        vulnerabilities, and update recommendations
    """
    logger.info(
        "mcp_tool_called",
        tool="maven_analyze_dependencies",
        project_path=project_path,
        include_snapshots=include_snapshots,
        check_vulnerabilities=check_vulnerabilities
    )

    result = await analyze_dependencies(
        project_path=project_path,
        include_snapshots=include_snapshots,
        check_vulnerabilities=check_vulnerabilities
    )

    logger.info(
        "mcp_tool_completed",
        tool="maven_analyze_dependencies",
        result_length=len(result)
    )

    return result


@tool
async def maven_compile_tests(
    project_path: str,
    profiles: list[str] | None = None,
    skip_main: bool = False
) -> str:
    """
    Compile test sources for a Maven project.

    Use this tool to:
    - Verify test sources compile after dependency updates
    - Detect compilation errors before running tests
    - Validate build integrity

    Args:
        project_path: Path to the Maven project root directory (must contain pom.xml)
        profiles: Maven profiles to activate during compilation (optional)
        skip_main: Skip main source compilation and only compile tests (default: False)

    Returns:
        Compilation result message with success/failure status and error details
    """
    logger.info(
        "mcp_tool_called",
        tool="maven_compile_tests",
        project_path=project_path,
        profiles=profiles,
        skip_main=skip_main
    )

    result = await compile_tests(
        project_path=project_path,
        profiles=profiles or [],
        skip_main=skip_main
    )

    logger.info(
        "mcp_tool_completed",
        tool="maven_compile_tests",
        result_length=len(result)
    )

    return result


@tool
async def maven_run_tests(
    project_path: str,
    test_pattern: str = "**/Test*.java",
    profiles: list[str] | None = None,
    parallel: bool = False,
    fail_fast: bool = False
) -> str:
    """
    Execute tests for a Maven project.

    Use this tool to:
    - Run tests after dependency updates to validate changes
    - Establish baseline test results before updates
    - Detect test failures caused by dependency changes

    Args:
        project_path: Path to the Maven project root directory (must contain pom.xml)
        test_pattern: Pattern to match test classes (default: "**/Test*.java")
        profiles: Maven profiles to activate during test execution (optional)
        parallel: Run tests in parallel for faster execution (default: False)
        fail_fast: Stop on first failure instead of running all tests (default: False)

    Returns:
        Test execution results with pass/fail counts, execution time, and failure details
    """
    logger.info(
        "mcp_tool_called",
        tool="maven_run_tests",
        project_path=project_path,
        test_pattern=test_pattern,
        profiles=profiles,
        parallel=parallel,
        fail_fast=fail_fast
    )

    result = await run_tests(
        project_path=project_path,
        test_pattern=test_pattern,
        profiles=profiles or [],
        parallel=parallel,
        fail_fast=fail_fast
    )

    logger.info(
        "mcp_tool_completed",
        tool="maven_run_tests",
        result_length=len(result)
    )

    return result


@tool
async def maven_package(
    project_path: str,
    skip_tests: bool = False,
    profiles: list[str] | None = None
) -> str:
    """
    Package a Maven project (create JAR/WAR).

    Use this tool to:
    - Verify full build succeeds after dependency updates
    - Create deployable artifact
    - Validate packaging configuration

    Args:
        project_path: Path to the Maven project root directory (must contain pom.xml)
        skip_tests: Skip test execution during packaging (default: False)
        profiles: Maven profiles to activate during packaging (optional)

    Returns:
        Packaging result with artifact location and build status
    """
    logger.info(
        "mcp_tool_called",
        tool="maven_package",
        project_path=project_path,
        skip_tests=skip_tests,
        profiles=profiles
    )

    result = await package_project(
        project_path=project_path,
        skip_tests=skip_tests,
        profiles=profiles or []
    )

    logger.info(
        "mcp_tool_completed",
        tool="maven_package",
        result_length=len(result)
    )

    return result


def get_maven_tools() -> list[BaseTool]:
    """
    Get all Maven maintenance tools as BaseTool instances.

    Returns:
        List of 4 Maven maintenance tools:
        - maven_analyze_dependencies: Analyze dependencies for updates/vulnerabilities
        - maven_compile_tests: Compile test sources
        - maven_run_tests: Execute project tests
        - maven_package: Package the project
    """
    return [
        maven_analyze_dependencies,
        maven_compile_tests,
        maven_run_tests,
        maven_package,
    ]


__all__ = [
    "get_maven_tools",
    "maven_analyze_dependencies",
    "maven_compile_tests",
    "maven_run_tests",
    "maven_package",
]
