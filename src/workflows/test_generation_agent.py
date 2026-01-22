"""
Test Generation Workflow with DeepAgents LLM Integration.

Implements User Story 4 (US4) from 002-deepagents-integration:
- Real LLM agent for test generation analysis
- Auto-correction retry logic for compilation errors (A2: max 3 attempts)
- Tool-based project context analysis
- Artifact storage for agent reasoning and metrics

Tasks implemented: T054-T064
"""

import json
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent

from src.agents.loader import AgentLoader
from src.db.repository import ArtifactRepository, SessionRepository
from src.lib.agent_retry import invoke_agent_with_retry
from src.lib.config import get_settings
from src.lib.llm import LLMError, get_llm
from src.lib.logging import get_logger
from src.mcp_servers.registry import get_tools_for_servers
from src.mcp_servers.test_generator.tools.generate_unit import generate_adaptive_tests
from src.models.impact import TestRequirement

logger = get_logger(__name__)
settings = get_settings()

# Retry configuration for auto-correction (A2 edge case)
MAX_CORRECTION_RETRIES = 3

# Feedback loop configuration - run tests and fix until passing
MAX_TEST_ITERATIONS = 5  # Maximum attempts to fix failing tests
TEST_TIMEOUT_SECONDS = 300  # 5 minutes timeout for Maven test run

# Write verification configuration
MAX_WRITE_RETRIES = 3  # Maximum retries for file write with verification
WRITE_RETRY_DELAY_BASE = 0.5  # Base delay in seconds for retry backoff


class TestGenerationError(Exception):
    """Base exception for test generation errors."""

    def __init__(self, message: str = "Test generation failed", source_file: str | None = None):
        if source_file:
            message = f"{message} for {source_file}"
        super().__init__(message)
        self.source_file = source_file


class CompilationError(TestGenerationError):
    """Raised when generated tests fail to compile."""

    def __init__(self, message: str = "Generated tests failed to compile", test_file: str | None = None, errors: list[str] | None = None):
        if test_file:
            message = f"{message}: {test_file}"
        if errors:
            message = f"{message}. Errors: {'; '.join(errors[:3])}"
        super().__init__(message)
        self.test_file = test_file
        self.errors = errors or []


class MavenNotFoundError(TestGenerationError):
    """Raised when Maven executable is not found on the system.

    This typically means Maven is not installed or not in the system PATH.
    """

    def __init__(
        self,
        message: str = "Maven executable not found",
        search_paths: list[str] | None = None,
    ):
        if search_paths:
            message = f"{message}. Searched in: {', '.join(search_paths)}"
        super().__init__(message)
        self.search_paths = search_paths or []


class MavenTimeoutError(TestGenerationError):
    """Raised when Maven test execution times out.

    This can happen with large test suites or slow CI environments.
    """

    def __init__(
        self,
        message: str = "Maven test execution timed out",
        timeout_seconds: float | None = None,
        module: str | None = None,
    ):
        if timeout_seconds:
            message = f"{message} after {timeout_seconds}s"
        if module:
            message = f"{message} (module: {module})"
        super().__init__(message)
        self.timeout_seconds = timeout_seconds
        self.module = module


def _find_source_files(project_path: str) -> list[str]:
    """
    Find Java source files to generate tests for.

    Filters out test files, DTOs, entities, configuration, and other non-testable classes.

    Args:
        project_path: Path to the Java project root

    Returns:
        List of relative paths to source files
    """
    project_dir = Path(project_path)
    source_files = []

    # Patterns to include (testable classes)
    # Include all Java files, then filter with exclude patterns
    include_patterns = [
        "**/*.java",  # All Java files
    ]

    # Patterns to exclude
    exclude_patterns = [
        "**/test/**",  # Test files
        "**/model/**",  # Entities, DTOs
        "**/entity/**",
        "**/dto/**",
        "**/config/**",  # Configuration
        "**/configuration/**",
        "**/mapper/**",  # Mappers (usually simple)
        # Note: Main Application classes are excluded only if they're simple Spring Boot launchers
        # "**/*Application.java",  # Too restrictive - some Application classes have business logic
        "**/*Config.java",
        "**/*Configuration.java",
        "**/*Request.java",  # Request/Response DTOs
        "**/*Response.java",
        "**/*DTO.java",
        "**/*Exception.java",  # Exceptions
    ]

    # Find all Java files in src/main/java
    main_java_dirs = list(project_dir.glob("**/src/main/java"))

    for main_java_dir in main_java_dirs:
        for pattern in include_patterns:
            for source_file in main_java_dir.glob(pattern):
                # Check if file should be excluded
                relative_path = str(source_file.relative_to(project_dir))
                should_exclude = False

                for exclude in exclude_patterns:
                    # Simple pattern matching
                    exclude_name = exclude.replace("**/*", "").replace("**", "")
                    if exclude_name in relative_path or source_file.name.endswith(exclude_name.replace("*", "")):
                        should_exclude = True
                        break

                if not should_exclude and relative_path not in source_files:
                    source_files.append(relative_path)

    logger.info("source_files_found", count=len(source_files), project_path=project_path)
    return source_files


async def _generate_tests_directly(
    project_path: str,
    source_files: list[str],
    test_requirements: list[TestRequirement] | None = None,
    use_llm: bool = True,
) -> list[dict[str, Any]]:
    """
    Generate tests by calling the generator tool for each source file.

    Args:
        project_path: Path to the Java project
        source_files: List of source files to generate tests for
        test_requirements: Optional test requirements from impact analysis
        use_llm: If True (default), use LLM for intelligent test generation.
                 If False, use template-based generation (for CI without LLM).

    Returns:
        List of generated test info dicts
    """
    generated_tests = []

    # Convert test requirements to dict format
    requirements_by_file: dict[str, list[dict[str, Any]]] = {}
    if test_requirements:
        for req in test_requirements:
            # Match requirement to source file by class name
            for source_file in source_files:
                if req.target_class and req.target_class in source_file:
                    if source_file not in requirements_by_file:
                        requirements_by_file[source_file] = []
                    requirements_by_file[source_file].append({
                        "suggested_test_name": req.suggested_test_name,
                        "description": req.description,
                        "scenario_type": req.scenario_type.value if req.scenario_type else "nominal",
                        "target_method": req.target_method,
                    })

    for source_file in source_files:
        logger.info("generating_tests_for_file", source_file=source_file)

        try:
            # Get requirements for this file if any
            file_requirements = requirements_by_file.get(source_file)

            # Call generator with LLM mode (production) or template mode (CI)
            result_json = await generate_adaptive_tests(
                project_path=project_path,
                source_file=source_file,
                test_requirements=file_requirements,
                use_llm=use_llm,
            )

            result = json.loads(result_json)

            if result.get("success"):
                test_code = result.get("test_code", "")
                test_file = result.get("test_file", "")

                if test_code and "@Test" in test_code:
                    test_info = {
                        "path": test_file,
                        "content": test_code,
                        "class_name": result.get("context", {}).get("class_name", ""),
                        "package": result.get("context", {}).get("package", ""),
                        "source_file": source_file,
                        "test_count": result.get("test_count", 0),
                    }
                    generated_tests.append(test_info)
                    logger.info(
                        "test_generated",
                        source_file=source_file,
                        test_file=test_file,
                        test_count=result.get("test_count", 0),
                    )
                else:
                    logger.warning("no_tests_generated", source_file=source_file)
            else:
                logger.warning(
                    "test_generation_failed",
                    source_file=source_file,
                    error=result.get("error"),
                )

        except Exception as e:
            logger.error(
                "test_generation_error",
                source_file=source_file,
                error=str(e),
            )

    logger.info(
        "direct_generation_complete",
        total_source_files=len(source_files),
        tests_generated=len(generated_tests),
    )

    return generated_tests


def _find_source_files(project_path: str) -> list[str]:
    """
    Find Java source files to generate tests for.

    Filters out test files, DTOs, entities, configuration, and other non-testable classes.

    Args:
        project_path: Path to the Java project root

    Returns:
        List of relative paths to source files
    """
    project_dir = Path(project_path)
    source_files = []

    # Patterns to include (testable classes)
    include_patterns = [
        "**/web/**/*.java",  # Controllers, resources
        "**/controller/**/*.java",
        "**/service/**/*.java",
        "**/application/**/*.java",
        "**/api/**/*.java",
    ]

    # Patterns to exclude
    exclude_patterns = [
        "**/test/**",  # Test files
        "**/model/**",  # Entities, DTOs
        "**/entity/**",
        "**/dto/**",
        "**/config/**",  # Configuration
        "**/configuration/**",
        "**/mapper/**",  # Mappers (usually simple)
        "**/*Application.java",  # Main classes
        "**/*Config.java",
        "**/*Configuration.java",
        "**/*Request.java",  # Request/Response DTOs
        "**/*Response.java",
        "**/*DTO.java",
        "**/*Exception.java",  # Exceptions
    ]

    # Find all Java files in src/main/java
    main_java_dirs = list(project_dir.glob("**/src/main/java"))

    for main_java_dir in main_java_dirs:
        for pattern in include_patterns:
            for source_file in main_java_dir.glob(pattern):
                # Check if file should be excluded
                relative_path = str(source_file.relative_to(project_dir))
                should_exclude = False

                for exclude in exclude_patterns:
                    # Simple pattern matching
                    exclude_name = exclude.replace("**/*", "").replace("**", "")
                    if exclude_name in relative_path or source_file.name.endswith(exclude_name.replace("*", "")):
                        should_exclude = True
                        break

                if not should_exclude and relative_path not in source_files:
                    source_files.append(relative_path)

    logger.info("source_files_found", count=len(source_files), project_path=project_path)
    return source_files


