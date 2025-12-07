"""LangChain BaseTool wrappers for Test Generator MCP tools."""

from typing import Any

from langchain_core.tools import BaseTool, tool

# Import existing MCP tool implementations
from src.mcp_servers.test_generator.tools.analyze import analyze_project_context
from src.mcp_servers.test_generator.tools.conventions import detect_test_conventions
from src.mcp_servers.test_generator.tools.generate_unit import generate_adaptive_tests
from src.mcp_servers.test_generator.tools.generate_integration import generate_integration_tests
from src.mcp_servers.test_generator.tools.generate_snapshot import generate_snapshot_tests
from src.mcp_servers.test_generator.tools.mutation import run_mutation_testing
from src.mcp_servers.test_generator.tools.analyze_mutants import analyze_mutants
from src.mcp_servers.test_generator.tools.killer_tests import generate_killer_tests


@tool
async def test_gen_analyze_project(
    project_path: str,
    include_dependencies: bool = True,
    scan_depth: int = 10
) -> str:
    """
    Analyze Java project structure, frameworks, and testing patterns.

    Use this tool to:
    - Detect project structure (Maven/Gradle, Spring Boot, etc.)
    - Identify testing frameworks (JUnit, Mockito, AssertJ, etc.)
    - Discover existing test patterns and conventions
    - Map source files to test files

    Args:
        project_path: Path to the Java project root directory
        include_dependencies: Include dependency analysis (default: True)
        scan_depth: Maximum directory depth to scan (default: 10)

    Returns:
        JSON with project metadata, frameworks, dependencies, and file structure
    """
    return await analyze_project_context(
        project_path=project_path,
        include_dependencies=include_dependencies,
        scan_depth=scan_depth
    )


@tool
async def test_gen_detect_conventions(
    project_path: str,
    sample_size: int = 20
) -> str:
    """
    Detect existing test conventions and patterns in the project.

    Use this tool to:
    - Identify naming conventions (e.g., Test suffix vs Should prefix)
    - Detect assertion styles (AssertJ fluent vs JUnit classic)
    - Find mocking patterns (Mockito annotations vs manual mocks)
    - Discover test organization patterns

    Args:
        project_path: Path to the Java project root directory
        sample_size: Number of test files to sample for analysis (default: 20)

    Returns:
        JSON with detected conventions for naming, assertions, mocking, and organization
    """
    return await detect_test_conventions(
        project_path=project_path,
        sample_size=sample_size
    )


@tool
async def test_gen_generate_unit_tests(
    project_path: str,
    source_file: str,
    class_type: str | None = None,
    conventions: dict[str, Any] | None = None,
    coverage_target: float = 80.0
) -> str:
    """
    Generate unit tests adapted to project conventions and class type.

    Use this tool to:
    - Generate unit tests following project conventions
    - Adapt test style to class type (Controller, Service, Repository, etc.)
    - Target specific code coverage percentage
    - Use appropriate mocking and assertion strategies

    Args:
        project_path: Path to the Java project root directory
        source_file: Path to the source file to generate tests for
        class_type: Classification of the class (controller, service, repository, utility, model)
        conventions: Test conventions to follow (from detect_test_conventions)
        coverage_target: Target code coverage percentage (default: 80.0)

    Returns:
        Generated test code as a string
    """
    return await generate_adaptive_tests(
        project_path=project_path,
        source_file=source_file,
        class_type=class_type,
        conventions=conventions,
        coverage_target=coverage_target
    )


@tool
async def test_gen_generate_integration_tests(
    project_path: str,
    source_file: str,
    test_containers: bool = True,
    mock_external: bool = True
) -> str:
    """
    Generate integration tests for service interactions and database operations.

    Use this tool to:
    - Generate integration tests with Testcontainers for database tests
    - Test service layer interactions with real/mocked dependencies
    - Validate transaction handling and rollback behavior
    - Test repository queries against real database

    Args:
        project_path: Path to the Java project root directory
        source_file: Path to the source file to generate tests for
        test_containers: Use Testcontainers for database tests (default: True)
        mock_external: Mock external service calls (default: True)

    Returns:
        Generated integration test code as a string
    """
    return await generate_integration_tests(
        project_path=project_path,
        source_file=source_file,
        test_containers=test_containers,
        mock_external=mock_external
    )


