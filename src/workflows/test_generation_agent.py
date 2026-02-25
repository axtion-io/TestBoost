# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

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
import re
import shutil
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
from src.lib.llm import get_llm
from src.lib.logging import get_logger
from src.lib.maven_error_parser import MavenErrorParser
from src.lib.path_utils import (
    detect_maven_modules,
    extract_package,
    get_source_directories,
    test_path_to_source_path,
)
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


def _get_maven_executable() -> str:
    """Get the Maven executable name for the current platform.

    On Windows, Maven is a .cmd script, so we need 'mvn.cmd'.
    On Linux/macOS, it's a shell script, so 'mvn' works.

    Returns:
        str: The Maven executable name ('mvn.cmd' on Windows, 'mvn' elsewhere)
    """
    mvn = shutil.which("mvn")
    if mvn is None:
        # Fallback: try mvn.cmd explicitly on Windows
        mvn = shutil.which("mvn.cmd")
        if mvn is None:
            # If still not found, return 'mvn' and let subprocess fail with clear error
            return "mvn"
    return mvn


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
    use_llm: bool = True,
) -> list[dict[str, Any]]:
    """
    Generate tests directly by calling the generator tool for each source file.

    This bypasses the LLM agent and calls the generator directly, which produces
    more reliable results than asking the LLM to use tools.

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

            # Call generator directly
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
        # Write file to disk FIRST (critical for artifact retrieval)
        file_path = f"artifacts/{session_id}/compilation_errors/{Path(test_path).stem}_{attempt}.json"
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        error_content = json.dumps(errors, indent=2)
        path.write_text(error_content, encoding="utf-8")

        # Calculate actual file size
        size_bytes = path.stat().st_size

        # Create database record AFTER file exists
        await artifact_repo.create(
            session_id=session_id,
            name=f"compilation_error_{Path(test_path).stem}_attempt_{attempt}",
            artifact_type="compilation_error",
            content_type="application/json",
            file_path=file_path,
            size_bytes=size_bytes,
            file_format="json",  # T078: JSON format for errors (changed from txt)
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
    Comprehensive syntax validation for Java test files.

    Uses advanced Java syntax validation to detect common issues like
    unbalanced braces, incomplete statements, and malformed methods.

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

    # Advanced syntax validation (detects truncation, unbalanced braces, incomplete statements)
    is_valid, error_msg = _validate_java_syntax(test_content)
    if not is_valid:
        errors.append({"line": 0, "message": error_msg})

    return {"success": len(errors) == 0, "errors": errors}


def _extract_generated_tests(response: dict[str, Any] | AIMessage) -> list[dict[str, Any]]:
    """Extract generated test files from agent response.

    Extracts tests from:
    1. ```java code blocks in the response content
    2. JSON tool results containing 'test_code' field
    3. All messages in the conversation history
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
        # Strategy 1: Look for Java code blocks
        if "```java" in content:
            code_blocks = content.split("```java")
            for block in code_blocks[1:]:
                code = block.split("```")[0].strip()
                if code and _is_valid_test_code(code):
                    test_info = _extract_test_info(code)
                    if test_info and test_info not in tests:
                        tests.append(test_info)

        # Strategy 2: Look for JSON tool results with test_code
        if '"test_code"' in content or "'test_code'" in content:
            try:
                # Try to find and parse JSON objects in the content
                import re
                json_pattern = r'\{[^{}]*"test_code"[^{}]*\}'
                for match in re.finditer(json_pattern, content, re.DOTALL):
                    try:
                        data = json.loads(match.group())
                        if data.get("test_code"):
                            test_info = _extract_test_info(data["test_code"])
                            if test_info and test_info not in tests:
                                # Use file path from tool result if available
                                if data.get("test_file"):
                                    test_info["path"] = data["test_file"]
                                tests.append(test_info)
                    except json.JSONDecodeError:
                        # Expected for partial JSON matches, skip silently
                        continue
            except Exception as e:
                logger.debug("test_extraction_error", error=str(e), content_length=len(content))

    logger.debug("extracted_tests", count=len(tests))
    return tests