async def _generate_tests_directly(
    project_path: str,
    source_files: list[str],
    test_requirements: list[TestRequirement] | None = None,
) -> list[dict[str, Any]]:
    """
    Generate tests directly by calling the generator tool for each source file.

    This bypasses the LLM agent and calls the generator directly, which produces
    more reliable results than asking the LLM to use tools.

    Args:
        project_path: Path to the Java project
        source_files: List of source files to generate tests for
        test_requirements: Optional test requirements from impact analysis

    Returns:
        List of generated test info dicts
    """
    generated_tests = []

    # Convert test requirements to dict format
    requirements_by_file: dict[str, list[dict[str, Any]]] = {}
    if test_requirements:
        for req in test_requirements:
            # Match requirement to source file by class name
            for source_file in source_files:
                if req.target_class and req.target_class in source_file:
                    if source_file not in requirements_by_file:
                        requirements_by_file[source_file] = []
                    requirements_by_file[source_file].append({
                        "suggested_test_name": req.suggested_test_name,
                        "description": req.description,
                        "scenario_type": req.scenario_type.value if req.scenario_type else "nominal",
                        "target_method": req.target_method,
                    })

    for source_file in source_files:
        logger.info("generating_tests_for_file", source_file=source_file)

        try:
            # Get requirements for this file if any
            file_requirements = requirements_by_file.get(source_file)

            # Call generator directly
            result_json = await generate_adaptive_tests(
                project_path=project_path,
                source_file=source_file,
                test_requirements=file_requirements,
            )

            result = json.loads(result_json)

            if result.get("success"):
                test_code = result.get("test_code", "")
                test_file = result.get("test_file", "")

                if test_code and "@Test" in test_code:
                    test_info = {
                        "path": test_file,
                        "content": test_code,
                        "class_name": result.get("context", {}).get("class_name", ""),
                        "package": result.get("context", {}).get("package", ""),
                        "source_file": source_file,
                        "test_count": result.get("test_count", 0),
                    }
                    generated_tests.append(test_info)
                    logger.info(
                        "test_generated",
                        source_file=source_file,
                        test_file=test_file,
                        test_count=result.get("test_count", 0),
                    )
                else:
                    logger.warning("no_tests_generated", source_file=source_file)
            else:
                logger.warning(
                    "test_generation_failed",
                    source_file=source_file,
                    error=result.get("error"),
                )

        except Exception as e:
            logger.error(
                "test_generation_error",
                source_file=source_file,
                error=str(e),
            )

    logger.info(
        "direct_generation_complete",
        total_source_files=len(source_files),
        tests_generated=len(generated_tests),
    )

    return generated_tests


