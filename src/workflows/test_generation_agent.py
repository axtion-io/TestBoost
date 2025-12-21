"""
Test Generation Workflow with DeepAgents LLM Integration.

Implements User Story 4 (US4) from 002-deepagents-integration:
- Real LLM agent for test generation analysis
- Auto-correction retry logic for compilation errors (A2: max 3 attempts)
- Tool-based project context analysis
- Artifact storage for agent reasoning and metrics

Tasks implemented: T054-T064
"""

import asyncio
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.agents.loader import AgentLoader
from src.db.repository import ArtifactRepository, SessionRepository
from src.lib.config import get_settings
from src.lib.llm import LLMError, get_llm
from src.lib.logging import get_logger
from src.mcp_servers.registry import get_tools_for_servers
from src.models.impact import TestRequirement

logger = get_logger(__name__)
settings = get_settings()

# Retry configuration for auto-correction (A2 edge case)
MAX_CORRECTION_RETRIES = 3
MIN_WAIT = 1
MAX_WAIT = 5

# Feedback loop configuration - run tests and fix until passing
MAX_TEST_ITERATIONS = 5  # Maximum attempts to fix failing tests
TEST_TIMEOUT_SECONDS = 300  # 5 minutes timeout for Maven test run


class TestGenerationError(Exception):
    """Base exception for test generation errors."""

    pass


class CompilationError(TestGenerationError):
    """Raised when generated tests fail to compile."""

    pass