def _validate_java_syntax(code: str) -> tuple[bool, str | None]:
    """
    Validate Java code syntax for common truncation issues.

    Args:
        code: Java source code to validate

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check 1: Balanced braces
    open_braces = code.count("{")
    close_braces = code.count("}")
    if open_braces != close_braces:
        return False, f"Unbalanced braces: {open_braces} open, {close_braces} close"

    # Check 2: Balanced parentheses
    open_parens = code.count("(")
    close_parens = code.count(")")
    if open_parens != close_parens:
        return False, f"Unbalanced parentheses: {open_parens} open, {close_parens} close"

    # Check 3: Class declaration is closed
    if "class " in code and not code.rstrip().endswith("}"):
        return False, "Class declaration not properly closed (missing final })"

    # Check 4: No incomplete statements at end (common truncation pattern)
    last_line = code.strip().split("\n")[-1].strip()
    incomplete_patterns = [
        "assertThrows(",  # Incomplete assertThrows
        "assertEquals(",  # Incomplete assertion
        "assertTrue(",
        "assertFalse(",
        "assertNotNull(",
        "verify(",  # Incomplete Mockito verify
        "when(",  # Incomplete Mockito when
        "throws ",  # Incomplete throws clause
        "= ",  # Incomplete assignment
    ]
    for pattern in incomplete_patterns:
        if last_line.endswith(pattern) or (pattern in last_line and not last_line.endswith(";")):
            return False, f"Incomplete statement detected at end: '{last_line[:50]}...'"

    # Check 5: Method declarations have opening brace
    import re
    method_pattern = r'(@Test|@BeforeEach|@AfterEach|@ParameterizedTest)\s*\n\s*(?:public|private|protected)?\s*\w+\s+\w+\s*\([^)]*\)'
    for match in re.finditer(method_pattern, code):
        # Find if there's a '{' after the method declaration within next 100 chars
        snippet = code[match.end():match.end() + 100]
        if '{' not in snippet:
            return False, f"Test method missing opening brace: {match.group()[:50]}"

    return True, None


def _is_valid_test_code(code: str) -> bool:
    """Check if code is valid Java test code."""
    # Basic content checks
    if not ("class " in code and ("@Test" in code or "@ParameterizedTest" in code) and len(code) > 100):
        return False

    # Syntax validation
    is_valid, error = _validate_java_syntax(code)
    if not is_valid:
        logger.warning("invalid_java_syntax", error=error, code_length=len(code))
        return False

    return True


def _extract_test_info(code: str) -> dict[str, Any] | None:
    """Extract test info from Java code."""
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

    # Build test file path
    if package:
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
    """Extract Java code from agent response."""
    if "```java" in content:
        code_blocks = content.split("```java")
        if len(code_blocks) > 1:
            code = code_blocks[1].split("```")[0].strip()
            return code
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


def _detect_maven_modules(project_dir: Path) -> list[Path]:
    """Detect Maven module directories in a multi-module project."""
    return detect_maven_modules(project_dir)


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
    package = extract_package(test_content)
    if not package:
        return None

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

    # Write file to disk FIRST (critical for artifact retrieval)
    file_path = f"artifacts/{session_id}/reasoning/{agent_name}.json"
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    content_json = json.dumps(reasoning_content, indent=2)
    path.write_text(content_json, encoding="utf-8")

    # Calculate actual file size
    size_bytes = path.stat().st_size

    # Create database record AFTER file exists
    await artifact_repo.create(
        session_id=session_id,
        name=f"agent_reasoning_{agent_name}",
        artifact_type="agent_reasoning",
        content_type="application/json",
        file_path=file_path,
        size_bytes=size_bytes,
        file_format="json",  # T079: JSON format for agent reasoning
    )

    logger.debug("agent_reasoning_stored", session_id=str(session_id), file_path=file_path)


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

        # Write file to disk FIRST (critical for artifact retrieval)
        file_path = f"artifacts/{session_id}/tool_calls/call_{i}.json"
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        content_json = json.dumps(tool_content, indent=2)
        path.write_text(content_json, encoding="utf-8")

        # Calculate actual file size
        size_bytes = path.stat().st_size

        # Create database record AFTER file exists
        await artifact_repo.create(
            session_id=session_id,
            name=f"tool_call_{i}_{tool_content['tool_name']}",
            artifact_type="llm_tool_call",
            content_type="application/json",
            file_path=file_path,
            size_bytes=size_bytes,
            file_format="json",  # T079: JSON format for tool calls
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

        # Write file to disk FIRST (critical for artifact retrieval)
        artifact_file_path = f"artifacts/{session_id}/tests/{Path(file_path).name}"
        artifact_path = Path(artifact_file_path)
        artifact_path.parent.mkdir(parents=True, exist_ok=True)

        artifact_path.write_text(content, encoding="utf-8")

        # Calculate actual file size
        size_bytes = artifact_path.stat().st_size

        # Create database record AFTER file exists
        await artifact_repo.create(
            session_id=session_id,
            name=f"test_file_{Path(file_path).stem}",
            artifact_type="file_modification",
            content_type="text/x-java",
            file_path=artifact_file_path,
            size_bytes=size_bytes,
            artifact_metadata=metadata,
            file_format="java",  # T077: Java source files
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

    # Write file to disk FIRST (critical for artifact retrieval)
    file_path = f"artifacts/{session_id}/metrics/generation_metrics.json"
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    content_json = json.dumps(metrics_content, indent=2)
    path.write_text(content_json, encoding="utf-8")

    # Calculate actual file size
    size_bytes = path.stat().st_size

    # Create database record AFTER file exists
    await artifact_repo.create(
        session_id=session_id,
        name="generation_metrics",
        artifact_type="generation_metrics",
        content_type="application/json",
        file_path=file_path,
        size_bytes=size_bytes,
        file_format="json",  # T079: JSON format for metrics
    )

    logger.debug("generation_metrics_stored", session_id=str(session_id), file_path=file_path)


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

    # Write file to disk FIRST (critical for artifact retrieval)
    file_path = f"artifacts/{session_id}/metrics/llm_metrics.json"
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    content_json = json.dumps(metrics_content, indent=2)
    path.write_text(content_json, encoding="utf-8")

    # Calculate actual file size
    size_bytes = path.stat().st_size

    # Create database record AFTER file exists
    await artifact_repo.create(
        session_id=session_id,
        name="llm_metrics",
        artifact_type="llm_metrics",
        content_type="application/json",
        file_path=file_path,
        size_bytes=size_bytes,
        file_format="json",  # T079: JSON format for LLM metrics
    )

    logger.debug("llm_metrics_stored", session_id=str(session_id), file_path=file_path)


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

    # Extract project context once (pom.xml, Java version, frameworks)
    project_context = _get_project_context(project_path)
    if project_context:
        logger.info("project_context_loaded", project_path=project_path, context_length=len(project_context))

    for iteration in range(1, max_iterations + 1):
        logger.info(
            "test_feedback_iteration",
            session_id=str(session_id),
            iteration=iteration,
            max_iterations=max_iterations,
        )

        # Step 1: Compile tests first to detect compilation errors early
        compile_result = await _compile_maven_tests(project_dir, test_files)

        if not compile_result["success"]:
            # Compilation failed - extract errors and ask agent to fix
            logger.warning(
                "test_compilation_failed",
                session_id=str(session_id),
                iteration=iteration,
                error_count=len(compile_result.get("compilation_errors", [])),
            )

            # Store compilation error artifact
            file_path = f"artifacts/{session_id}/compilation_errors/iteration_{iteration}.json"
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            errors_content = json.dumps(compile_result.get("compilation_errors", []), indent=2)
            path.write_text(errors_content, encoding="utf-8")
            size_bytes = path.stat().st_size

            await artifact_repo.create(
                session_id=session_id,
                name=f"compilation_errors_iteration_{iteration}",
                artifact_type="compilation_error",
                content_type="application/json",
                file_path=file_path,
                size_bytes=size_bytes,
                file_format="json",
            )

            # Fix compilation errors FILE BY FILE to avoid LLM output truncation
            all_errors = compile_result.get("compilation_errors", [])
            errors_by_file = {}
            for err in all_errors:
                fname = err.get("file", "unknown")
                if fname not in errors_by_file:
                    errors_by_file[fname] = []
                errors_by_file[fname].append(err)

            logger.info(
                "per_file_correction_start",
                session_id=str(session_id),
                iteration=iteration,
                files_with_errors=len(errors_by_file),
                total_errors=len(all_errors),
            )

            files_corrected = 0
            for error_file, file_errors in errors_by_file.items():
                # Find the matching test path in current_tests
                test_path_match = None
                for test_path in current_tests:
                    if Path(error_file).name in test_path or Path(test_path).name == Path(error_file).name:
                        test_path_match = test_path
                        break

                if not test_path_match:
                    logger.warning("no_test_match_for_error_file", error_file=error_file)
                    continue

                # Build a focused prompt for this single file
                fix_prompt = _build_fix_prompt_per_file(
                    file_errors,
                    test_path_match,
                    current_tests[test_path_match],
                    project_path,
                    project_context=project_context,
                )

                fix_response = await _invoke_agent_and_store_tools(
                    agent=agent,
                    input_data={"messages": [HumanMessage(content=fix_prompt)]},
                    session_id=session_id,
                    artifact_repo=artifact_repo,
                )

                # Extract and write corrected test
                corrected_tests = _extract_generated_tests(fix_response)

                if corrected_tests:
                    for corrected in corrected_tests:
                        path_str = corrected.get("path")
                        content = corrected.get("content")
                        if path_str and content:
                            # Validate Java syntax before writing
                            is_valid, syntax_error = _validate_java_syntax(content)
                            if not is_valid:
                                logger.warning(
                                    "corrected_file_invalid_syntax",
                                    path=path_str,
                                    error=syntax_error,
                                    iteration=iteration,
                                )
                                # Try to auto-fix unbalanced braces
                                content = _try_fix_truncated_java(content)

                            current_tests[path_str] = content
                            full_path = project_dir / path_str
                            try:
                                full_path.parent.mkdir(parents=True, exist_ok=True)
                                full_path.write_text(content, encoding="utf-8")
                                files_corrected += 1
                                logger.info(
                                    "corrected_test_written",
                                    path=str(full_path),
                                    iteration=iteration,
                                    file_errors=len(file_errors),
                                )
                            except Exception as e:
                                logger.error("corrected_test_write_failed", path=path_str, error=str(e))

            logger.info(
                "per_file_correction_complete",
                session_id=str(session_id),
                iteration=iteration,
                files_corrected=files_corrected,
                files_with_errors=len(errors_by_file),
            )

            # Continue to next iteration
            continue

        # Step 2: Run Maven tests (only if compilation succeeded)
        test_result = await _run_maven_tests(project_dir, test_files)

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
        # Write file to disk FIRST (critical for artifact retrieval)
        file_path = f"artifacts/{session_id}/test_failures/iteration_{iteration}.json"
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        failures_content = json.dumps(failures, indent=2)
        path.write_text(failures_content, encoding="utf-8")

        # Calculate actual file size
        size_bytes = path.stat().st_size

        # Create database record AFTER file exists
        await artifact_repo.create(
            session_id=session_id,
            name=f"test_failures_iteration_{iteration}",
            artifact_type="test_failure",
            content_type="application/json",
            file_path=file_path,
            size_bytes=size_bytes,
            file_format="json",  # T079: JSON format for test failures
        )

        # Step 3: Group runtime failures by test class and fix per-file
        runtime_failures = [f for f in failures if f.get("type") == "runtime"]
        other_failures = [f for f in failures if f.get("type") != "runtime"]

        if runtime_failures:
            # Group by simple class name -> find matching test file
            failures_by_class: dict[str, list[dict[str, Any]]] = {}
            for f in runtime_failures:
                cls = f.get("class", "unknown")
                simple_cls = cls.rsplit(".", 1)[-1] if "." in cls else cls
                if simple_cls not in failures_by_class:
                    failures_by_class[simple_cls] = []
                failures_by_class[simple_cls].append(f)

            logger.info(
                "per_file_runtime_correction_start",
                session_id=str(session_id),
                iteration=iteration,
                classes_with_failures=len(failures_by_class),
                total_failures=len(runtime_failures),
            )

            files_corrected = 0
            for class_name, class_failures in failures_by_class.items():
                # Find matching test path
                test_path_match = None
                for test_path in current_tests:
                    if class_name in Path(test_path).stem:
                        test_path_match = test_path
                        break

                if not test_path_match:
                    logger.warning("no_test_match_for_failure_class", class_name=class_name)
                    continue

                # Build per-file prompt with runtime failures
                fix_prompt = _build_fix_prompt_per_file(
                    class_failures,
                    test_path_match,
                    current_tests[test_path_match],
                    project_path,
                    project_context=project_context,
                )

                fix_response = await _invoke_agent_and_store_tools(
                    agent=agent,
                    input_data={"messages": [HumanMessage(content=fix_prompt)]},
                    session_id=session_id,
                    artifact_repo=artifact_repo,
                )

                corrected_tests = _extract_generated_tests(fix_response)
                if corrected_tests:
                    for corrected in corrected_tests:
                        path_str = corrected.get("path")
                        content = corrected.get("content")
                        if path_str and content:
                            is_valid, syntax_error = _validate_java_syntax(content)
                            if not is_valid:
                                logger.warning(
                                    "corrected_file_invalid_syntax",
                                    path=path_str,
                                    error=syntax_error,
                                    iteration=iteration,
                                )
                                content = _try_fix_truncated_java(content)

                            current_tests[path_str] = content
                            full_path = project_dir / path_str
                            try:
                                full_path.parent.mkdir(parents=True, exist_ok=True)
                                full_path.write_text(content, encoding="utf-8")
                                files_corrected += 1
                                logger.info(
                                    "corrected_test_written",
                                    path=str(full_path),
                                    iteration=iteration,
                                    runtime_failures=len(class_failures),
                                )
                            except Exception as e:
                                logger.error("corrected_test_write_failed", path=path_str, error=str(e))

            logger.info(
                "per_file_runtime_correction_complete",
                session_id=str(session_id),
                iteration=iteration,
                files_corrected=files_corrected,
                classes_with_failures=len(failures_by_class),
            )

        elif other_failures:
            # Fallback: non-runtime failures (compilation, assertion, unknown)
            fix_prompt = _build_fix_prompt(other_failures, current_tests, project_path, project_context=project_context)

            fix_response = await _invoke_agent_and_store_tools(
                agent=agent,
                input_data={"messages": [HumanMessage(content=fix_prompt)]},
                session_id=session_id,
                artifact_repo=artifact_repo,
            )

            corrected_tests = _extract_generated_tests(fix_response)
            if corrected_tests:
                for corrected in corrected_tests:
                    path_str = corrected.get("path")
                    content = corrected.get("content")
                    if path_str and content:
                        current_tests[path_str] = content
                        full_path = project_dir / path_str
                        try:
                            full_path.parent.mkdir(parents=True, exist_ok=True)
                            full_path.write_text(content, encoding="utf-8")
                            logger.info(
                                "corrected_test_written",
                                path=str(full_path),
                                iteration=iteration,
                            )
                        except Exception as e:
                            logger.error("corrected_test_write_failed", path=path_str, error=str(e))

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


async def _compile_maven_tests(
    project_dir: Path,
    test_files: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compile test files using 'mvn clean test-compile' to detect compilation errors early.

    This step is CRITICAL to detect type errors and other compilation issues before
    running tests. Without this, Maven might use pre-compiled classes from target/
    directory, leading to false positives where tests appear to pass but actually
    contain compilation errors.

    Args:
        project_dir: Path to the Maven project
        test_files: List of test file info dicts

    Returns:
        dict with success flag, output, and parsed compilation errors
    """
    # Group tests by module
    tests_by_module: dict[str, list[str]] = {}
    for test_file in test_files:
        path = test_file.get("actual_path", test_file.get("path", ""))
        if not path.endswith(".java"):
            continue

        # Check if path includes a module directory
        parts = Path(path).parts
        if len(parts) > 1 and (project_dir / parts[0] / "pom.xml").exists():
            module = parts[0]
        else:
            module = ""

        if module not in tests_by_module:
            tests_by_module[module] = []

    if not tests_by_module:
        return {
            "success": False,
            "output": "No test files found",
            "return_code": -1,
            "compilation_errors": [],
        }

    all_output = []
    all_success = True
    all_compilation_errors = []

    # Compile tests for each module
    for module in tests_by_module:
        if module:
            pom_path = project_dir / module / "pom.xml"
            cwd = project_dir / module
        else:
            pom_path = project_dir / "pom.xml"
            cwd = project_dir

        if not pom_path.exists():
            all_output.append(f"No pom.xml found for module {module or 'root'}")
            continue

        # Build Maven compile command
        mvn_cmd = [_get_maven_executable(), "clean", "test-compile", "-f", pom_path.resolve().as_posix()]

        logger.info(
            "compiling_maven_tests",
            module=module or "root",
            command=" ".join(mvn_cmd),
        )

        try:
            result = subprocess.run(
                mvn_cmd,
                cwd=str(cwd.resolve()),
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
            )

            output = result.stdout + "\n" + result.stderr
            all_output.append(f"=== Module: {module or 'root'} ===\n{output}")

            # Parse compilation errors with new structured parser
            compilation_errors = []
            if result.returncode != 0:
                all_success = False
                # Use new MavenErrorParser for better structured feedback
                error_parser = MavenErrorParser()
                parsed_errors = error_parser.parse(output)

                # Convert to dict format for compatibility
                compilation_errors = [
                    {
                        "type": "compilation",
                        "file": str(err.file_path),
                        "line": err.line,
                        "column": err.column,
                        "error": err.message,
                        "error_type": err.error_type,
                        "actual_type": err.actual_type,
                        "expected_type": err.expected_type,
                        "symbol": err.symbol,
                        "suggestion": err.suggestion,
                    }
                    for err in parsed_errors
                ]
                all_compilation_errors.extend(compilation_errors)

                # Log summary
                summary = error_parser.get_summary(parsed_errors)
                logger.info(
                    "compilation_errors_parsed",
                    module=module or "root",
                    total_errors=summary["total_errors"],
                    errors_by_type=summary["errors_by_type"],
                )

            logger.info(
                "maven_test_compile_complete",
                module=module or "root",
                success=result.returncode == 0,
                return_code=result.returncode,
                errors_found=len(compilation_errors),
            )

        except subprocess.TimeoutExpired:
            logger.error("maven_test_compile_timeout", module=module, timeout=TEST_TIMEOUT_SECONDS)
            all_output.append(f"Module {module}: compilation timed out after {TEST_TIMEOUT_SECONDS}s")
            all_success = False

        except Exception as e:
            logger.error("maven_test_compile_failed", module=module, error=str(e))
            all_output.append(f"Module {module}: {str(e)}")
            all_success = False

    return {
        "success": all_success,
        "output": "\n".join(all_output),
        "return_code": 0 if all_success else 1,
        "compilation_errors": all_compilation_errors,
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
        # CRITICAL: Use 'mvn clean test' to force full recompilation and avoid false positives
        # from pre-compiled classes in target/ directory
        mvn_cmd = [_get_maven_executable(), "clean", "test", "-f", pom_path.resolve().as_posix()]

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
            result = subprocess.run(
                mvn_cmd,
                cwd=str(cwd.resolve()),
                capture_output=True,
                text=True,
                timeout=TEST_TIMEOUT_SECONDS,
            )

            output = result.stdout + "\n" + result.stderr
            all_output.append(f"=== Module: {module or 'root'} ===\n{output}")

            if result.returncode != 0:
                all_success = False

            # CRITICAL: Check that tests were actually executed.
            # Maven with -DfailIfNoTests=false returns code 0 even when 0 tests run
            # (e.g. Surefire version incompatible with JUnit 5).
            tests_run_match = re.search(
                r"Tests run:\s*(\d+),\s*Failures:\s*(\d+),\s*Errors:\s*(\d+)",
                output,
            )
            if tests_run_match:
                total_run = int(tests_run_match.group(1))
                total_failures = int(tests_run_match.group(2))
                total_errors = int(tests_run_match.group(3))
                if total_run == 0:
                    logger.error(
                        "maven_zero_tests_run",
                        module=module or "root",
                        message="Maven returned 0 tests run - tests were NOT executed",
                    )
                    all_success = False
                    all_output.append(
                        f"ERROR: 0 tests were executed in module {module or 'root'}. "
                        "This likely means the test framework is not properly configured "
                        "(e.g. Surefire version incompatible with JUnit 5)."
                    )
                elif total_failures > 0 or total_errors > 0:
                    all_success = False
            else:
                # No "Tests run:" line found at all - suspicious
                logger.warning(
                    "maven_no_test_summary",
                    module=module or "root",
                    message="Could not find 'Tests run:' summary in Maven output",
                )
                # If returncode was 0 but no test summary, treat as failure
                if result.returncode == 0:
                    all_success = False
                    all_output.append(
                        f"WARNING: No test execution summary found for module {module or 'root'}. "
                        "Tests may not have been executed."
                    )

            logger.info(
                "maven_tests_complete",
                module=module or "root",
                success=all_success,
                return_code=result.returncode,
            )

        except subprocess.TimeoutExpired:
            logger.error("maven_tests_timeout", module=module, timeout=TEST_TIMEOUT_SECONDS)
            all_output.append(f"Module {module}: timed out after {TEST_TIMEOUT_SECONDS}s")
            all_success = False

        except Exception as e:
            logger.error("maven_tests_failed", module=module, error=str(e))
            all_output.append(f"Module {module}: {str(e)}")
            all_success = False

    return {
        "success": all_success,
        "output": "\n".join(all_output),
        "return_code": 0 if all_success else 1,
    }


def _parse_test_failures(maven_output: str) -> list[dict[str, Any]]:
    """
    Parse Maven test output to extract failure information.

    Supports both Surefire 2.x and 3.x output formats.

    Args:
        maven_output: Raw Maven test output

    Returns:
        List of failure dicts with test name, error message, and stack trace
    """
    failures = []
    seen_keys: set[str] = set()  # Deduplicate by (class, method)

    def _add_failure(failure: dict[str, Any]) -> None:
        """Add failure if not already seen (deduplicates by fully qualified class name + method)."""
        cls = failure.get("class", "")
        method = failure.get("method", "")
        key = f"{cls}.{method}"
        if key != "." and key in seen_keys:
            # If already seen, update with stack trace if available
            if failure.get("stacktrace"):
                for f in failures:
                    if f.get("class", "") == cls and f.get("method") == method:
                        f["stacktrace"] = failure["stacktrace"]
                        break
            return
        if key != ".":
            seen_keys.add(key)
        failures.append(failure)

    # ---- Surefire 3.x format ----
    # Summary section:
    #   [ERROR] Errors:
    #   [ERROR]   ClassName.methodName:lineNum ~ ExceptionType message
    # or:
    #   [ERROR] Failures:
    #   [ERROR]   ClassName.methodName:lineNum ~ ExceptionType message
    surefire3_summary_pattern = re.compile(
        r"\[ERROR\]\s+(?:Errors|Failures):\s*\n((?:\[ERROR\]\s+.+\n)+)",
        re.MULTILINE,
    )
    # Individual line format: "  ClassName.methodName:line ~ ExceptionType message"
    surefire3_line_pattern = re.compile(
        r"\[ERROR\]\s+(\S+)\.(\w+):(\d+)\s+.{1,3}\s+(\w+(?:\.\w+)*)\s+(.*)"
    )

    for section_match in surefire3_summary_pattern.finditer(maven_output):
        section_block = section_match.group(1)
        for line in section_block.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            line_match = surefire3_line_pattern.match(line)
            if line_match:
                _add_failure({
                    "type": "runtime",
                    "class": line_match.group(1),
                    "method": line_match.group(2),
                    "line": int(line_match.group(3)),
                    "error_type": line_match.group(4),
                    "error": line_match.group(5).strip(),
                })

    # ---- Stack trace blocks (Surefire 3.x) ----
    # [ERROR] com.example.FooTest.myMethod -- Time elapsed: 0.005 s <<< ERROR!
    # java.lang.NullPointerException: message
    #     at com.example.Foo.bar(Foo.java:42)
    #     at com.example.FooTest.myMethod(FooTest.java:15)
    stacktrace_pattern = re.compile(
        r"\[ERROR\]\s+([\w.]+)\.([\w]+)\s+--\s+Time elapsed:.*?<<<\s+(?:ERROR|FAILURE)!\n"
        r"([\s\S]*?)(?=\n\[ERROR\]\s+\S+\.\S+\s+--|(?:\n\[INFO\])|\n\n)",
        re.MULTILINE,
    )

    for match in stacktrace_pattern.finditer(maven_output):
        class_name = match.group(1)
        method_name = match.group(2)
        stacktrace_block = match.group(3).strip()

        # Extract exception type and message from first line of stack trace
        exception_line = stacktrace_block.split("\n")[0] if stacktrace_block else ""
        exc_match = re.match(r"([\w.]+(?:Exception|Error|Throwable)):\s*(.*)", exception_line)

        # Limit stack trace to useful lines (max 10)
        trace_lines = stacktrace_block.split("\n")
        limited_trace = "\n".join(trace_lines[:10])
        if len(trace_lines) > 10:
            limited_trace += f"\n    ... ({len(trace_lines) - 10} more lines)"

        key = f"{class_name}.{method_name}"
        if key in seen_keys:
            # Update existing failure with stack trace
            for f in failures:
                if f.get("class") == class_name and f.get("method") == method_name:
                    f["stacktrace"] = limited_trace
                    break
        else:
            _add_failure({
                "type": "runtime",
                "class": class_name,
                "method": method_name,
                "error_type": exc_match.group(1) if exc_match else "Unknown",
                "error": exc_match.group(2).strip() if exc_match else exception_line,
                "stacktrace": limited_trace,
            })

    # ---- Surefire 2.x format (backwards compatibility) ----
    # "Failed tests:"  or  "Tests in error:"
    #   methodName(className): error message
    failure_pattern = re.compile(
        r"(?:Failed tests?|Tests in error):\s*\n((?:\s+.+\n)+)",
        re.MULTILINE,
    )
    for match in failure_pattern.findall(maven_output):
        for line in match.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            test_match = re.match(r"(\w+)\(([^)]+)\):\s*(.+)", line)
            if test_match:
                _add_failure({
                    "type": "runtime",
                    "method": test_match.group(1),
                    "class": test_match.group(2),
                    "error": test_match.group(3),
                })

    # ---- Compilation errors ----
    compile_error_pattern = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),(\d+)\]\s*(.+)",
        re.MULTILINE,
    )
    for match in compile_error_pattern.finditer(maven_output):
        error_msg = match.group(4)
        failure = {
            "type": "compilation",
            "file": match.group(1),
            "line": int(match.group(2)),
            "column": int(match.group(3)),
            "error": error_msg,
        }
        failure["jpa_error"] = _categorize_jpa_error(error_msg)
        failure["type_error"] = _categorize_type_error(error_msg)
        failures.append(failure)

    # ---- Assertion failures with stack traces ----
    assertion_pattern = re.compile(
        r"(org\.opentest4j\.\w+|java\.lang\.AssertionError):\s*(.+?)(?=\n\tat|\n\n|$)",
        re.DOTALL,
    )
    for match in assertion_pattern.finditer(maven_output):
        error_type = match.group(1)
        message = match.group(2).strip()
        if message and not any(f.get("error") == message for f in failures):
            failures.append({
                "type": "assertion",
                "error_type": error_type,
                "error": message,
            })

    return failures