async def run_test_generation_with_agent(
    session_id: UUID,
    project_path: str,
    db_session: Any,
    source_files: list[str] | None = None,
    coverage_target: float = 80.0,
    test_requirements: list[TestRequirement] | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    Run test generation workflow.

    Two modes:
    - LLM mode (use_llm=True, default): Uses LLM for intelligent test generation
    - Template mode (use_llm=False): Uses templates for CI without LLM access

    Implements:
    - T054-T055: Agent creation with create_deep_agent()
    - T056-T057: Load config from YAML and prompts from Markdown
    - T058-T059: Bind MCP tools and invoke with retry logic
    - T060: Auto-correction retry for compilation errors
    - T061: Store agent reasoning and tool calls in artifacts
    - T064: LangSmith tracing validation

    Args:
        session_id: Workflow session UUID
        project_path: Path to Java project
        db_session: SQLAlchemy async session for artifact storage
        source_files: Optional list of specific source files to test
        coverage_target: Target code coverage percentage
        test_requirements: Optional test requirements from impact analysis
        use_llm: If True (default), use LLM for intelligent test generation.
                 If False, use template-based generation (for CI without LLM).

    Returns:
        dict with workflow results including generated tests and metrics

    Raises:
        TestGenerationError: If generation fails after retries
        LLMError: If LLM connection issues persist (only in LLM mode)
    """
    start_time = time.time()
    generation_mode = "llm" if use_llm else "template"
    logger.info(
        "test_gen_workflow_start",
        session_id=str(session_id),
        project_path=project_path,
        coverage_target=coverage_target,
        generation_mode=generation_mode,
    )

    # Initialize repositories
    session_repo = SessionRepository(db_session)
    artifact_repo = ArtifactRepository(db_session)

    # Load agent configuration (T056)
    loader = AgentLoader("config/agents")
    config = loader.load_agent("test_gen_agent")
    logger.info("agent_config_loaded", agent_name=config.name, model=config.llm.model)

    # Load system prompt (T057)
    prompt = loader.load_prompt("unit_test_strategy", category="testing")
    logger.info("system_prompt_loaded", category="testing")

    # Get MCP tools from registry (T058)
    tools = get_tools_for_servers(config.tools.mcp_servers)
    logger.info("mcp_tools_loaded", server_count=len(config.tools.mcp_servers), tool_count=len(tools))

    # Get LLM instance (T055)
    llm = get_llm(
        provider=config.llm.provider,
        model=config.llm.model,
        temperature=config.llm.temperature,
        max_tokens=config.llm.max_tokens,
        timeout=config.error_handling.timeout_seconds,
    )

    # Create LangGraph ReAct agent
    # Note: create_react_agent handles tool binding internally - don't call bind_tools separately
    # as it can cause infinite loops (agent always calls tools without stopping)
    logger.info("creating_react_agent", tool_count=len(tools))

    agent = create_react_agent(
        model=llm,
        tools=tools,
        prompt=prompt,
        # Note: PostgreSQL checkpointer would be shared here if implementing pause/resume
        # checkpointer=postgres_checkpointer
    )
    logger.info("react_agent_created", agent_type="test_generation")

    try:
        # ===== DIRECT TEST GENERATION (bypasses unreliable LLM tool calling) =====
        # Instead of asking the LLM to call tools (which often produces placeholder tests),
        # we call the generator directly for each source file.

        # Step 1: Discover source files if not provided
        if not source_files:
            source_files = _find_source_files(project_path)

        if not source_files:
            logger.warning("no_source_files_found", project_path=project_path)
            return {
                "success": False,
                "generated_tests": [],
                "metrics": {"duration_seconds": 0, "tests_generated": 0},
                "agent_name": config.name,
                "error": "No testable source files found in project",
            }

        logger.info(
            "starting_direct_generation",
            source_file_count=len(source_files),
            has_requirements=bool(test_requirements),
        )

        # Step 2: Generate tests for each source file (LLM or template mode)
        generated_tests = await _generate_tests_directly(
            project_path=project_path,
            source_files=source_files,
            test_requirements=test_requirements,
            use_llm=use_llm,
        )

        if not generated_tests:
            logger.warning("no_tests_generated", project_path=project_path)
            return {
                "success": False,
                "generated_tests": [],
                "metrics": {"duration_seconds": time.time() - start_time, "tests_generated": 0},
                "agent_name": config.name,
                "error": "No tests could be generated for the source files",
            }

        # Step 3: Validate tests (basic syntax check)
        validated_tests = []
        for test in generated_tests:
            syntax_result = _check_test_syntax(test.get("content", ""))
            test["compiles"] = syntax_result["success"]
            test["compilation_errors"] = syntax_result.get("errors", [])
            test["correction_attempts"] = 0
            validated_tests.append(test)

        logger.info(
            "direct_generation_complete",
            tests_generated=len(validated_tests),
            compilable=sum(1 for t in validated_tests if t.get("compiles")),
        )

        # Write validated tests to disk (also sets written_to_disk flag on each test)
        _write_tests_to_disk(project_path, validated_tests)

        # Run test feedback loop - execute tests and fix until passing
        feedback_result = await _run_test_feedback_loop(
            session_id=session_id,
            artifact_repo=artifact_repo,
            agent=agent,
            validated_tests=validated_tests,
            project_path=project_path,
        )

        # Calculate metrics
        duration = time.time() - start_time
        metrics = {
            "duration_seconds": round(duration, 2),
            "tests_generated": len(validated_tests),
            "compilation_success": all(t.get("compiles", False) for t in validated_tests),
            "coverage_target": coverage_target,
            "tests_passing": feedback_result.get("success", False),
            "feedback_iterations": feedback_result.get("iterations", 0),
            "generation_mode": "llm" if use_llm else "template",
            "source_files_processed": len(source_files),
        }

        # Store metrics (without LLM response since we used direct generation)
        await _store_generation_metrics(
            session_id=session_id,
            artifact_repo=artifact_repo,
            metrics=metrics,
        )

        logger.info(
            "test_gen_workflow_complete",
            session_id=str(session_id),
            tests_generated=len(validated_tests),
            duration_seconds=metrics["duration_seconds"],
        )

        return {
            "success": True,
            "generated_tests": validated_tests,
            "metrics": metrics,
            "agent_name": config.name,
            "feedback_result": feedback_result,
        }

    except Exception as e:
        logger.error(
            "test_gen_workflow_failed",
            session_id=str(session_id),
            error=str(e),
            error_type=type(e).__name__,
        )
        # Store error in session
        await session_repo.update(session_id, status="failed", error_message=str(e))
        raise TestGenerationError(f"Test generation failed: {e}") from e


async def _invoke_agent_and_store_tools(
    agent: Any,
    input_data: dict[str, Any],
    session_id: UUID,
    artifact_repo: ArtifactRepository,
) -> dict[str, Any] | AIMessage:
    """
    Invoke agent and store tool calls as artifacts.

    Uses shared retry logic from agent_retry module.

    Args:
        agent: LangGraph agent instance
        input_data: Input messages and context
        session_id: Session UUID for artifact storage
        artifact_repo: Repository for storing tool calls

    Returns:
        Agent response (dict for LangGraph final state or AIMessage for single LLM call)
    """
    logger.debug("agent_invoke_start", session_id=str(session_id))

    # Use shared retry utility
    messages = input_data.get("messages", [])
    response = await invoke_agent_with_retry(
        agent=agent,
        input_data=messages,
        max_retries=MAX_CORRECTION_RETRIES,
    )

    # Store tool calls from response
    if hasattr(response, "tool_calls") and response.tool_calls:
        await _store_tool_calls(session_id, artifact_repo, response.tool_calls)

    logger.debug("agent_invoke_success", session_id=str(session_id))
    return response


async def _validate_and_correct_tests(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    agent: Any,
    generated_tests: list[dict[str, Any]],
    project_path: str,
) -> list[dict[str, Any]]:
    """
    Validate generated tests and retry with auto-correction if compilation fails (T060, A2).

    Args:
        session_id: Session UUID
        artifact_repo: Artifact repository
        agent: DeepAgents agent for corrections
        generated_tests: List of generated test files
        project_path: Java project path

    Returns:
        List of validated test files with compilation status
    """
    validated = []

    for test_file in generated_tests:
        test_path = test_file.get("path")
        test_content = test_file.get("content")

        if not test_path or not test_content:
            logger.warning("invalid_test_file", test_file=test_file)
            continue

        # Try to compile with retries
        compilation_result = await _compile_with_auto_correction(
            session_id=session_id,
            artifact_repo=artifact_repo,
            agent=agent,
            test_path=test_path,
            test_content=test_content,
            project_path=project_path,
        )

        validated.append(
            {
                "path": test_path,
                "content": compilation_result.get("corrected_content", test_content),
                "compiles": compilation_result.get("success", False),
                "compilation_errors": compilation_result.get("errors", []),
                "correction_attempts": compilation_result.get("attempts", 0),
            }
        )

    return validated


async def _compile_with_auto_correction(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    agent: Any,
    test_path: str,
    test_content: str,
    project_path: str,
    max_attempts: int = MAX_CORRECTION_RETRIES,
) -> dict[str, Any]:
    """
    Attempt to compile test with auto-correction retries (T060, A2 edge case).

    Args:
        session_id: Session UUID
        artifact_repo: Artifact repository
        agent: DeepAgents agent
        test_path: Test file path
        test_content: Test file content
        project_path: Java project path
        max_attempts: Maximum correction attempts

    Returns:
        dict with compilation results and corrected content
    """
    current_content = test_content
    errors = []

    for attempt in range(1, max_attempts + 1):
        logger.info("test_compilation_attempt", test_path=test_path, attempt=attempt)

        # Simulate compilation check (in real implementation, would call Maven/Gradle)
        # For now, basic syntax validation
        compilation_result = _check_test_syntax(current_content)

        if compilation_result["success"]:
            logger.info("test_compilation_success", test_path=test_path, attempt=attempt)
            return {
                "success": True,
                "corrected_content": current_content,
                "attempts": attempt,
            }

        # Store compilation errors
        errors = compilation_result.get("errors", [])
        logger.warning("test_compilation_failed", test_path=test_path, attempt=attempt, errors=errors)

        # Store compilation error artifact
        await artifact_repo.create(
            session_id=session_id,
            name=f"compilation_error_{Path(test_path).stem}_attempt_{attempt}",
            artifact_type="compilation_error",
            content_type="application/json",
            file_path=f"artifacts/{session_id}/compilation_errors/{Path(test_path).stem}_{attempt}.json",
            size_bytes=len(json.dumps(errors)),
        )

        # If max attempts reached, return failure
        if attempt >= max_attempts:
            logger.error("test_compilation_max_retries", test_path=test_path, max_attempts=max_attempts)
            return {
                "success": False,
                "corrected_content": current_content,
                "errors": errors,
                "attempts": attempt,
            }

        # Ask agent to correct errors
        correction_prompt = f"""The following test has compilation errors:

File: {test_path}

Errors:
{json.dumps(errors, indent=2)}

Current content:
```java
{current_content}
```

Please fix these compilation errors while maintaining test logic and coverage."""

        correction_response = await _invoke_agent_and_store_tools(
            agent=agent,
            input_data={"messages": [HumanMessage(content=correction_prompt)]},
            session_id=session_id,
            artifact_repo=artifact_repo,
        )

        # Extract corrected content from response
        # Handle both dict (LangGraph state) and AIMessage responses
        if isinstance(correction_response, dict):
            messages = correction_response.get("messages", [])
            if messages:
                last_message = messages[-1]
                response_content = last_message.content if hasattr(last_message, "content") else str(last_message)
            else:
                response_content = str(correction_response)
        else:
            response_content = correction_response.content

        corrected = _extract_code_from_response(response_content)
        if corrected:
            current_content = corrected

    return {
        "success": False,
        "corrected_content": current_content,
        "errors": errors,
        "attempts": max_attempts,
    }


def _check_test_syntax(test_content: str) -> dict[str, Any]:
    """
    Basic syntax validation for Java test files.

    In production, this would call Maven/Gradle to compile.
    For now, checks basic Java syntax patterns.

    Args:
        test_content: Java test content

    Returns:
        dict with success flag and errors
    """
    errors = []

    # Basic checks
    if "class" not in test_content:
        errors.append({"line": 0, "message": "Missing class declaration"})
    if "@Test" not in test_content and "@ParameterizedTest" not in test_content:
        errors.append({"line": 0, "message": "No test methods found"})

    # Check for balanced braces
    if test_content.count("{") != test_content.count("}"):
        errors.append({"line": 0, "message": "Unbalanced braces"})

    return {"success": len(errors) == 0, "errors": errors}


def _extract_generated_tests(
    response: dict[str, Any] | AIMessage,
    existing_tests: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Extract generated test files from agent response.

    Handles various agent response formats including:
    1. ```java code blocks (case-insensitive: ```java, ```Java, ```JAVA)
    2. Plain ``` code blocks containing Java class definitions
    3. JSON tool results containing 'test_code' field
    4. Raw Java code without markdown blocks (fallback)
    5. All messages in the conversation history

    For multi-module projects, existing_tests can be passed to preserve
    the actual_path (with module prefix) when extracting corrected tests.

    Args:
        response: Agent response as dict with 'messages' key or AIMessage
        existing_tests: Optional list of existing test dicts with actual_path.
                       Used to match corrected tests to their original paths.

    Returns:
        List of test info dicts with path, content, class_name, package
    """
    tests = []
    all_content = []

    # Extract content from response (handle both dict and AIMessage)
    if isinstance(response, dict):
        # LangGraph returns final state as dict with 'messages' key
        messages = response.get("messages", [])
        for msg in messages:
            if hasattr(msg, "content"):
                msg_content = msg.content if isinstance(msg.content, str) else str(msg.content)
                all_content.append(msg_content)
            elif isinstance(msg, str):
                all_content.append(msg)
    else:
        # Direct AIMessage response
        content = response.content if isinstance(response.content, str) else str(response.content)
        all_content.append(content)

    # Process all collected content
    for content in all_content:
        extracted_codes = []

        # Strategy 1: Look for Java code blocks (case-insensitive)
        # Matches: ```java, ```Java, ```JAVA, ``` java (with space)
        java_block_pattern = r'```[jJ][aA][vV][aA]\s*\n(.*?)```'
        for match in re.finditer(java_block_pattern, content, re.DOTALL):
            code = match.group(1).strip()
            if code:
                extracted_codes.append(code)

        # Strategy 2: Look for plain code blocks that contain Java class definitions
        # Only if no java-specific blocks were found
        if not extracted_codes:
            plain_block_pattern = r'```\s*\n(.*?)```'
            for match in re.finditer(plain_block_pattern, content, re.DOTALL):
                code = match.group(1).strip()
                # Check if this looks like Java code (has class definition)
                if code and ("public class " in code or "class " in code) and "@Test" in code:
                    extracted_codes.append(code)

        # Strategy 3: Look for JSON tool results with test_code
        if '"test_code"' in content or "'test_code'" in content:
            try:
                # Try to find and parse JSON objects in the content
                json_pattern = r'\{[^{}]*"test_code"[^{}]*\}'
                for match in re.finditer(json_pattern, content, re.DOTALL):
                    try:
                        data = json.loads(match.group())
                        if data.get("test_code"):
                            code = data["test_code"]
                            test_info = _extract_test_info(code, existing_tests)
                            if test_info and test_info not in tests:
                                # Use file path from tool result if available
                                if data.get("test_file"):
                                    test_info["path"] = data["test_file"]
                                tests.append(test_info)
                    except json.JSONDecodeError:
                        # Expected for partial JSON matches, skip silently
                        continue
            except Exception as e:
                logger.debug("test_extraction_json_error", error=str(e), content_length=len(content))

        # Strategy 4: Fallback - look for raw Java code without markdown blocks
        # Only if no code blocks found and content has Java patterns
        if not extracted_codes and "class " in content and "@Test" in content:
            # Try to extract Java class definition from raw content
            raw_code = _extract_java_class_from_raw_content(content)
            if raw_code:
                extracted_codes.append(raw_code)

        # Validate and add extracted codes
        for code in extracted_codes:
            if _is_valid_test_code(code):
                test_info = _extract_test_info(code, existing_tests)
                if test_info and test_info not in tests:
                    tests.append(test_info)

    logger.debug("extracted_tests", count=len(tests))
    return tests


def _extract_java_class_from_raw_content(content: str) -> str | None:
    """Extract Java class definition from raw content without markdown blocks.

    Attempts to find Java code by looking for package/import/class patterns.

    Args:
        content: Raw text content that may contain Java code

    Returns:
        Extracted Java code or None if not found
    """
    lines = content.split("\n")
    java_lines = []
    in_class = False
    brace_count = 0

    for line in lines:
        stripped = line.strip()

        # Start capturing at package, import, or class declaration
        if not in_class:
            if stripped.startswith("package ") or stripped.startswith("import ") or "class " in stripped:
                in_class = True

        if in_class:
            java_lines.append(line)
            brace_count += line.count("{") - line.count("}")

            # Stop when we've closed all braces after opening the class
            if brace_count == 0 and len(java_lines) > 1 and any("{" in l for l in java_lines):
                break

    if java_lines:
        code = "\n".join(java_lines).strip()
        # Verify it's actually valid Java test code
        if "class " in code and "@Test" in code:
            return code

    return None


def _is_valid_test_code(code: str) -> bool:
    """Check if code is valid Java test code.

    Validates that code contains essential Java test elements:
    - A class declaration
    - At least one test annotation (@Test or @ParameterizedTest)
    - Balanced braces (basic syntax check)

    Args:
        code: Java source code to validate

    Returns:
        True if code appears to be valid Java test code
    """
    if not code or not isinstance(code, str):
        logger.warning("validation_failed", reason="empty_or_invalid_input", code_type=type(code).__name__)
        return False

    # Must have a class declaration
    has_class = "class " in code
    if not has_class:
        logger.warning("validation_failed", reason="no_class_declaration", code_preview=code[:100] if len(code) > 100 else code)
        return False

    # Must have at least one test annotation
    has_test = "@Test" in code or "@ParameterizedTest" in code
    if not has_test:
        logger.warning("validation_failed", reason="no_test_annotation", code_preview=code[:100] if len(code) > 100 else code)
        return False

    # Basic sanity check: code should have some minimal structure
    # (at least have opening/closing braces for a class)
    has_structure = "{" in code and "}" in code
    if not has_structure:
        logger.warning("validation_failed", reason="no_brace_structure", code_preview=code[:100] if len(code) > 100 else code)
        return False

    # Check for balanced braces - critical for valid Java syntax
    if not _has_balanced_braces(code):
        logger.warning("validation_failed", reason="unbalanced_braces", code_preview=code[:100] if len(code) > 100 else code)
        return False

    return True


def _has_balanced_braces(code: str) -> bool:
    """Check if braces are balanced in Java code.

    Counts curly braces while ignoring those inside string literals
    and comments to determine if they are balanced.

    Args:
        code: Java source code to check

    Returns:
        True if braces are balanced, False otherwise
    """
    brace_count = 0
    in_string = False
    in_char = False
    in_line_comment = False
    in_block_comment = False
    prev_char = ""

    for i, char in enumerate(code):
        # Handle end of line comment
        if in_line_comment:
            if char == "\n":
                in_line_comment = False
            prev_char = char
            continue

        # Handle block comment
        if in_block_comment:
            if prev_char == "*" and char == "/":
                in_block_comment = False
            prev_char = char
            continue

        # Check for start of comments
        if not in_string and not in_char:
            if prev_char == "/" and char == "/":
                in_line_comment = True
                prev_char = char
                continue
            if prev_char == "/" and char == "*":
                in_block_comment = True
                prev_char = char
                continue

        # Handle string literals
        if char == '"' and not in_char and prev_char != "\\":
            in_string = not in_string
            prev_char = char
            continue

        # Handle char literals
        if char == "'" and not in_string and prev_char != "\\":
            in_char = not in_char
            prev_char = char
            continue

        # Count braces only outside strings, chars, and comments
        if not in_string and not in_char:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                # Early exit: more closing than opening braces
                if brace_count < 0:
                    return False

        prev_char = char

    return brace_count == 0


def _extract_test_info(
    code: str,
    existing_tests: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    """Extract test info from Java code.

    For multi-module projects, this function can match the extracted class name
    against existing tests to preserve their actual_path (which includes module prefix).

    Args:
        code: Java test code to extract info from
        existing_tests: Optional list of existing test dicts with actual_path.
                       Used to match corrected tests to their original paths
                       in multi-module projects.

    Returns:
        dict with path, content, class_name, and package, or None if invalid
    """
    if not code:
        return None

    # Extract class name from code
    class_name = "GeneratedTest"
    package = ""

    for line in code.split("\n"):
        line = line.strip()
        if line.startswith("package ") and ";" in line:
            package = line.replace("package ", "").replace(";", "").strip()
        if "class " in line and "{" in line:
            parts = line.split("class ")[1].split()
            if parts:
                class_name = parts[0].replace("{", "").strip()
            break

    # Try to match against existing tests to preserve multi-module paths
    matched_path = None
    if existing_tests:
        for existing in existing_tests:
            existing_class = existing.get("class_name")
            existing_pkg = existing.get("package")

            # Match by class name and package
            if existing_class == class_name and existing_pkg == package:
                # Use actual_path (with module) if available, otherwise original path
                matched_path = existing.get("actual_path") or existing.get("path")
                logger.debug(
                    "test_path_matched",
                    class_name=class_name,
                    matched_path=matched_path,
                )
                break

            # Fallback: match by class name only if no package in existing
            # (for backward compatibility)
            if existing_class == class_name and not existing_pkg:
                matched_path = existing.get("actual_path") or existing.get("path")
                logger.debug(
                    "test_path_matched_by_class",
                    class_name=class_name,
                    matched_path=matched_path,
                )
                break

    # Build test file path (default for new tests or when no match found)
    if matched_path:
        path = matched_path
    elif package:
        package_path = package.replace(".", "/")
        path = f"src/test/java/{package_path}/{class_name}.java"
    else:
        path = f"src/test/java/{class_name}.java"

    return {
        "path": path,
        "content": code,
        "class_name": class_name,
        "package": package,
    }


def _extract_code_from_response(content: str) -> str | None:
    """Extract Java code from agent response.

    Handles various code block formats:
    - ```java (case-insensitive: java, Java, JAVA)
    - Plain ``` blocks containing Java code
    - Raw Java code without markdown blocks (fallback)

    Args:
        content: Response content that may contain Java code

    Returns:
        Extracted Java code or None if not found
    """
    if not content:
        return None

    # Strategy 1: Look for Java code blocks (case-insensitive)
    java_block_pattern = r'```[jJ][aA][vV][aA]\s*\n(.*?)```'
    match = re.search(java_block_pattern, content, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Strategy 2: Look for plain code blocks with Java content
    plain_block_pattern = r'```\s*\n(.*?)```'
    for match in re.finditer(plain_block_pattern, content, re.DOTALL):
        code = match.group(1).strip()
        # Check if this looks like Java code
        if code and ("class " in code or "public " in code):
            return code

    # Strategy 3: Fallback - try to extract raw Java code
    if "class " in content:
        raw_code = _extract_java_class_from_raw_content(content)
        if raw_code:
            return raw_code

    return None


def _write_tests_to_disk(project_path: str, validated_tests: list[dict[str, Any]]) -> list[str]:
    """
    Write validated tests to the project's src/test/java directory.

    For multi-module Maven projects, detects the correct module directory
    based on the package name and existing module structure.

    Also updates each test dict with:
    - 'actual_path': the full path where the test was written
    - 'written_to_disk': True if successfully written

    Args:
        project_path: Path to the Java project root
        validated_tests: List of validated test files with content

    Returns:
        List of file paths that were successfully written
    """
    written_files = []
    project_dir = Path(project_path)

    # Detect multi-module Maven structure
    modules = _detect_maven_modules(project_dir)

    for test in validated_tests:
        # Only write tests that compiled successfully
        if not test.get("compiles", False):
            logger.warning(
                "skip_writing_failed_test",
                path=test.get("path"),
                reason="compilation_failed",
            )
            test["written_to_disk"] = False
            continue

        content = test.get("content")
        relative_path = test.get("path")

        if not content or not relative_path:
            test["written_to_disk"] = False
            continue

        # For multi-module projects, find the best module for this test
        if modules:
            module_path = _find_best_module_for_test(project_dir, modules, content)
            if module_path:
                # Rewrite path to be within the module
                full_path = module_path / relative_path
            else:
                full_path = project_dir / relative_path
        else:
            full_path = project_dir / relative_path

        try:
            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the test file
            full_path.write_text(content, encoding="utf-8")

            # Update test dict with actual path
            actual_path = str(full_path.relative_to(project_dir))
            test["actual_path"] = actual_path
            test["written_to_disk"] = True

            logger.info(
                "test_written_to_disk",
                path=str(full_path),
                size_bytes=len(content),
            )
            written_files.append(actual_path)

        except Exception as e:
            logger.error(
                "test_write_failed",
                path=str(full_path),
                error=str(e),
            )
            test["written_to_disk"] = False

    logger.info(
        "tests_write_complete",
        total=len(validated_tests),
        written=len(written_files),
    )

    return written_files


def _write_test_file_with_verification(
    file_path: Path,
    content: str,
    max_retries: int = MAX_WRITE_RETRIES,
    retry_delay_base: float = WRITE_RETRY_DELAY_BASE,
) -> dict[str, Any]:
    """
    Write a test file to disk with verification and retry logic.

    Following the retry pattern from agent_retry.py, this function:
    - Writes the file content
    - Reads it back to verify write success
    - Retries with exponential backoff on transient failures
    - Returns detailed result info for logging and tracking

    Args:
        file_path: Full path to write the file
        content: Content to write
        max_retries: Maximum retry attempts
        retry_delay_base: Base delay in seconds for exponential backoff

    Returns:
        dict with:
        - success: bool indicating if write succeeded
        - path: str path that was written
        - size_bytes: int size of content written (if successful)
        - attempts: int number of attempts made
        - error: str error message (if failed)
        - verified: bool indicating if content was verified
    """
    import time

    last_error: str | None = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(
                "test_file_write_attempt",
                path=str(file_path),
                attempt=attempt,
                max_retries=max_retries,
                content_size=len(content),
            )

            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the file
            file_path.write_text(content, encoding="utf-8")

            # Verify write by reading back
            verification_content = file_path.read_text(encoding="utf-8")

            if verification_content != content:
                logger.warning(
                    "test_file_write_verification_mismatch",
                    path=str(file_path),
                    attempt=attempt,
                    expected_size=len(content),
                    actual_size=len(verification_content),
                )
                last_error = "Content verification failed: written content does not match"
                if attempt < max_retries:
                    wait_time = min(retry_delay_base * (2 ** (attempt - 1)), 5.0)
                    time.sleep(wait_time)
                    continue
                return {
                    "success": False,
                    "path": str(file_path),
                    "attempts": attempt,
                    "error": last_error,
                    "verified": False,
                }

            # Success - content verified
            logger.info(
                "test_file_write_success",
                path=str(file_path),
                attempt=attempt,
                size_bytes=len(content),
                verified=True,
            )
            return {
                "success": True,
                "path": str(file_path),
                "size_bytes": len(content),
                "attempts": attempt,
                "verified": True,
            }

        except PermissionError as e:
            # Permission errors are usually not transient - don't retry
            logger.error(
                "test_file_write_permission_error",
                path=str(file_path),
                error=str(e),
            )
            return {
                "success": False,
                "path": str(file_path),
                "attempts": attempt,
                "error": f"Permission denied: {e}",
                "verified": False,
            }

        except OSError as e:
            # OS errors (disk full, etc.) - retry with backoff
            logger.warning(
                "test_file_write_os_error",
                path=str(file_path),
                attempt=attempt,
                error=str(e),
            )
            last_error = f"OS error: {e}"
            if attempt < max_retries:
                wait_time = min(retry_delay_base * (2 ** (attempt - 1)), 5.0)
                time.sleep(wait_time)
                continue
            return {
                "success": False,
                "path": str(file_path),
                "attempts": attempt,
                "error": last_error,
                "verified": False,
            }

        except Exception as e:
            # Unknown error - retry with backoff
            logger.error(
                "test_file_write_error",
                path=str(file_path),
                attempt=attempt,
                error=str(e),
                error_type=type(e).__name__,
            )
            last_error = f"{type(e).__name__}: {e}"
            if attempt < max_retries:
                wait_time = min(retry_delay_base * (2 ** (attempt - 1)), 5.0)
                time.sleep(wait_time)
                continue
            return {
                "success": False,
                "path": str(file_path),
                "attempts": attempt,
                "error": last_error,
                "verified": False,
            }

    # Should not reach here, but handle it gracefully
    return {
        "success": False,
        "path": str(file_path),
        "attempts": max_retries,
        "error": last_error or "Unknown error after max retries",
        "verified": False,
    }


def _detect_maven_modules(project_dir: Path) -> list[Path]:
    """
    Detect Maven module directories in a multi-module project.

    Args:
        project_dir: Root project directory

    Returns:
        List of module directory paths (empty if not multi-module)
    """
    modules: list[Path] = []
    parent_pom = project_dir / "pom.xml"

    if not parent_pom.exists():
        return modules

    # Check if it's a multi-module project by looking for subdirectories with pom.xml
    for subdir in project_dir.iterdir():
        if subdir.is_dir() and (subdir / "pom.xml").exists():
            # Verify it has Java sources
            if (subdir / "src" / "main" / "java").exists():
                modules.append(subdir)

    return modules


def _find_best_module_for_test(
    project_dir: Path,
    modules: list[Path],
    test_content: str,
) -> Path | None:
    """
    Find the best module to place a test based on package and class references.

    Args:
        project_dir: Root project directory
        modules: List of module paths
        test_content: Test file content

    Returns:
        Best matching module path, or None if no match found
    """
    # Extract package from test content
    package_match = re.search(r'package\s+([\w.]+);', test_content)
    if not package_match:
        return None

    package = package_match.group(1)
    package_path = package.replace(".", "/")

    # Extract the class being tested (look for imports or class under test)
    class_under_test = None
    import_match = re.search(r'import\s+([\w.]+\.(\w+));', test_content)
    if import_match:
        class_under_test = import_match.group(1)

    # Find module that has matching source package
    for module in modules:
        src_dir = module / "src" / "main" / "java"
        if (src_dir / package_path).exists():
            return module

        # Also check if the class under test exists in this module
        if class_under_test:
            class_path = class_under_test.replace(".", "/") + ".java"
            if (src_dir / class_path).exists():
                return module

    # Heuristic: match by module name patterns
    for module in modules:
        module_name = module.name.lower()
        # Check common patterns
        if "api" in package.lower() and "api" in module_name:
            return module
        if "customer" in package.lower() and "customer" in module_name:
            return module
        if "vet" in package.lower() and "vet" in module_name:
            return module
        if "visit" in package.lower() and "visit" in module_name:
            return module

    # Default to first module with test directory
    for module in modules:
        if (module / "src" / "test" / "java").exists():
            return module

    return None


async def _store_agent_reasoning(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    response: dict[str, Any] | AIMessage,
    agent_name: str,
) -> None:
    """Store agent reasoning as artifact (T061)."""
    # Extract content from response (handle both dict and AIMessage)
    if isinstance(response, dict):
        # LangGraph returns final state as dict with 'messages' key
        messages = response.get("messages", [])
        if messages:
            last_message = messages[-1]
            content = last_message.content if hasattr(last_message, "content") else str(last_message)
        else:
            content = str(response)
    else:
        # Direct AIMessage response
        content = response.content if isinstance(response.content, str) else str(response.content)

    reasoning_content = {
        "agent": agent_name,
        "reasoning": content,
        "timestamp": time.time(),
    }

    await artifact_repo.create(
        session_id=session_id,
        name=f"agent_reasoning_{agent_name}",
        artifact_type="agent_reasoning",
        content_type="application/json",
        file_path=f"artifacts/{session_id}/reasoning/{agent_name}.json",
        size_bytes=len(json.dumps(reasoning_content)),
    )

    logger.debug("agent_reasoning_stored", session_id=str(session_id))


async def _store_tool_calls(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    tool_calls: list[Any],
) -> None:
    """Store LLM tool calls as artifacts (T061)."""
    for i, tool_call in enumerate(tool_calls):
        tool_content = {
            "tool_name": tool_call.get("name", "unknown"),
            "arguments": tool_call.get("args", {}),
            "timestamp": time.time(),
        }

        await artifact_repo.create(
            session_id=session_id,
            name=f"tool_call_{i}_{tool_content['tool_name']}",
            artifact_type="llm_tool_call",
            content_type="application/json",
            file_path=f"artifacts/{session_id}/tool_calls/call_{i}.json",
            size_bytes=len(json.dumps(tool_content)),
        )

    logger.debug("tool_calls_stored", session_id=str(session_id), count=len(tool_calls))


async def _store_test_file_artifacts(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    validated_tests: list[dict[str, Any]],
    project_path: str,
) -> None:
    """
    Store file_modification artifacts for each generated test file.

    This allows the frontend to discover and display generated test files
    via the /artifacts API endpoint.

    Args:
        session_id: Session UUID
        artifact_repo: Artifact repository
        validated_tests: List of validated test files
        project_path: Project root path
    """
    from src.lib.diff import generate_unified_diff

    for test in validated_tests:
        # Only store artifacts for tests that were written to disk
        if not test.get("written_to_disk", False):
            continue

        file_path = test.get("actual_path") or test.get("path")
        content = test.get("content", "")

        if not file_path or not content:
            continue

        # Generate diff (original is None for new files)
        diff = generate_unified_diff(
            original=None,
            modified=content,
            file_path=file_path,
        )

        # Create artifact metadata
        metadata = {
            "file_path": file_path,
            "operation": "create",
            "original_content": None,
            "modified_content": content,
            "diff": diff,
        }

        # Create artifact
        await artifact_repo.create(
            session_id=session_id,
            name=f"test_file_{Path(file_path).stem}",
            artifact_type="file_modification",
            content_type="text/x-java",
            file_path=f"artifacts/{session_id}/tests/{Path(file_path).name}",
            size_bytes=len(content),
            artifact_metadata=metadata,
        )

    logger.info(
        "test_file_artifacts_stored",
        session_id=str(session_id),
        test_count=sum(1 for t in validated_tests if t.get("written_to_disk", False)),
    )


async def _store_generation_metrics(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    metrics: dict[str, Any],
) -> None:
    """Store direct generation metrics as artifact."""
    metrics_content = {
        **metrics,
        "timestamp": time.time(),
    }

    await artifact_repo.create(
        session_id=session_id,
        name="generation_metrics",
        artifact_type="generation_metrics",
        content_type="application/json",
        file_path=f"artifacts/{session_id}/metrics/generation_metrics.json",
        size_bytes=len(json.dumps(metrics_content)),
    )

    logger.debug("generation_metrics_stored", session_id=str(session_id))


async def _store_llm_metrics(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    metrics: dict[str, Any],
    response: dict[str, Any] | AIMessage,
) -> None:
    """Store LLM metrics as artifact (T061)."""
    # Extract token usage if available
    token_usage = {}
    # Handle both dict (LangGraph state) and AIMessage responses
    if isinstance(response, dict):
        messages = response.get("messages", [])
        if messages:
            last_message = messages[-1]
            if hasattr(last_message, "usage_metadata"):
                token_usage = {
                    "prompt_tokens": getattr(last_message.usage_metadata, "input_tokens", 0),
                    "completion_tokens": getattr(last_message.usage_metadata, "output_tokens", 0),
                    "total_tokens": getattr(last_message.usage_metadata, "total_tokens", 0),
                }
    elif hasattr(response, "usage_metadata"):
        token_usage = {
            "prompt_tokens": getattr(response.usage_metadata, "input_tokens", 0),
            "completion_tokens": getattr(response.usage_metadata, "output_tokens", 0),
            "total_tokens": getattr(response.usage_metadata, "total_tokens", 0),
        }

    metrics_content = {
        **metrics,
        **token_usage,
        "timestamp": time.time(),
    }

    await artifact_repo.create(
        session_id=session_id,
        name="llm_metrics",
        artifact_type="llm_metrics",
        content_type="application/json",
        file_path=f"artifacts/{session_id}/metrics/llm_metrics.json",
        size_bytes=len(json.dumps(metrics_content)),
    )

    logger.debug("llm_metrics_stored", session_id=str(session_id))


async def _run_test_feedback_loop(
    session_id: UUID,
    artifact_repo: ArtifactRepository,
    agent: Any,
    validated_tests: list[dict[str, Any]],
    project_path: str,
    max_iterations: int = MAX_TEST_ITERATIONS,
) -> dict[str, Any]:
    """
    Run tests and iterate with agent corrections until all tests pass.

    This implements a feedback loop:
    1. Run Maven tests
    2. Parse failures
    3. If failures exist, ask agent to fix them
    4. Write corrected tests
    5. Repeat until success or max iterations

    Args:
        session_id: Session UUID
        artifact_repo: Artifact repository
        agent: LangGraph agent for corrections
        validated_tests: List of validated test files
        project_path: Java project path
        max_iterations: Maximum correction iterations

    Returns:
        dict with final test results and iteration count
    """
    # Get the test files that were written
    test_files = [t for t in validated_tests if t.get("written_to_disk")]
    if not test_files:
        logger.warning("no_tests_to_run", session_id=str(session_id))
        return {
            "success": False,
            "iterations": 0,
            "tests": validated_tests,
            "message": "No tests were written to disk",
        }

    project_dir = Path(project_path)
    # Use actual_path (with module) if available, otherwise original path
    current_tests = {
        t.get("actual_path", t["path"]): t["content"]
        for t in validated_tests
    }

    for iteration in range(1, max_iterations + 1):
        logger.info(
            "test_feedback_iteration",
            session_id=str(session_id),
            iteration=iteration,
            max_iterations=max_iterations,
        )

        # Step 1: Run Maven tests
        try:
            test_result = await _run_maven_tests(project_dir, test_files)
        except MavenNotFoundError as e:
            logger.error(
                "maven_not_found_in_feedback_loop",
                session_id=str(session_id),
                error=str(e),
            )
            return {
                "success": False,
                "iterations": iteration,
                "tests": validated_tests,
                "message": f"Maven not found: {e}. Please install Maven and ensure it's in your PATH.",
                "error_type": "maven_not_found",
            }
        except MavenTimeoutError as e:
            logger.error(
                "maven_timeout_in_feedback_loop",
                session_id=str(session_id),
                iteration=iteration,
                timeout=e.timeout_seconds,
                module=e.module,
            )
            return {
                "success": False,
                "iterations": iteration,
                "tests": validated_tests,
                "message": f"Maven tests timed out: {e}. Consider increasing TEST_TIMEOUT_SECONDS or optimizing tests.",
                "error_type": "maven_timeout",
            }

        if test_result["success"]:
            logger.info(
                "test_feedback_success",
                session_id=str(session_id),
                iteration=iteration,
            )
            return {
                "success": True,
                "iterations": iteration,
                "tests": validated_tests,
                "message": f"All tests passed after {iteration} iteration(s)",
            }

        # Step 2: Parse failures
        failures = _parse_test_failures(test_result["output"])

        if not failures:
            # Tests failed but couldn't parse failures - might be compilation issue
            logger.warning(
                "test_failures_unparseable",
                session_id=str(session_id),
                output=test_result["output"][:500],
            )
            failures = [{"error": test_result["output"][:2000], "test": "unknown"}]

        logger.info(
            "test_failures_found",
            session_id=str(session_id),
            failure_count=len(failures),
            iteration=iteration,
        )

        # Store failure artifact
        await artifact_repo.create(
            session_id=session_id,
            name=f"test_failures_iteration_{iteration}",
            artifact_type="test_failure",
            content_type="application/json",
            file_path=f"artifacts/{session_id}/test_failures/iteration_{iteration}.json",
            size_bytes=len(json.dumps(failures)),
        )

        # Step 3: Ask agent to fix failures
        fix_prompt = _build_fix_prompt(failures, current_tests, project_path)

        fix_response = await _invoke_agent_and_store_tools(
            agent=agent,
            input_data={"messages": [HumanMessage(content=fix_prompt)]},
            session_id=session_id,
            artifact_repo=artifact_repo,
        )

        # Step 4: Extract and write corrected tests
        # Pass validated_tests to preserve multi-module paths in corrections
        corrected_tests = _extract_generated_tests(fix_response, validated_tests)

        if not corrected_tests:
            logger.warning(
                "no_corrections_from_agent",
                session_id=str(session_id),
                iteration=iteration,
            )
            continue

        # Update current tests with corrections and write to disk with verification
        corrections_written = 0
        corrections_failed = 0

        for corrected in corrected_tests:
            path = corrected.get("path")
            content = corrected.get("content")
            if not path or not content:
                logger.warning(
                    "correction_missing_data",
                    session_id=str(session_id),
                    iteration=iteration,
                    has_path=bool(path),
                    has_content=bool(content),
                )
                continue

            current_tests[path] = content
            full_path = project_dir / path

            # Write to disk with verification and retry logic
            write_result = _write_test_file_with_verification(full_path, content)

            # Update corrected test dict with write status
            corrected["written_to_disk"] = write_result["success"]
            corrected["write_verified"] = write_result.get("verified", False)
            corrected["actual_path"] = path

            if write_result["success"]:
                corrections_written += 1
                logger.info(
                    "corrected_test_written",
                    session_id=str(session_id),
                    path=str(full_path),
                    iteration=iteration,
                    attempts=write_result["attempts"],
                    verified=write_result["verified"],
                    size_bytes=write_result.get("size_bytes"),
                )

                # Also update the original test in validated_tests if found
                for orig_test in validated_tests:
                    orig_path = orig_test.get("actual_path") or orig_test.get("path")
                    if orig_path == path:
                        orig_test["content"] = content
                        orig_test["corrected_iteration"] = iteration
                        break
            else:
                corrections_failed += 1
                logger.error(
                    "corrected_test_write_failed",
                    session_id=str(session_id),
                    path=path,
                    iteration=iteration,
                    attempts=write_result["attempts"],
                    error=write_result.get("error"),
                )

        # Log summary of corrections for this iteration
        logger.info(
            "correction_write_summary",
            session_id=str(session_id),
            iteration=iteration,
            total_corrections=len(corrected_tests),
            written=corrections_written,
            failed=corrections_failed,
        )

    # Max iterations reached
    logger.warning(
        "test_feedback_max_iterations",
        session_id=str(session_id),
        max_iterations=max_iterations,
    )
    return {
        "success": False,
        "iterations": max_iterations,
        "tests": validated_tests,
        "message": f"Tests still failing after {max_iterations} iterations",
    }


async def _run_maven_tests(
    project_dir: Path,
    test_files: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Run Maven tests on the project.

    For multi-module projects, runs tests in each module that has test files.

    Args:
        project_dir: Path to the Maven project
        test_files: List of test file info dicts

    Returns:
        dict with success flag and output
    """
    # Group tests by module
    tests_by_module: dict[str, list[str]] = {}
    for test_file in test_files:
        # Use actual_path which includes module directory
        path = test_file.get("actual_path", test_file.get("path", ""))
        if not path.endswith(".java"):
            continue

        class_name = Path(path).stem

        # Check if path includes a module directory
        parts = Path(path).parts
        if len(parts) > 1 and (project_dir / parts[0] / "pom.xml").exists():
            module = parts[0]
        else:
            module = ""

        if module not in tests_by_module:
            tests_by_module[module] = []
        tests_by_module[module].append(class_name)

    if not tests_by_module:
        return {
            "success": False,
            "output": "No test files found",
            "return_code": -1,
        }

    all_output = []
    all_success = True

    # Run tests for each module
    for module, test_classes in tests_by_module.items():
        if module:
            # Multi-module: run in specific module
            pom_path = project_dir / module / "pom.xml"
            cwd = project_dir / module
        else:
            # Single module: run in project root
            pom_path = project_dir / "pom.xml"
            cwd = project_dir

        if not pom_path.exists():
            all_output.append(f"No pom.xml found for module {module or 'root'}")
            continue

        # Build Maven command
        # Use absolute paths with forward slashes for cross-platform compatibility
        mvn_cmd = ["mvn", "test", "-f", pom_path.resolve().as_posix()]

        # Add specific test classes
        if test_classes:
            test_pattern = ",".join(test_classes)
            mvn_cmd.extend(["-Dtest=" + test_pattern, "-DfailIfNoTests=false"])

        logger.info(
            "running_maven_tests",
            module=module or "root",
            command=" ".join(mvn_cmd),
        )

        try:
            # Platform-specific subprocess handling:
            # - Windows: shell=True requires string command (not list)
            # - Unix/Mac: shell=False with list is more secure
            is_windows = platform.system() == "Windows"
            if is_windows:
                # On Windows, convert list to string for shell=True
                cmd = " ".join(mvn_cmd)
                result = subprocess.run(
                    cmd,
                    cwd=str(cwd.resolve()),
                    capture_output=True,
                    text=True,
                    timeout=TEST_TIMEOUT_SECONDS,
                    shell=True,
                )
            else:
                # On Unix/Mac, use list with shell=False (more secure)
                result = subprocess.run(
                    mvn_cmd,
                    cwd=str(cwd.resolve()),
                    capture_output=True,
                    text=True,
                    timeout=TEST_TIMEOUT_SECONDS,
                    shell=False,
                )

            output = result.stdout + "\n" + result.stderr
            all_output.append(f"=== Module: {module or 'root'} ===\n{output}")

            if result.returncode != 0:
                all_success = False

            logger.info(
                "maven_tests_complete",
                module=module or "root",
                success=result.returncode == 0,
                return_code=result.returncode,
            )

        except subprocess.TimeoutExpired as e:
            logger.error(
                "maven_tests_timeout",
                module=module or "root",
                timeout=TEST_TIMEOUT_SECONDS,
                command=" ".join(mvn_cmd),
            )
            # Raise specific timeout error for proper handling upstream
            raise MavenTimeoutError(
                message="Maven test execution timed out",
                timeout_seconds=TEST_TIMEOUT_SECONDS,
                module=module or "root",
            ) from e

        except FileNotFoundError as e:
            # Maven executable not found in PATH
            logger.error(
                "maven_not_found",
                module=module or "root",
                command=mvn_cmd[0],
                error=str(e),
            )
            # Check common Maven installation paths
            common_paths = [
                "/usr/bin/mvn",
                "/usr/local/bin/mvn",
                "C:\\Program Files\\Apache\\maven\\bin\\mvn.cmd",
                "C:\\Program Files (x86)\\Apache\\maven\\bin\\mvn.cmd",
            ]
            raise MavenNotFoundError(
                message="Maven executable not found. Ensure Maven is installed and in your PATH",
                search_paths=common_paths,
            ) from e

        except OSError as e:
            # Handle other OS-level errors (permission denied, etc.)
            error_msg = str(e)
            logger.error(
                "maven_execution_os_error",
                module=module or "root",
                error=error_msg,
                error_code=getattr(e, "errno", None),
            )
            # Check if it's a "file not found" variant (errno 2)
            if getattr(e, "errno", None) == 2:
                raise MavenNotFoundError(
                    message=f"Maven executable not found: {error_msg}",
                ) from e
            all_output.append(f"Module {module or 'root'}: OS error - {error_msg}")
            all_success = False

        except Exception as e:
            logger.error(
                "maven_tests_failed",
                module=module or "root",
                error=str(e),
                error_type=type(e).__name__,
            )
            all_output.append(f"Module {module or 'root'}: {str(e)}")
            all_success = False

    return {
        "success": all_success,
        "output": "\n".join(all_output),
        "return_code": 0 if all_success else 1,
    }


def _parse_test_failures(maven_output: str) -> list[dict[str, Any]]:
    """
    Parse Maven test output to extract failure information.

    Args:
        maven_output: Raw Maven test output

    Returns:
        List of failure dicts with test name, error message, and stack trace
    """
    failures = []

    # Pattern for test failures in Maven output
    # Example: "Tests run: 5, Failures: 2, Errors: 1"
    # Example failure block:
    # "Failed tests:
    #   shouldRejectInvalidEmail(com.example.OwnerResourceTest): expected: <400> but was: <500>"

    # Look for failure summary
    # Pattern matches "Failed tests:" or "Tests in error:" followed by indented lines
    # Uses (?:\n|$) to handle both mid-string and end-of-string cases
    failure_pattern = re.compile(
        r"(?:Failed tests?|Tests in error):\s*\n((?:\s+.+(?:\n|$))+)",
        re.MULTILINE
    )

    matches = failure_pattern.findall(maven_output)
    for match in matches:
        # Parse individual failures
        for line in match.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            # Parse format: "methodName(className): error message"
            test_match = re.match(r"(\w+)\(([^)]+)\):\s*(.+)", line)
            if test_match:
                failures.append({
                    "method": test_match.group(1),
                    "class": test_match.group(2),
                    "error": test_match.group(3),
                })
            else:
                # Generic format
                failures.append({"error": line, "test": "unknown"})

    # ===== COMPREHENSIVE COMPILATION ERROR PARSING =====
    # Maven outputs various compilation error formats that need to be parsed

    # Pattern 1: Standard format with line and column [ERROR] /path/Test.java:[10,5] message
    compile_error_pattern_1 = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),(\d+)\]\s*(.+)",
        re.MULTILINE
    )

    for match in compile_error_pattern_1.finditer(maven_output):
        error_msg = match.group(4)
        failure = {
            "type": "compilation",
            "file": match.group(1),
            "line": int(match.group(2)),
            "column": int(match.group(3)),
            "error": error_msg,
        }
        # Categorize JPA-specific errors with fix suggestions
        failure["jpa_error"] = _categorize_jpa_error(error_msg)
        failures.append(failure)

    # Pattern 2: Format without column [ERROR] /path/Test.java:[10] message
    compile_error_pattern_2 = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+)\]\s+(.+)",
        re.MULTILINE
    )

    for match in compile_error_pattern_2.finditer(maven_output):
        # Skip if already captured by pattern 1 (has column)
        file_path = match.group(1)
        line_num = int(match.group(2))
        if any(f.get("file") == file_path and f.get("line") == line_num for f in failures):
            continue
        error_msg = match.group(3)
        failure = {
            "type": "compilation",
            "file": file_path,
            "line": line_num,
            "column": 0,
            "error": error_msg,
        }
        failure["jpa_error"] = _categorize_jpa_error(error_msg)
        failures.append(failure)

    # Pattern 3: Alternative format with colon separator /path/Test.java:10: error: message
    compile_error_pattern_3 = re.compile(
        r"(?:^|\n)\s*(.+\.java):(\d+):\s*(?:error:\s*)?(.+?)(?=\n|$)",
        re.MULTILINE
    )

    for match in compile_error_pattern_3.finditer(maven_output):
        file_path = match.group(1)
        line_num = int(match.group(2))
        # Skip if already captured
        if any(f.get("file") == file_path and f.get("line") == line_num for f in failures):
            continue
        error_msg = match.group(3).strip()
        if error_msg:
            failure = {
                "type": "compilation",
                "file": file_path,
                "line": line_num,
                "column": 0,
                "error": error_msg,
            }
            failure["jpa_error"] = _categorize_jpa_error(error_msg)
            failures.append(failure)

    # Pattern 4: Multi-line errors - capture symbol and location info
    # Example:
    #   [ERROR] /path/Test.java:[10,5] cannot find symbol
    #     symbol:   method setId(long)
    #     location: class com.example.Entity
    multiline_error_pattern = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),?(\d*)\]\s*(cannot find symbol|incompatible types)[^\n]*\n"
        r"(?:\s+symbol:\s*(.+?)\n)?"
        r"(?:\s+location:\s*(.+?)(?:\n|$))?",
        re.MULTILINE
    )

    for match in multiline_error_pattern.finditer(maven_output):
        file_path = match.group(1)
        line_num = int(match.group(2))
        col_num = int(match.group(3)) if match.group(3) else 0

        # Skip if already captured without symbol/location info
        existing = next((f for f in failures if f.get("file") == file_path and f.get("line") == line_num), None)

        error_type = match.group(4)
        symbol = match.group(5).strip() if match.group(5) else None
        location = match.group(6).strip() if match.group(6) else None

        # Build comprehensive error message
        error_msg = error_type
        if symbol:
            error_msg += f" - symbol: {symbol}"
        if location:
            error_msg += f" in {location}"

        if existing:
            # Update existing failure with more details
            existing["error"] = error_msg
            if symbol:
                existing["symbol"] = symbol
            if location:
                existing["location"] = location
            existing["jpa_error"] = _categorize_jpa_error(error_msg)
        else:
            failure = {
                "type": "compilation",
                "file": file_path,
                "line": line_num,
                "column": col_num,
                "error": error_msg,
            }
            if symbol:
                failure["symbol"] = symbol
            if location:
                failure["location"] = location
            failure["jpa_error"] = _categorize_jpa_error(error_msg)
            failures.append(failure)

    # Pattern 5: Package does not exist errors
    package_error_pattern = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),?(\d*)\]\s*package\s+(\S+)\s+does not exist",
        re.MULTILINE
    )

    for match in package_error_pattern.finditer(maven_output):
        file_path = match.group(1)
        line_num = int(match.group(2))
        if any(f.get("file") == file_path and f.get("line") == line_num for f in failures):
            continue
        col_num = int(match.group(3)) if match.group(3) else 0
        package_name = match.group(4)
        failure = {
            "type": "compilation",
            "file": file_path,
            "line": line_num,
            "column": col_num,
            "error": f"package {package_name} does not exist",
            "missing_package": package_name,
            "jpa_error": None,
        }
        failures.append(failure)

    # Pattern 6: Class not found / cannot be resolved errors
    class_not_found_pattern = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),?(\d*)\]\s*(?:cannot find symbol|cannot resolve)\s*[:-]?\s*(?:class|type)?\s*(\w+)",
        re.MULTILINE
    )

    for match in class_not_found_pattern.finditer(maven_output):
        file_path = match.group(1)
        line_num = int(match.group(2))
        if any(f.get("file") == file_path and f.get("line") == line_num for f in failures):
            continue
        col_num = int(match.group(3)) if match.group(3) else 0
        class_name = match.group(4)
        failure = {
            "type": "compilation",
            "file": file_path,
            "line": line_num,
            "column": col_num,
            "error": f"cannot find symbol: class {class_name}",
            "missing_class": class_name,
            "jpa_error": None,
        }
        failures.append(failure)

    # Pattern 7: Maven compiler plugin failure summary
    compiler_failure_pattern = re.compile(
        r"\[ERROR\]\s*COMPILATION ERROR\s*:\s*\n\[INFO\]\s*-+\n((?:\[ERROR\].+\n)+)",
        re.MULTILINE
    )

    for match in compiler_failure_pattern.finditer(maven_output):
        error_block = match.group(1)
        # Parse individual errors within the block
        for error_line in error_block.strip().split("\n"):
            error_line = error_line.replace("[ERROR]", "").strip()
            if error_line and not any(f.get("error") == error_line for f in failures):
                failures.append({
                    "type": "compilation",
                    "error": error_line,
                    "file": "unknown",
                    "line": 0,
                    "column": 0,
                    "jpa_error": _categorize_jpa_error(error_line),
                })

    # ===== JUNIT 5 ASSERTION FAILURE PARSING =====
    # JUnit 5 uses org.opentest4j exceptions with various message formats

    # Pattern for extracting test method from stack trace
    stack_trace_method_pattern = re.compile(
        r"\tat\s+([a-zA-Z_][\w.]*?)\.([a-zA-Z_]\w*)\(([^:]+):(\d+)\)"
    )

    def _extract_test_method_from_trace(output_text: str, start_pos: int) -> dict[str, Any] | None:
        """Extract the first non-JDK test method from stack trace after assertion."""
        # Look for stack trace lines after the assertion
        trace_section = output_text[start_pos:start_pos + 2000]  # Reasonable limit
        matches = stack_trace_method_pattern.findall(trace_section)
        for class_name, method_name, file_name, line_num in matches:
            # Skip JDK internal classes
            if not class_name.startswith(("java.", "sun.", "jdk.", "org.junit.", "org.opentest4j.")):
                return {
                    "class": class_name,
                    "method": method_name,
                    "file": file_name,
                    "line": int(line_num),
                }
        return None

    # Pattern 1: JUnit 5 assertion failures with expected/actual values
    # org.opentest4j.AssertionFailedError: expected: <true> but was: <false>
    # org.opentest4j.AssertionFailedError: custom message ==> expected: <1> but was: <2>
    assertion_expected_actual_pattern = re.compile(
        r"(org\.opentest4j\.\w+|java\.lang\.AssertionError):\s*"
        r"(?:(.+?)\s*==>\s*)?"  # Optional custom message before ==>
        r"expected:\s*<([^>]*)>\s*but was:\s*<([^>]*)>",
        re.DOTALL
    )

    for match in assertion_expected_actual_pattern.finditer(maven_output):
        error_type = match.group(1)
        custom_message = match.group(2).strip() if match.group(2) else None
        expected_value = match.group(3)
        actual_value = match.group(4)

        # Build error message
        error_msg = f"expected: <{expected_value}> but was: <{actual_value}>"
        if custom_message:
            error_msg = f"{custom_message} ==> {error_msg}"

        # Skip if already captured
        if any(f.get("error") == error_msg for f in failures):
            continue

        failure = {
            "type": "assertion",
            "error_type": error_type,
            "error": error_msg,
            "expected": expected_value,
            "actual": actual_value,
        }
        if custom_message:
            failure["custom_message"] = custom_message

        # Try to extract test method from stack trace
        test_method = _extract_test_method_from_trace(maven_output, match.end())
        if test_method:
            failure["test_method"] = test_method

        failures.append(failure)

    # Pattern 2: JUnit 5 null assertion failures
    # org.opentest4j.AssertionFailedError: expected: not <null>
    # org.opentest4j.AssertionFailedError: expected: <null>
    null_assertion_pattern = re.compile(
        r"(org\.opentest4j\.AssertionFailedError):\s*"
        r"expected:\s*(not\s+)?<null>",
        re.DOTALL
    )

    for match in null_assertion_pattern.finditer(maven_output):
        error_type = match.group(1)
        not_null = bool(match.group(2))
        error_msg = f"expected: {'not ' if not_null else ''}<null>"

        # Skip if already captured
        if any(f.get("error") == error_msg for f in failures):
            continue

        failure = {
            "type": "assertion",
            "error_type": error_type,
            "error": error_msg,
            "null_assertion": True,
            "expected_not_null": not_null,
        }

        # Try to extract test method from stack trace
        test_method = _extract_test_method_from_trace(maven_output, match.end())
        if test_method:
            failure["test_method"] = test_method

        failures.append(failure)

    # Pattern 3: JUnit 5 MultipleFailuresError from assertAll
    # org.opentest4j.MultipleFailuresError: Multiple Failures (3 failures)
    multiple_failures_pattern = re.compile(
        r"(org\.opentest4j\.MultipleFailuresError):\s*"
        r"(?:Multiple Failures)?\s*\((\d+)\s*failures?\)",
        re.DOTALL
    )

    for match in multiple_failures_pattern.finditer(maven_output):
        error_type = match.group(1)
        failure_count = int(match.group(2))
        error_msg = f"Multiple Failures ({failure_count} failures)"

        # Skip if already captured
        if any(f.get("error") == error_msg for f in failures):
            continue

        failure = {
            "type": "assertion",
            "error_type": error_type,
            "error": error_msg,
            "multiple_failures": True,
            "failure_count": failure_count,
        }

        # Try to extract test method from stack trace
        test_method = _extract_test_method_from_trace(maven_output, match.end())
        if test_method:
            failure["test_method"] = test_method

        failures.append(failure)

    # Pattern 4: Generic assertion failures (fallback for other formats)
    # org.opentest4j.AssertionFailedError: any message
    # java.lang.AssertionError: any message
    assertion_generic_pattern = re.compile(
        r"(org\.opentest4j\.\w+|java\.lang\.AssertionError):\s*(.+?)(?=\n\tat|\n\n|$)",
        re.DOTALL
    )

    for match in assertion_generic_pattern.finditer(maven_output):
        error_type = match.group(1)
        message = match.group(2).strip()

        # Skip empty messages or already captured
        if not message or any(f.get("error") == message for f in failures):
            continue

        # Skip if this looks like an expected/actual pattern (already handled above)
        if "expected:" in message and "but was:" in message:
            continue

        failure = {
            "type": "assertion",
            "error_type": error_type,
            "error": message,
        }

        # Try to extract test method from stack trace
        test_method = _extract_test_method_from_trace(maven_output, match.end())
        if test_method:
            failure["test_method"] = test_method

        failures.append(failure)

    return failures


def _categorize_jpa_error(error_msg: str) -> dict[str, Any] | None:
    """Categorize JPA/Hibernate-specific errors and provide fix suggestions.

    This helps the feedback loop to intelligently fix common JPA test errors.
    Covers both compilation errors and runtime/test failures related to JPA/Hibernate.

    Categories covered:
    - Compilation errors (missing setId, type mismatches)
    - Hibernate-specific runtime errors (LazyInitializationException, EntityNotFoundException)
    - JPA lifecycle errors (detached entities, transaction issues)
    - Constraint violations
    """
    error_lower = error_msg.lower()

    # ===== COMPILATION ERRORS =====

    # Pattern 1: setId() on @GeneratedValue field
    if "cannot find symbol" in error_lower and "setid" in error_lower:
        return {
            "category": "generated_value_setid",
            "description": "Attempting to call setId() on a JPA entity with @GeneratedValue",
            "fix": "Use ReflectionTestUtils.setField(entity, \"id\", value) instead of entity.setId(value)",
            "import_needed": "org.springframework.test.util.ReflectionTestUtils",
        }

    # Pattern 2: Type mismatch Long vs Integer
    if "incompatible types" in error_lower and ("long" in error_lower or "integer" in error_lower):
        return {
            "category": "id_type_mismatch",
            "description": "Type mismatch between Long and Integer for ID field",
            "fix": "Use 1L for Long IDs, use 1 for Integer IDs. Check the entity's getId() return type.",
        }

    # Pattern 3: Optional misuse - calling method on Optional directly
    if "cannot find symbol" in error_lower and "optional" in error_lower:
        return {
            "category": "optional_misuse",
            "description": "Calling entity method directly on Optional<Entity> instead of extracted value",
            "fix": "Use optional.get().getProperty() or assertThat(optional).isPresent() then extract",
        }

    # Pattern 4: Date type mismatch
    if ("incompatible types" in error_lower or "cannot find symbol" in error_lower) and \
       ("date" in error_lower or "localdate" in error_lower):
        return {
            "category": "date_type_mismatch",
            "description": "Using wrong date type (java.util.Date vs java.time.LocalDate)",
            "fix": "Check entity field type: use new Date() for java.util.Date, LocalDate.of() for LocalDate",
        }

    # Pattern 5: Duplicate class
    if "duplicate class" in error_lower:
        return {
            "category": "duplicate_class",
            "description": "Two test classes with the same name exist",
            "fix": "Delete one of the duplicate test files",
        }

    # Pattern 6: Ambiguous method reference (assertEquals with Long)
    if "ambiguous" in error_lower and "assertequals" in error_lower:
        return {
            "category": "ambiguous_assertion",
            "description": "Ambiguous assertEquals call with boxed types",
            "fix": "Use AssertJ assertThat(actual).isEqualTo(expected) instead of assertEquals",
        }

    # ===== HIBERNATE/JPA RUNTIME ERRORS =====

    # Pattern 7: LazyInitializationException - accessing lazy collection outside session
    if "lazyinitializationexception" in error_lower or \
       ("could not initialize proxy" in error_lower and "no session" in error_lower) or \
       ("failed to lazily initialize" in error_lower):
        return {
            "category": "lazy_initialization",
            "description": "Accessing a lazy-loaded collection or proxy outside of an active Hibernate session",
            "fix": "Either: (1) Add @Transactional to the test method, (2) Use FetchType.EAGER on the relationship, "
                   "(3) Use Hibernate.initialize() before the session closes, or (4) Use JOIN FETCH in your query",
            "import_needed": "org.springframework.transaction.annotation.Transactional",
        }

    # Pattern 8: EntityNotFoundException - entity not found by ID
    if "entitynotfoundexception" in error_lower or \
       ("unable to find" in error_lower and "with id" in error_lower) or \
       ("no entity found for query" in error_lower):
        return {
            "category": "entity_not_found",
            "description": "JPA could not find an entity with the specified identifier",
            "fix": "Ensure the test data is properly set up before querying. "
                   "Use @BeforeEach to insert test entities, or mock the repository method to return test data.",
        }

    # Pattern 9: Detached entity passed to persist
    if "detached entity passed to persist" in error_lower or \
       ("detachedentitypassedtopersist" in error_lower.replace(" ", "")):
        return {
            "category": "detached_entity_persist",
            "description": "Attempting to persist an entity that is already detached from the persistence context",
            "fix": "Use merge() instead of persist() for detached entities, "
                   "or ensure the entity is new (without ID) before calling persist().",
        }

    # Pattern 10: Transaction required exception
    if "transactionrequiredexception" in error_lower or \
       ("no transaction is in progress" in error_lower) or \
       ("transaction required" in error_lower):
        return {
            "category": "transaction_required",
            "description": "A database operation was attempted without an active transaction",
            "fix": "Add @Transactional annotation to the test method or test class. "
                   "For Spring tests, ensure @DataJpaTest or @SpringBootTest is used.",
            "import_needed": "org.springframework.transaction.annotation.Transactional",
        }

    # Pattern 11: EntityManager closed/not open
    if ("entitymanager is closed" in error_lower) or \
       ("session is closed" in error_lower) or \
       ("session/entitymanager is closed" in error_lower.replace(" ", "")):
        return {
            "category": "session_closed",
            "description": "Attempting to use EntityManager/Session after it has been closed",
            "fix": "Ensure all database operations complete before the session closes. "
                   "Use @Transactional on the test or access data within the same transaction.",
        }

    # Pattern 12: Object references an unsaved transient instance
    if "object references an unsaved transient instance" in error_lower or \
       "transientobjectexception" in error_lower:
        return {
            "category": "unsaved_transient",
            "description": "An entity references another entity that has not been persisted yet",
            "fix": "Either: (1) Persist the referenced entity first, (2) Add CascadeType.PERSIST to the relationship, "
                   "or (3) Set the referenced entity's ID if it already exists in the database.",
        }

    # Pattern 13: Constraint violation (unique, foreign key, not null)
    if "constraintviolationexception" in error_lower or \
       "dataintegrity" in error_lower or \
       "unique constraint" in error_lower or \
       "foreign key constraint" in error_lower or \
       "not-null property" in error_lower:
        return {
            "category": "constraint_violation",
            "description": "A database constraint was violated (unique, foreign key, or not null)",
            "fix": "Check test data for: (1) duplicate unique values, (2) missing required fields, "
                   "(3) invalid foreign key references. Use unique test data for each test.",
        }

    # Pattern 14: PropertyNotFoundException - wrong property/field name in query
    if "propertynotfoundexception" in error_lower or \
       ("could not resolve property" in error_lower) or \
       ("unknown property" in error_lower):
        return {
            "category": "property_not_found",
            "description": "A property name used in a query does not exist on the entity",
            "fix": "Verify the property name matches the entity field name exactly (case-sensitive). "
                   "Check for typos or renamed fields.",
        }

    # Pattern 15: PersistenceException generic wrapper
    if "persistenceexception" in error_lower and "caused by" in error_lower:
        return {
            "category": "persistence_exception",
            "description": "A JPA persistence operation failed (wrapper exception)",
            "fix": "Check the nested 'Caused by' exception for the root cause. "
                   "Common causes: missing entity mapping, constraint violation, or connection issue.",
        }

    # Pattern 16: StaleObjectStateException - optimistic locking failure
    if "staleobjectstateexception" in error_lower or \
       "optimisticlock" in error_lower or \
       ("row was updated or deleted by another transaction" in error_lower):
        return {
            "category": "optimistic_lock_failure",
            "description": "Optimistic locking failed - the entity was modified by another transaction",
            "fix": "In tests, ensure no concurrent modifications. Refresh the entity before updating, "
                   "or use @Version field with proper handling.",
        }

    # Pattern 17: Missing @Entity or @Id annotation hints
    if ("unknown entity" in error_lower) or \
       ("not an entity" in error_lower) or \
       ("no identifier specified for entity" in error_lower):
        return {
            "category": "missing_entity_mapping",
            "description": "Entity is not properly mapped (missing @Entity or @Id)",
            "fix": "Ensure the entity class has @Entity annotation and has an @Id field. "
                   "Check that the entity is included in the component scan.",
            "import_needed": "jakarta.persistence.Entity",
        }

    # Pattern 18: Repository method name derivation error
    if "no property" in error_lower and "found for type" in error_lower:
        return {
            "category": "repository_method_error",
            "description": "Spring Data JPA cannot derive query from repository method name",
            "fix": "Verify method name follows Spring Data naming conventions. "
                   "Property name must match entity field exactly. Consider using @Query annotation.",
        }

    return None


def _build_fix_prompt(
    failures: list[dict[str, Any]],
    current_tests: dict[str, str],
    project_path: str,
) -> str:
    """
    Build a prompt for the agent to fix test failures.

    Args:
        failures: List of test failures
        current_tests: Dict of test file path -> content
        project_path: Project path

    Returns:
        Prompt string for the agent
    """
    prompt = f"""The following tests have failures that need to be fixed.

## Project: {project_path}

## Failures:
"""

    for i, failure in enumerate(failures, 1):
        prompt += f"\n### Failure {i}:\n"
        if failure.get("type") == "compilation":
            prompt += f"**Compilation Error** in `{failure.get('file')}` line {failure.get('line')}:\n"
            prompt += f"```\n{failure.get('error')}\n```\n"
            # Include JPA-specific fix suggestion if available
            jpa_error = failure.get("jpa_error")
            if jpa_error:
                prompt += f"\n**🔧 Suggested Fix ({jpa_error['category']}):**\n"
                prompt += f"- Problem: {jpa_error['description']}\n"
                prompt += f"- Solution: {jpa_error['fix']}\n"
                if jpa_error.get("import_needed"):
                    prompt += f"- Required import: `{jpa_error['import_needed']}`\n"
        elif failure.get("method"):
            prompt += f"**Test**: `{failure.get('class')}.{failure.get('method')}()`\n"
            prompt += f"**Error**: {failure.get('error')}\n"
        else:
            prompt += f"**Error**: {failure.get('error')}\n"

    prompt += "\n## Current Test Files:\n"

    for path, content in current_tests.items():
        prompt += f"\n### {path}\n```java\n{content}\n```\n"

    prompt += """
## Instructions:

1. Analyze each failure and understand the root cause
2. Fix the test code to make it pass
3. Common issues to check:
   - Missing imports
   - Wrong method signatures
   - Incorrect assertions
   - Missing mock setup
   - Wrong exception types
   - Null pointer issues

4. **JPA Entity Testing Rules (CRITICAL):**
   - NEVER call setId() on entities with @GeneratedValue - use ReflectionTestUtils.setField(entity, "id", value)
   - Use Optional.of(entity) not Optional.empty() when testing found entities
   - Use correct ID types: 1L for Long, 1 for Integer
   - Use assertThat() instead of assertEquals() for type safety
   - Import: org.springframework.test.util.ReflectionTestUtils

5. Return the COMPLETE fixed test files in ```java code blocks

IMPORTANT: Include the full corrected test class content, not just the changed parts.
Each test file should be in a separate ```java block with the complete class.
"""

    return prompt


__all__ = [
    "run_test_generation_with_agent",
    "TestGenerationError",
    "CompilationError",
    "MavenNotFoundError",
    "MavenTimeoutError",
    "_categorize_jpa_error",
]
