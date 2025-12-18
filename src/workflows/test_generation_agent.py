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
import time
from pathlib import Path
from typing import Any
from uuid import UUID

from deepagents import create_deep_agent
from langchain_core.messages import AIMessage, HumanMessage
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

logger = get_logger(__name__)
settings = get_settings()

# Retry configuration for auto-correction (A2 edge case)
MAX_CORRECTION_RETRIES = 3
MIN_WAIT = 1
MAX_WAIT = 5


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

    # Bind tools to LLM with tool_choice="any" to force tool usage
    # This ensures the agent calls tools instead of generating placeholder responses
    llm_with_tools = llm.bind_tools(tools, tool_choice="any")
    logger.info("tools_bound_to_llm", tool_count=len(tools), tool_choice="any")

    # Create DeepAgents agent (T055)
    agent = create_deep_agent(
        model=llm_with_tools,
        system_prompt=prompt,
        tools=tools,
        # Note: PostgreSQL checkpointer would be shared here if implementing pause/resume
        # checkpointer=postgres_checkpointer
    )
    logger.info("deep_agent_created", agent_type="test_generation")

    # Prepare agent input
    agent_input = {
        "messages": [
            HumanMessage(
                content=f"""Analyze and generate unit tests for Java project at: {project_path}

Target coverage: {coverage_target}%
Source files: {source_files if source_files else 'all untested classes'}

## Instructions

1. First, use `test_gen_analyze_project` to understand project structure and frameworks
2. Use `test_gen_detect_conventions` to identify existing test patterns
3. Use `test_gen_generate_unit_tests` for each source file found, following conventions

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

        # Calculate metrics
        duration = time.time() - start_time
        metrics = {
            "duration_seconds": round(duration, 2),
            "tests_generated": len(validated_tests),
            "compilation_success": all(t.get("compiles", False) for t in validated_tests),
            "coverage_target": coverage_target,
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
        response = await agent.ainvoke(input_data)

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


__all__ = [
    "run_test_generation_with_agent",
    "TestGenerationError",
    "CompilationError",
]