def _categorize_jpa_error(error_msg: str) -> dict[str, Any] | None:
    """Categorize JPA-specific compilation errors and provide fix suggestions.

    This helps the feedback loop to intelligently fix common JPA test errors.
    """
    error_lower = error_msg.lower()

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

    return None


def _categorize_type_error(error_msg: str) -> dict[str, Any] | None:
    """
    Categorize type-related compilation errors and provide fix suggestions.

    This helps detect common type errors like BigDecimal vs Double, String vs Integer, etc.
    These are the exact errors that were missed in the BankApp validation issue.

    Args:
        error_msg: Compilation error message

    Returns:
        dict with error category and fix suggestion, or None if not a type error
    """
    error_lower = error_msg.lower()

    # Pattern 1: BigDecimal vs Double
    if "incompatible types" in error_lower and ("bigdecimal" in error_lower or "double" in error_lower):
        return {
            "category": "bigdecimal_double_mismatch",
            "description": "Type mismatch between BigDecimal and Double",
            "fix": "Use new BigDecimal(\"value\") instead of Double. Never use double primitives with BigDecimal fields.",
            "example": "new BigDecimal(\"100.00\") instead of 100.0",
        }

    # Pattern 2: String vs Integer
    if "incompatible types" in error_lower and (
        ("string" in error_lower and "integer" in error_lower) or
        ("string" in error_lower and "int" in error_lower)
    ):
        return {
            "category": "string_integer_mismatch",
            "description": "Type mismatch between String and Integer",
            "fix": "Use Integer.parseInt(string) to convert String to Integer, or use string literals with quotes",
            "example": "Use 123 (Integer) instead of \"123\" (String), or vice versa",
        }

    # Pattern 3: Method parameter type mismatch
    if "method" in error_lower and "cannot be applied to given types" in error_lower:
        return {
            "category": "method_parameter_type_mismatch",
            "description": "Method called with wrong parameter types",
            "fix": "Check the method signature and ensure parameter types match exactly",
        }

    # Pattern 4: Builder pattern error (method not found)
    if "cannot find symbol" in error_lower and "builder" in error_lower:
        return {
            "category": "builder_not_found",
            "description": "Builder pattern method not found on class",
            "fix": "Check if class has @Builder annotation (Lombok), or use constructor instead",
            "example": "Use new ClassName() constructor instead of ClassName.builder()",
        }

    # Pattern 5: Private field access
    if "has private access" in error_lower or "is not visible" in error_lower:
        return {
            "category": "private_field_access",
            "description": "Attempting to access private field directly",
            "fix": "Use getter method or ReflectionTestUtils.setField() for private fields in tests",
            "import_needed": "org.springframework.test.util.ReflectionTestUtils",
        }

    # Pattern 6: Cannot find symbol (general)
    if "cannot find symbol" in error_lower:
        return {
            "category": "symbol_not_found",
            "description": "Variable, method, or class not found",
            "fix": "Check spelling, imports, and ensure the symbol exists in the source code",
        }

    # Pattern 7: Array vs Collection type mismatch
    if "incompatible types" in error_lower and ("list" in error_lower or "array" in error_lower):
        return {
            "category": "array_collection_mismatch",
            "description": "Type mismatch between array and collection",
            "fix": "Use Arrays.asList() to convert array to List, or toArray() to convert List to array",
        }

    return None