@tool
async def test_gen_generate_snapshot_tests(
    project_path: str,
    source_file: str,
    snapshot_format: str = "json"
) -> str:
    """
    Generate snapshot tests for API responses and serialization.

    Use this tool to:
    - Generate snapshot tests for REST controller responses
    - Capture and verify JSON/XML output
    - Detect unintended API contract changes
    - Test complex object serialization

    Args:
        project_path: Path to the Java project root directory
        source_file: Path to the source file to generate tests for
        snapshot_format: Format for snapshot files (json, xml, text) (default: json)

    Returns:
        Generated snapshot test code as a string
    """
    return await generate_snapshot_tests(
        project_path=project_path,
        source_file=source_file,
        snapshot_format=snapshot_format
    )


@tool
async def test_gen_run_mutation_testing(
    project_path: str,
    target_classes: list[str] | None = None,
    target_tests: list[str] | None = None,
    mutators: list[str] | None = None,
    timeout_factor: float = 1.5
) -> str:
    """
    Run mutation testing using PIT to measure test effectiveness.

    Use this tool to:
    - Measure true test effectiveness (not just coverage)
    - Identify weak tests that don't catch bugs
    - Get mutation score percentage
    - Find hard-to-kill mutants

    Args:
        project_path: Path to the Java project root directory
        target_classes: Classes to mutate with glob patterns (optional, defaults to all)
        target_tests: Tests to run against mutants with glob patterns (optional, defaults to all)
        mutators: Mutation operators to use (default: ["DEFAULTS"])
        timeout_factor: Factor to multiply normal test timeout (default: 1.5)

    Returns:
        JSON with mutation score, killed/survived mutant counts, and detailed results
    """
    return await run_mutation_testing(
        project_path=project_path,
        target_classes=target_classes,
        target_tests=target_tests,
        mutators=mutators or ["DEFAULTS"],
        timeout_factor=timeout_factor
    )


@tool
async def test_gen_analyze_mutants(
    project_path: str,
    report_path: str | None = None,
    min_score: float = 80.0
) -> str:
    """
    Analyze mutation testing results to identify hard-to-kill mutants.

    Use this tool to:
    - Identify patterns in surviving mutants
    - Find classes with low mutation scores
    - Get recommendations for improving tests
    - Prioritize test improvement efforts

    Args:
        project_path: Path to the Java project root directory
        report_path: Path to PIT mutation report (optional, auto-detected if not provided)
        min_score: Minimum mutation score threshold (default: 80.0)

    Returns:
        JSON with mutant analysis, low-score classes, and improvement recommendations
    """
    return await analyze_mutants(
        project_path=project_path,
        report_path=report_path,
        min_score=min_score
    )


@tool
async def test_gen_generate_killer_tests(
    project_path: str,
    surviving_mutants: list[dict[str, Any]],
    source_file: str,
    max_tests: int = 10
) -> str:
    """
    Generate tests specifically designed to kill surviving mutants.

    Use this tool to:
    - Generate targeted tests for hard-to-kill mutants
    - Improve mutation score by killing specific mutants
    - Create edge case tests for boundary conditions
    - Add assertions for unchecked behavior

    Args:
        project_path: Path to the Java project root directory
        surviving_mutants: List of surviving mutants to target (from analyze_mutants)
        source_file: Path to the source file with surviving mutants
        max_tests: Maximum number of killer tests to generate (default: 10)

    Returns:
        Generated killer test code as a string
    """
    return await generate_killer_tests(
        project_path=project_path,
        surviving_mutants=surviving_mutants,
        source_file=source_file,
        max_tests=max_tests
    )


def get_test_gen_tools() -> list[BaseTool]:
    """
    Get all test generation tools as BaseTool instances.

    Returns:
        List of 8 test generation tools:
        - test_gen_analyze_project: Analyze project structure and frameworks
        - test_gen_detect_conventions: Detect test conventions
        - test_gen_generate_unit_tests: Generate adaptive unit tests
        - test_gen_generate_integration_tests: Generate integration tests
        - test_gen_generate_snapshot_tests: Generate snapshot tests
        - test_gen_run_mutation_testing: Run PIT mutation testing
        - test_gen_analyze_mutants: Analyze mutation results
        - test_gen_generate_killer_tests: Generate tests for surviving mutants
    """
    return [
        test_gen_analyze_project,
        test_gen_detect_conventions,
        test_gen_generate_unit_tests,
        test_gen_generate_integration_tests,
        test_gen_generate_snapshot_tests,
        test_gen_run_mutation_testing,
        test_gen_analyze_mutants,
        test_gen_generate_killer_tests,
    ]


__all__ = [
    "get_test_gen_tools",
    "test_gen_analyze_project",
    "test_gen_detect_conventions",
    "test_gen_generate_unit_tests",
    "test_gen_generate_integration_tests",
    "test_gen_generate_snapshot_tests",
    "test_gen_run_mutation_testing",
    "test_gen_analyze_mutants",
    "test_gen_generate_killer_tests",
]