async def run_test_generation_with_agent(
    session_id: UUID,
    project_path: str,
    db_session: Any,
    source_files: list[str] | None = None,
    coverage_target: float = 80.0,
    test_requirements: list[TestRequirement] | None = None,
) -> dict[str, Any]:
    """
    Run test generation workflow using DeepAgents LLM agent.

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

    Returns:
        dict with workflow results including generated tests and metrics

    Raises:
        TestGenerationError: If generation fails after retries
        LLMError: If LLM connection issues persist
    """
    start_time = time.time()
    logger.info(
        "test_gen_workflow_start",
        session_id=str(session_id),
        project_path=project_path,
        coverage_target=coverage_target,
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

    # Build test requirements section if provided from impact analysis
    requirements_section = ""
    if test_requirements:
        requirements_section = "\n\n## Test Requirements from Impact Analysis\n\n"
        requirements_section += "The following specific tests MUST be generated based on code impact analysis:\n\n"
        for req in test_requirements:
            requirements_section += f"- **{req.suggested_test_name or req.id}** ({req.test_type.value}, {req.scenario_type.value}, P{req.priority}):\n"
            requirements_section += f"  - Target: `{req.target_class}`"
            if req.target_method:
                requirements_section += f".{req.target_method}()"
            requirements_section += f"\n  - Description: {req.description}\n"

    # Prepare agent input
    agent_input = {
        "messages": [
            HumanMessage(
                content=f"""Analyze and generate unit tests for Java project at: {project_path}

Target coverage: {coverage_target}%
Source files: {source_files if source_files else 'all untested classes'}
{requirements_section}
## Instructions

1. First, use `test_gen_analyze_project` to understand project structure and frameworks
2. Use `test_gen_detect_conventions` to identify existing test patterns
3. Use `test_gen_generate_unit_tests` for each source file found, following conventions

{"## PRIORITY: Generate tests matching the Impact Analysis requirements above FIRST." if test_requirements else ""}

## CRITICAL OUTPUT REQUIREMENT

After using the tools, you MUST include ALL generated test code in your final response.
Format each test class in a separate ```java code block with the full test class content.

Example format:
```java
package com.example;

import org.junit.jupiter.api.Test;
// ... imports

class ExampleClassTest {{
    @Test
    void shouldTestMethod() {{
        // test implementation
    }}
}}
```

Generate tests for at least 3-5 classes from the project.
Include the complete test code for each class in separate ```java blocks."""
            )
        ]
    }

    try:
        # Invoke agent with retry logic (T059)
        response = await _invoke_agent_with_retry(
            agent=agent,
            input_data=agent_input,
            session_id=session_id,
            artifact_repo=artifact_repo,
        )

        # Store agent reasoning (T061)
        await _store_agent_reasoning(
            session_id=session_id,
            artifact_repo=artifact_repo,
            response=response,
            agent_name=config.name,
        )

        # Extract generated tests from response
        generated_tests = _extract_generated_tests(response)

        # Auto-correction retry logic (T060)
        if generated_tests:
            validated_tests = await _validate_and_correct_tests(
                session_id=session_id,
                artifact_repo=artifact_repo,
                agent=agent,
                generated_tests=generated_tests,
                project_path=project_path,
            )
        else:
            validated_tests = []

        # Write validated tests to disk
        written_tests = _write_tests_to_disk(project_path, validated_tests)
        for test in validated_tests:
            test["written_to_disk"] = test.get("path") in written_tests

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
        }

        # Store LLM metrics (T061)
        await _store_llm_metrics(
            session_id=session_id,
            artifact_repo=artifact_repo,
            metrics=metrics,
            response=response,
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


@retry(
    stop=stop_after_attempt(MAX_CORRECTION_RETRIES),
    wait=wait_exponential(multiplier=1, min=MIN_WAIT, max=MAX_WAIT),
    retry=retry_if_exception_type((ConnectionError, asyncio.TimeoutError)),
)
async def _invoke_agent_with_retry(
    agent: Any,
    input_data: dict[str, Any],
    session_id: UUID,
    artifact_repo: ArtifactRepository,
) -> dict[str, Any] | AIMessage:
    """
    Invoke agent with retry logic for transient failures (T059, A4 edge case).

    Retries on:
    - Network errors
    - Timeout errors

    Does NOT retry on:
    - Authentication errors
    - Rate limit errors (A1 edge case - fails immediately)

    Args:
        agent: DeepAgents agent instance
        input_data: Input messages and context
        session_id: Session UUID for artifact storage
        artifact_repo: Repository for storing tool calls

    Returns:
        Agent response (dict for LangGraph final state or AIMessage for single LLM call)

    Raises:
        LLMError: If invocation fails after retries
    """
    try:
        logger.debug("agent_invoke_start", session_id=str(session_id))
        # Set higher recursion limit to allow agent to complete complex tasks
        config = {"recursion_limit": 100}
        response = await agent.ainvoke(input_data, config)

        # Handle both dict (LangGraph state) and AIMessage responses
        if isinstance(response, dict):
            # LangGraph returns final state as dict with 'messages' key
            messages = response.get("messages", [])
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                    await _store_tool_calls(session_id, artifact_repo, last_message.tool_calls)
        elif hasattr(response, "tool_calls") and response.tool_calls:
            # Direct AIMessage response
            await _store_tool_calls(session_id, artifact_repo, response.tool_calls)

        logger.debug("agent_invoke_success", session_id=str(session_id))
        return response  # type: ignore[no-any-return]

    except ConnectionError as e:
        logger.warning("agent_invoke_connection_error", error=str(e))
        raise  # Will retry
    except TimeoutError as e:
        logger.warning("agent_invoke_timeout", error=str(e))
        raise  # Will retry
    except Exception as e:
        # Check for rate limit (A1 edge case - do NOT retry)
        error_msg = str(e)
        if "429" in error_msg or "rate limit" in error_msg.lower():
            logger.error("agent_rate_limited", error=error_msg)
            raise LLMError(f"LLM rate limit exceeded: {error_msg}") from e

        # Check for auth errors (do NOT retry)
        if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg.lower():
            logger.error("agent_auth_failed", error=error_msg)
            raise LLMError(f"LLM authentication failed: {error_msg}") from e

        # Re-raise as generic error
        logger.error("agent_invoke_failed", error=error_msg, error_type=type(e).__name__)
        raise LLMError(f"Agent invocation failed: {e}") from e


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

        correction_response = await _invoke_agent_with_retry(
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
                        pass
            except Exception:
                pass

    logger.debug("extracted_tests", count=len(tests))
    return tests


def _is_valid_test_code(code: str) -> bool:
    """Check if code is valid Java test code."""
    return (
        "class " in code
        and ("@Test" in code or "@ParameterizedTest" in code)
        and len(code) > 100  # Minimum reasonable test size
    )


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

    Args:
        project_path: Path to the Java project root
        validated_tests: List of validated test files with content

    Returns:
        List of file paths that were successfully written
    """
    written_files = []
    project_dir = Path(project_path)

    for test in validated_tests:
        # Only write tests that compiled successfully
        if not test.get("compiles", False):
            logger.warning(
                "skip_writing_failed_test",
                path=test.get("path"),
                reason="compilation_failed",
            )
            continue

        content = test.get("content")
        relative_path = test.get("path")

        if not content or not relative_path:
            continue

        # Build full path
        full_path = project_dir / relative_path

        try:
            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Write the test file
            full_path.write_text(content, encoding="utf-8")

            logger.info(
                "test_written_to_disk",
                path=str(full_path),
                size_bytes=len(content),
            )
            written_files.append(relative_path)

        except Exception as e:
            logger.error(
                "test_write_failed",
                path=str(full_path),
                error=str(e),
            )

    logger.info(
        "tests_write_complete",
        total=len(validated_tests),
        written=len(written_files),
    )

    return written_files


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
    current_tests = {t["path"]: t["content"] for t in validated_tests}

    for iteration in range(1, max_iterations + 1):
        logger.info(
            "test_feedback_iteration",
            session_id=str(session_id),
            iteration=iteration,
            max_iterations=max_iterations,
        )

        # Step 1: Run Maven tests
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

        fix_response = await _invoke_agent_with_retry(
            agent=agent,
            input_data={"messages": [HumanMessage(content=fix_prompt)]},
            session_id=session_id,
            artifact_repo=artifact_repo,
        )

        # Step 4: Extract and write corrected tests
        corrected_tests = _extract_generated_tests(fix_response)

        if not corrected_tests:
            logger.warning(
                "no_corrections_from_agent",
                session_id=str(session_id),
                iteration=iteration,
            )
            continue

        # Update current tests with corrections
        for corrected in corrected_tests:
            path = corrected.get("path")
            content = corrected.get("content")
            if path and content:
                current_tests[path] = content
                # Write to disk
                full_path = project_dir / path
                try:
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(content, encoding="utf-8")
                    logger.info(
                        "corrected_test_written",
                        path=str(full_path),
                        iteration=iteration,
                    )
                except Exception as e:
                    logger.error("corrected_test_write_failed", path=path, error=str(e))

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

    Args:
        project_dir: Path to the Maven project
        test_files: List of test file info dicts

    Returns:
        dict with success flag and output
    """
    # Find the module containing the tests (for multi-module projects)
    # First, try to find a pom.xml in the project directory
    pom_path = project_dir / "pom.xml"

    # Build test command
    if pom_path.exists():
        # Check if it's a multi-module project
        mvn_cmd = ["mvn", "test", "-f", str(pom_path)]
    else:
        # Look for pom.xml in subdirectories
        for subdir in project_dir.iterdir():
            if subdir.is_dir() and (subdir / "pom.xml").exists():
                mvn_cmd = ["mvn", "test", "-f", str(subdir / "pom.xml")]
                break
        else:
            return {
                "success": False,
                "output": "No pom.xml found in project",
                "return_code": -1,
            }

    # Add specific test classes if we know them
    test_classes = []
    for test_file in test_files:
        path = test_file.get("path", "")
        if path.endswith(".java"):
            # Extract class name from path
            class_name = Path(path).stem
            test_classes.append(class_name)

    if test_classes:
        # Run only the generated tests
        test_pattern = ",".join(test_classes)
        mvn_cmd.extend(["-Dtest=" + test_pattern, "-DfailIfNoTests=false"])

    logger.info("running_maven_tests", command=" ".join(mvn_cmd))

    try:
        result = subprocess.run(
            mvn_cmd,
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            timeout=TEST_TIMEOUT_SECONDS,
            shell=True,  # Required on Windows
        )

        success = result.returncode == 0
        output = result.stdout + "\n" + result.stderr

        logger.info(
            "maven_tests_complete",
            success=success,
            return_code=result.returncode,
        )

        return {
            "success": success,
            "output": output,
            "return_code": result.returncode,
        }

    except subprocess.TimeoutExpired:
        logger.error("maven_tests_timeout", timeout=TEST_TIMEOUT_SECONDS)
        return {
            "success": False,
            "output": f"Maven tests timed out after {TEST_TIMEOUT_SECONDS} seconds",
            "return_code": -1,
        }
    except Exception as e:
        logger.error("maven_tests_failed", error=str(e))
        return {
            "success": False,
            "output": str(e),
            "return_code": -1,
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
    failure_pattern = re.compile(
        r"(?:Failed tests?|Tests in error):\s*\n((?:\s+.+\n)+)",
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

    # Also look for compilation errors
    compile_error_pattern = re.compile(
        r"\[ERROR\]\s*(.+\.java):\[(\d+),(\d+)\]\s*(.+)",
        re.MULTILINE
    )

    for match in compile_error_pattern.finditer(maven_output):
        failures.append({
            "type": "compilation",
            "file": match.group(1),
            "line": int(match.group(2)),
            "column": int(match.group(3)),
            "error": match.group(4),
        })

    # Look for assertion failures with stack traces
    assertion_pattern = re.compile(
        r"(org\.opentest4j\.\w+|java\.lang\.AssertionError):\s*(.+?)(?=\n\tat|\n\n|$)",
        re.DOTALL
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

4. Return the COMPLETE fixed test files in ```java code blocks

IMPORTANT: Include the full corrected test class content, not just the changed parts.
Each test file should be in a separate ```java block with the complete class.
"""

    return prompt


__all__ = [
    "run_test_generation_with_agent",
    "TestGenerationError",
    "CompilationError",
]