def _find_source_file_for_test(test_path: str, project_path: str) -> str | None:
    """Find the source file corresponding to a test file."""
    return test_path_to_source_path(test_path, project_path)


def _build_fix_prompt(
    failures: list[dict[str, Any]],
    current_tests: dict[str, str],
    project_path: str,
    project_context: str = "",
) -> str:
    """
    Build a prompt for the agent to fix test failures.

    Args:
        failures: List of test failures
        current_tests: Dict of test file path -> content
        project_path: Project path
        project_context: Pre-extracted project context (pom.xml info)

    Returns:
        Prompt string for the agent
    """
    from pathlib import Path

    # Limit number of failures to avoid context overflow
    MAX_FAILURES_IN_PROMPT = 20
    has_more_failures = len(failures) > MAX_FAILURES_IN_PROMPT

    # Separate compilation errors from runtime test failures
    compilation_errors = [f for f in failures if f.get("type") == "compilation"]
    runtime_failures = [f for f in failures if f.get("type") != "compilation"]

    prompt = f"""The following tests have failures that need to be fixed.

## Project: {project_path}

"""

    # Add project technical context
    if project_context:
        prompt += project_context + "\n"

    # Use MavenErrorParser to format compilation errors with structured suggestions
    if compilation_errors:
        # Convert dict format back to CompilationError objects for formatting
        from src.lib.maven_error_parser import CompilationError, MavenErrorParser

        error_objects = []
        for err in compilation_errors:
            if err.get("suggestion"):  # Only if parsed by MavenErrorParser
                error_objects.append(
                    CompilationError(
                        file_path=Path(err.get("file", "unknown.java")),
                        line=err.get("line", 0),
                        column=err.get("column", 0),
                        error_type=err.get("error_type", "unknown"),
                        message=err.get("error", ""),
                        actual_type=err.get("actual_type"),
                        expected_type=err.get("expected_type"),
                        symbol=err.get("symbol"),
                        suggestion=err.get("suggestion"),
                    )
                )

        if error_objects:
            parser = MavenErrorParser()
            formatted_errors = parser.format_for_llm(error_objects)
            prompt += formatted_errors + "\n\n"
        else:
            # Fallback to old format if errors weren't parsed
            prompt += "## Compilation Errors:\n\n"
            for i, failure in enumerate(compilation_errors[:MAX_FAILURES_IN_PROMPT], 1):
                error_msg = failure.get('error', '')
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "... (truncated)"
                prompt += f"### Error {i}:\n"
                prompt += f"**File**: `{failure.get('file')}` line {failure.get('line')}\n"
                prompt += f"```\n{error_msg}\n```\n\n"

    # Format runtime test failures
    if runtime_failures:
        runtime_to_show = runtime_failures[:MAX_FAILURES_IN_PROMPT]
        prompt += f"## Runtime Test Failures{f' (showing {len(runtime_to_show)} of {len(runtime_failures)})' if len(runtime_failures) > MAX_FAILURES_IN_PROMPT else ''}:\n\n"

        for i, failure in enumerate(runtime_to_show, 1):
            prompt += f"### Failure {i}:\n"
            if failure.get("method"):
                error_msg = failure.get('error', '')
                if len(error_msg) > 300:
                    error_msg = error_msg[:300] + "... (truncated)"
                prompt += f"**Test**: `{failure.get('class')}.{failure.get('method')}()`\n"
                prompt += f"**Error**: {error_msg}\n\n"
            else:
                error_msg = failure.get('error', '')
                if len(error_msg) > 300:
                    error_msg = error_msg[:300] + "... (truncated)"
                prompt += f"**Error**: {error_msg}\n\n"

    if has_more_failures:
        prompt += f"\n_Note: {len(failures) - MAX_FAILURES_IN_PROMPT} additional failures not shown. Fix the above first._\n"

    # Add source code context
    prompt += "\n## Source Code Context:\n"
    prompt += "\nHere are the actual implementations of the classes being tested:\n"

    source_files_added = set()
    project_dir = Path(project_path)

    for test_path in current_tests:
        source_path = _find_source_file_for_test(test_path, project_path)
        if source_path and source_path not in source_files_added:
            try:
                full_source_path = project_dir / source_path
                if full_source_path.exists():
                    source_content = full_source_path.read_text(encoding="utf-8")
                    # Limit source code to avoid context overflow (max 500 lines)
                    lines = source_content.split("\n")
                    if len(lines) > 500:
                        source_content = "\n".join(lines[:500]) + "\n... (truncated)"
                    prompt += f"\n### {source_path}\n```java\n{source_content}\n```\n"
                    source_files_added.add(source_path)
            except Exception as e:
                logger.debug("source_file_read_error", path=source_path, error=str(e))

    prompt += "\n## Current Test Files:\n"

    for path, content in current_tests.items():
        prompt += f"\n### {path}\n```java\n{content}\n```\n"

    prompt += """
## Instructions:

1. **READ THE SUGGESTIONS ABOVE** - Each error includes a specific "How to fix" suggestion. Follow these suggestions EXACTLY.

2. **For Compilation Errors:**
   - Apply the exact fix suggested for each error
   - Use the EXACT types specified (not approximations)
   - Check line and column numbers to locate the exact error location
   - Fix ALL compilation errors before moving to other issues

3. **Type Safety Rules (CRITICAL):**
   - NEVER mix BigDecimal with Double - use Double literals (123.45) not new BigDecimal("123.45")
   - NEVER mix String with Integer - use Integer literals (123) not String "123"
   - NEVER use builder() if the class doesn't have @Builder - use constructor instead
   - Check the source code types CAREFULLY before setting values
   - Use the exact type from the source class (Long vs Integer, BigDecimal vs Double, etc.)

4. **JPA Entity Testing Rules (CRITICAL):**
   - NEVER call setId() on entities with @GeneratedValue - use ReflectionTestUtils.setField(entity, "id", value)
   - Use Optional.of(entity) not Optional.empty() when testing found entities
   - Use correct ID types: 1L for Long, 1 for Integer
   - Use assertThat() instead of assertEquals() for type safety
   - Import: org.springframework.test.util.ReflectionTestUtils

5. **Common Runtime Test Issues:**
   - Missing imports
   - Wrong method signatures
   - Incorrect assertions
   - Missing mock setup
   - Wrong exception types
   - Null pointer issues

6. **Return Format:**
   - Return the COMPLETE fixed test files in ```java code blocks
   - Include the full corrected test class content, not just the changed parts
   - Each test file should be in a separate ```java block with the complete class

CRITICAL: The suggestions provided above are based on actual Maven compiler output and source code analysis.
Follow them EXACTLY to ensure successful compilation.
"""

    return prompt


def _build_fix_prompt_per_file(
    file_errors: list[dict[str, Any]],
    test_path: str,
    test_content: str,
    project_path: str,
    project_context: str = "",
) -> str:
    """Build a focused fix prompt for a single test file.

    This sends only the errors and code for ONE file, avoiding LLM output
    truncation that occurs when all files are sent at once.

    Supports both compilation errors and runtime test failures.

    Args:
        file_errors: Errors for this specific file (compilation or runtime)
        test_path: Path to the test file (relative to project)
        test_content: Current content of the test file
        project_path: Project path
        project_context: Pre-extracted project context (pom.xml info)

    Returns:
        Prompt string for the agent
    """
    from src.lib.maven_error_parser import CompilationError, MavenErrorParser

    file_name = Path(test_path).name

    # Separate compilation and runtime errors
    compilation_errors = [e for e in file_errors if e.get("type") == "compilation"]
    runtime_errors = [e for e in file_errors if e.get("type") == "runtime"]
    other_errors = [e for e in file_errors if e.get("type") not in ("compilation", "runtime")]

    # Choose the right heading
    if compilation_errors and not runtime_errors:
        heading = "Fix the compilation errors in the test file below."
    elif runtime_errors and not compilation_errors:
        heading = "Fix the runtime test failures in the test file below."
    else:
        heading = "Fix the errors in the test file below."

    prompt = f"""{heading}

## Project: {project_path}
## File to fix: {test_path}

"""

    # Add project technical context (Java version, dependencies, etc.)
    if project_context:
        prompt += project_context + "\n"

    # Format compilation errors using MavenErrorParser if possible
    if compilation_errors:
        error_objects = []
        for err in compilation_errors:
            if err.get("suggestion"):
                error_objects.append(
                    CompilationError(
                        file_path=Path(err.get("file", "unknown.java")),
                        line=err.get("line", 0),
                        column=err.get("column", 0),
                        error_type=err.get("error_type", "unknown"),
                        message=err.get("error", ""),
                        actual_type=err.get("actual_type"),
                        expected_type=err.get("expected_type"),
                        symbol=err.get("symbol"),
                        suggestion=err.get("suggestion"),
                    )
                )

        if error_objects:
            parser = MavenErrorParser()
            prompt += parser.format_for_llm(error_objects) + "\n\n"
        else:
            prompt += f"## Compilation Errors ({len(compilation_errors)}):\n\n"
            for i, err in enumerate(compilation_errors, 1):
                error_msg = err.get('error', '')
                if len(error_msg) > 500:
                    error_msg = error_msg[:500] + "... (truncated)"
                prompt += f"### Error {i} - Line {err.get('line')}:\n"
                prompt += f"```\n{error_msg}\n```\n\n"

    # Format runtime test failures with full stack traces
    if runtime_errors:
        prompt += f"## Runtime Test Failures ({len(runtime_errors)}):\n\n"
        for i, err in enumerate(runtime_errors, 1):
            method = err.get("method", "unknown")
            error_type = err.get("error_type", "Exception")
            error_msg = err.get("error", "")
            stacktrace = err.get("stacktrace", "")

            prompt += f"### Failure {i}: `{method}()`\n"
            prompt += f"**Exception**: `{error_type}`\n"
            prompt += f"**Message**: {error_msg}\n"
            if stacktrace:
                prompt += f"**Stack trace**:\n```\n{stacktrace}\n```\n"
            prompt += "\n"

    # Format other errors
    if other_errors:
        prompt += f"## Other Errors ({len(other_errors)}):\n\n"
        for i, err in enumerate(other_errors, 1):
            error_msg = err.get('error', '')
            if len(error_msg) > 500:
                error_msg = error_msg[:500] + "... (truncated)"
            prompt += f"### Error {i}:\n```\n{error_msg}\n```\n\n"

    # Add source code context for the class being tested
    source_path = _find_source_file_for_test(test_path, project_path)
    if source_path:
        try:
            full_source_path = Path(project_path) / source_path
            if full_source_path.exists():
                source_content = full_source_path.read_text(encoding="utf-8")
                lines = source_content.split("\n")
                if len(lines) > 500:
                    source_content = "\n".join(lines[:500]) + "\n// ... (truncated)"
                prompt += "## Source class being tested:\n\n"
                prompt += f"### {source_path}\n```java\n{source_content}\n```\n\n"
        except Exception as e:
            logger.debug("source_file_read_error", path=source_path, error=str(e))

    # Add source code of classes referenced in errors (domain, model, etc.)
    referenced_classes = _find_error_referenced_classes(file_errors, test_content, project_path)
    if referenced_classes:
        prompt += referenced_classes + "\n"

    # Add the current test file
    prompt += "## Current test file to fix:\n\n"
    prompt += f"### {test_path}\n```java\n{test_content}\n```\n\n"

    # Build instructions based on error types
    total_errors = len(file_errors)
    error_type_desc = "errors"
    if runtime_errors and not compilation_errors:
        error_type_desc = "runtime test failures"
    elif compilation_errors and not runtime_errors:
        error_type_desc = "compilation errors"

    prompt += f"""## Instructions:

1. Fix ALL {total_errors} {error_type_desc} listed above for `{file_name}`
2. Use ONLY methods and types that exist in the source classes shown above
3. Return the COMPLETE fixed `{file_name}` in a single ```java code block
4. Do NOT omit any test methods - return the full class
"""

    if runtime_errors:
        prompt += """
**For Runtime Failures:**
- Read the stack trace to understand WHERE and WHY the test failed
- **CRITICAL for NullPointerException:** If passing null to a method causes NPE, do NOT use
  assertNull(result). Instead use assertThrows:
  ```java
  assertThrows(NullPointerException.class, () -> service.method(null));
  ```
- Check that mock setup matches what the tested method actually calls
- When using Mockito matchers, ALL arguments must use matchers (don't mix raw values with any()):
  ```java
  // WRONG: verify(repo).save(any(), 123L);
  // RIGHT: verify(repo).save(any(), eq(123L));
  ```
- Use the EXACT field types from source classes. If a field is Double, use 100.0, NOT BigDecimal.valueOf(100)
- Verify that test data is consistent with the source code logic
"""

    if compilation_errors:
        prompt += """
**For Compilation Errors:**
- Apply the exact fix suggested for each error
- Use the EXACT types specified (not approximations)
"""

    prompt += f"""
**CRITICAL: Check the source classes above before using any method or field.**
Do NOT invent methods. Use only what is declared in the source code or generated
by annotations visible in the source (e.g. @Data, @Getter, @Setter, @Builder).

IMPORTANT: Return ONLY the complete corrected `{file_name}`. No other files.
"""

    return prompt


def _get_project_context(project_path: str) -> str:
    """Extract technical context from the project (pom.xml, Java version, frameworks).

    Reads pom.xml to extract key information the LLM needs to generate correct code:
    Java version, Spring Boot version, key dependencies, Lombok usage, etc.

    Args:
        project_path: Root directory of the Java project

    Returns:
        Formatted string with project context for LLM prompt
    """
    import xml.etree.ElementTree as ET

    project_dir = Path(project_path)
    pom_file = project_dir / "pom.xml"

    if not pom_file.exists():
        return ""

    try:
        tree = ET.parse(pom_file)
        root = tree.getroot()
        ns = {"m": "http://maven.apache.org/POM/4.0.0"}

        context_parts = ["## Project Technical Context\n"]

        # Java version
        props = root.find("m:properties", ns) or root.find("properties")
        java_version = None
        if props is not None:
            for tag in ["m:java.version", "java.version", "m:maven.compiler.source", "maven.compiler.source"]:
                el = props.find(tag, ns) if tag.startswith("m:") else props.find(tag)
                if el is not None and el.text:
                    java_version = el.text
                    break
        if java_version:
            context_parts.append(f"- **Java version**: {java_version}")

        # Spring Boot version (from parent)
        parent = root.find("m:parent", ns)
        if parent is None:
            parent = root.find("parent")
        if parent is not None:
            parent_artifact = parent.find("m:artifactId", ns)
            if parent_artifact is None:
                parent_artifact = parent.find("artifactId")
            parent_version = parent.find("m:version", ns)
            if parent_version is None:
                parent_version = parent.find("version")
            if parent_artifact is not None and "spring-boot" in (parent_artifact.text or ""):
                context_parts.append(f"- **Spring Boot version**: {parent_version.text if parent_version is not None else 'unknown'}")

        # Key dependencies
        deps = []
        for dep in root.findall(".//m:dependency", ns):
            artifact = dep.find("m:artifactId", ns)
            version = dep.find("m:version", ns)
            if artifact is not None:
                name = artifact.text
                ver = version.text if version is not None else "managed"
                deps.append((name, ver))

        # Fallback without namespace
        if not deps:
            for dep in root.findall(".//dependency"):
                artifact = dep.find("artifactId")
                version = dep.find("version")
                if artifact is not None:
                    name = artifact.text
                    ver = version.text if version is not None else "managed"
                    deps.append((name, ver))

        # Show relevant dependencies
        key_deps = []
        for name, ver in deps:
            if any(k in name for k in ["lombok", "junit", "mockito", "spring-boot-starter-test",
                                        "spring-boot-starter-data-jpa", "spring-boot-starter-web",
                                        "assertj", "h2"]):
                key_deps.append(f"  - {name} ({ver})")

        if key_deps:
            context_parts.append("- **Key dependencies**:")
            context_parts.extend(key_deps)

        context_parts.append("")
        return "\n".join(context_parts)

    except Exception as e:
        logger.debug("project_context_extraction_error", error=str(e))
        return ""


def _find_error_referenced_classes(
    errors: list[dict[str, Any]],
    test_content: str,
    project_path: str,
) -> str:
    """Find and return source code of classes referenced in compilation errors.

    When the LLM generates incorrect method calls (e.g. setBalance instead of
    setAccountBalance), it needs to see the actual class source to fix them.
    This function extracts class names from error messages and test imports,
    then returns their source code.

    Args:
        errors: Compilation errors for a single test file
        test_content: Current content of the test file
        project_path: Root directory of the Java project

    Returns:
        Formatted string with referenced class sources for LLM prompt
    """
    project_dir = Path(project_path)
    referenced_classes: set[str] = set()

    # Extract class names from error "location" and "symbol" fields
    for err in errors:
        symbol = err.get("symbol", "") or ""
        error_msg = err.get("error", "") or ""

        # Extract from "location: class com.example.Foo"
        location_match = re.search(r"class\s+([\w.]+)", error_msg)
        if location_match:
            fqcn = location_match.group(1)
            referenced_classes.add(fqcn.split(".")[-1])

        # Extract from symbol info like "method setBalance()" -> class referenced in location
        location_match2 = re.search(r"location:\s+class\s+([\w.]+)", error_msg)
        if location_match2:
            referenced_classes.add(location_match2.group(1).split(".")[-1])

        # Extract from "cannot find symbol" with method name -> look at imports
        if "method" in symbol.lower():
            # The class is in the error location, already captured above
            pass

        # Extract from incompatible types -> the class that declares the expected type
        if err.get("error_type") == "incompatible_types":
            # We need the class whose method expects this type - check test imports
            pass

    # Also extract classes from test file imports (domain/model classes only)
    import_pattern = re.compile(r"^import\s+([\w.]+);", re.MULTILINE)
    for match in import_pattern.finditer(test_content):
        fqcn = match.group(1)
        # Only include project classes (skip java.*, org.junit.*, org.mockito.*, etc.)
        if not any(fqcn.startswith(prefix) for prefix in [
            "java.", "javax.", "jakarta.",
            "org.junit", "org.mockito", "org.assertj", "org.hamcrest",
            "org.springframework.test", "org.springframework.beans",
            "org.springframework.boot.test",
        ]):
            class_name = fqcn.split(".")[-1]
            referenced_classes.add(class_name)

    if not referenced_classes:
        return ""

    # Find source files for referenced classes
    source_contents = []
    src_dirs = get_source_directories(project_dir)

    found_classes: set[str] = set()
    for src_dir in src_dirs:
        if not src_dir.exists():
            continue
        for java_file in src_dir.rglob("*.java"):
            class_name = java_file.stem
            if class_name in referenced_classes and class_name not in found_classes:
                try:
                    content = java_file.read_text(encoding="utf-8")
                    # Limit to 200 lines to avoid context overflow
                    lines = content.split("\n")
                    if len(lines) > 200:
                        content = "\n".join(lines[:200]) + "\n// ... (truncated)"
                    rel_path = java_file.relative_to(project_dir)
                    source_contents.append(f"### {rel_path}\n```java\n{content}\n```\n")
                    found_classes.add(class_name)
                except Exception:
                    pass

    if not source_contents:
        return ""

    result = "## Referenced classes (from errors and imports):\n\n"
    result += "\n".join(source_contents)
    return result


def _try_fix_truncated_java(code: str) -> str:
    """Attempt to fix Java code that was truncated by the LLM.

    Adds missing closing braces if the code has unbalanced braces.

    Args:
        code: Potentially truncated Java code

    Returns:
        Fixed code with balanced braces
    """
    open_braces = code.count("{")
    close_braces = code.count("}")
    missing = open_braces - close_braces

    if missing > 0:
        logger.info("auto_fixing_truncated_java", missing_braces=missing)
        code = code.rstrip()
        if not code.endswith("\n"):
            code += "\n"
        for _ in range(missing):
            code += "}\n"

    return code


__all__ = [
    "run_test_generation_with_agent",
    "TestGenerationError",
    "CompilationError",
]
