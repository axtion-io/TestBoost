"""
Integration tests for test generation agent workflow.

Tests implement T050-T053 from 002-deepagents-integration tasks.md.
Validates real LLM agent integration following TDD approach.
"""

import asyncio
import json
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from src.workflows.test_generation_agent import (
    CompilationError,
    TestGenerationError,
    run_test_generation_with_agent,
)


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.fixture
def sample_session_id():
    """Create a sample session UUID."""
    return uuid.uuid4()


@pytest.fixture
def sample_project_path(tmp_path):
    """Create a sample Java project structure."""
    project_dir = tmp_path / "sample-project"
    project_dir.mkdir()

    # Create source file
    src_dir = project_dir / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)
    (src_dir / "Calculator.java").write_text(
        """
package com.example;

public class Calculator {
    public int add(int a, int b) {
        return a + b;
    }

    public int subtract(int a, int b) {
        return a - b;
    }
}
"""
    )

    # Create test directory
    test_dir = project_dir / "src" / "test" / "java" / "com" / "example"
    test_dir.mkdir(parents=True)

    return str(project_dir)


class TestTestGenerationWorkflowUsesAgent:
    """Test T050: Verify test generation workflow uses agent."""

    @pytest.mark.asyncio
    @patch("src.workflows.test_generation_agent.create_deep_agent")
    @patch("src.workflows.test_generation_agent.get_llm")
    @patch("src.workflows.test_generation_agent.get_tools_for_servers")
    @patch("src.workflows.test_generation_agent.AgentLoader")
    async def test_workflow_creates_deep_agent(
        self,
        mock_loader_class,
        mock_get_tools,
        mock_get_llm,
        mock_create_agent,
        mock_db_session,
        sample_session_id,
        sample_project_path,
    ):
        """
        Verify workflow creates DeepAgents agent with correct configuration.

        Success criteria:
        - create_deep_agent() called with model, system_prompt, tools
        - Agent config loaded from test_gen_agent.yaml
        - System prompt loaded from unit_test_strategy.md
        - Tools loaded from MCP servers (test-generator, maven-maintenance, pit-recommendations)
        """
        # Setup mocks
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.name = "test_gen_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.5-flash-preview-09-2025"
        mock_config.llm.temperature = 0.2
        mock_config.llm.max_tokens = 8192
        mock_config.tools.mcp_servers = ["test-generator", "maven-maintenance", "pit-recommendations"]
        mock_config.error_handling.timeout_seconds = 180
        mock_config.error_handling.max_retries = 3

        mock_loader.load_agent.return_value = mock_config
        mock_loader.load_prompt.return_value = "System prompt for test generation"
        mock_loader_class.return_value = mock_loader

        mock_tools = [MagicMock(), MagicMock(), MagicMock()]
        mock_get_tools.return_value = mock_tools

        mock_llm = MagicMock()
        mock_get_llm.return_value = mock_llm

        mock_agent = AsyncMock()
        mock_agent.ainvoke = AsyncMock(
            return_value=AIMessage(
                content="""Analyzed project. Generating tests.

```java
package com.example;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class CalculatorTest {
    @Test
    void shouldAddNumbers() {
        Calculator calc = new Calculator();
        assertThat(calc.add(2, 3)).isEqualTo(5);
    }
}
```"""
            )
        )
        mock_create_agent.return_value = mock_agent

        # Execute workflow
        result = await run_test_generation_with_agent(
            session_id=sample_session_id,
            project_path=sample_project_path,
            db_session=mock_db_session,
        )

        # Verify agent creation
        mock_create_agent.assert_called_once()
        call_kwargs = mock_create_agent.call_args[1]
        assert call_kwargs["model"] == mock_llm
        assert "System prompt for test generation" in call_kwargs["system_prompt"]
        assert call_kwargs["tools"] == mock_tools

        # Verify configuration loaded
        mock_loader.load_agent.assert_called_once_with("test_gen_agent")
        mock_loader.load_prompt.assert_called_once_with("unit_test_strategy", category="testing")

        # Verify tools loaded from correct servers
        mock_get_tools.assert_called_once_with(
            ["test-generator", "maven-maintenance", "pit-recommendations"]
        )

        # Verify success
        assert result["success"] is True
        assert result["agent_name"] == "test_gen_agent"


class TestTestGenerationWorkflowStoresArtifacts:
    """Test T051: Verify workflow stores artifacts."""

    @pytest.mark.asyncio
    @patch("src.workflows.test_generation_agent.create_deep_agent")
    @patch("src.workflows.test_generation_agent.get_llm")
    @patch("src.workflows.test_generation_agent.get_tools_for_servers")
    @patch("src.workflows.test_generation_agent.AgentLoader")
    @patch("src.workflows.test_generation_agent.ArtifactRepository")
    async def test_workflow_stores_agent_reasoning(
        self,
        mock_artifact_repo_class,
        mock_loader_class,
        mock_get_tools,
        mock_get_llm,
        mock_create_agent,
        mock_db_session,
        sample_session_id,
        sample_project_path,
    ):
        """
        Verify workflow stores agent reasoning in artifacts.

        Success criteria:
        - artifact_type="agent_reasoning" stored with agent response
        - artifact_type="llm_tool_call" stored for each tool invocation
        - artifact_type="llm_metrics" stored with tokens, duration, cost
        """
        # Setup mocks
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.name = "test_gen_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.5-flash-preview-09-2025"
        mock_config.llm.temperature = 0.2
        mock_config.llm.max_tokens = 8192
        mock_config.tools.mcp_servers = ["test-generator"]
        mock_config.error_handling.timeout_seconds = 180
        mock_config.error_handling.max_retries = 3

        mock_loader.load_agent.return_value = mock_config
        mock_loader.load_prompt.return_value = "System prompt"
        mock_loader_class.return_value = mock_loader

        mock_get_tools.return_value = []
        mock_get_llm.return_value = MagicMock()

        # Mock agent response with reasoning
        mock_agent = AsyncMock()
        mock_response = AIMessage(content="Analysis complete. Generated tests.")
        mock_response.usage_metadata = MagicMock(
            input_tokens=1500,
            output_tokens=500,
            total_tokens=2000,
        )
        mock_agent.ainvoke = AsyncMock(return_value=mock_response)
        mock_create_agent.return_value = mock_agent

        # Mock artifact repository
        mock_artifact_repo = AsyncMock()
        mock_artifact_repo.create = AsyncMock()
        mock_artifact_repo_class.return_value = mock_artifact_repo

        # Execute workflow
        result = await run_test_generation_with_agent(
            session_id=sample_session_id,
            project_path=sample_project_path,
            db_session=mock_db_session,
        )

        # Verify artifacts stored
        assert mock_artifact_repo.create.call_count >= 2  # At least reasoning + metrics

        # Check artifact types
        artifact_calls = mock_artifact_repo.create.call_args_list
        artifact_types = [call[1]["artifact_type"] for call in artifact_calls]

        assert "agent_reasoning" in artifact_types
        assert "llm_metrics" in artifact_types

        # Verify reasoning artifact contains agent response
        reasoning_call = next(
            call for call in artifact_calls if call[1]["artifact_type"] == "agent_reasoning"
        )
        assert reasoning_call[1]["session_id"] == sample_session_id

        # Verify metrics artifact contains token counts
        metrics_call = next(
            call for call in artifact_calls if call[1]["artifact_type"] == "llm_metrics"
        )
        assert metrics_call[1]["session_id"] == sample_session_id


class TestTestGenerationAgentToolCallRetry:
    """Test T053: Verify agent retry logic for error correction."""

    @pytest.mark.asyncio
    @patch("src.workflows.test_generation_agent.create_deep_agent")
    @patch("src.workflows.test_generation_agent.get_llm")
    @patch("src.workflows.test_generation_agent.get_tools_for_servers")
    @patch("src.workflows.test_generation_agent.AgentLoader")
    async def test_agent_retries_on_compilation_errors(
        self,
        mock_loader_class,
        mock_get_tools,
        mock_get_llm,
        mock_create_agent,
        mock_db_session,
        sample_session_id,
        sample_project_path,
    ):
        """
        Verify agent retries with auto-correction when tests fail to compile.

        Success criteria (A2 edge case):
        - Max 3 correction attempts for compilation errors
        - Agent invoked with error details for correction
        - Compilation errors stored as artifacts
        - Final result indicates compilation status
        """
        # Setup mocks
        mock_loader = MagicMock()
        mock_config = MagicMock()
        mock_config.name = "test_gen_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.5-flash-preview-09-2025"
        mock_config.llm.temperature = 0.2
        mock_config.llm.max_tokens = 8192
        mock_config.tools.mcp_servers = ["test-generator"]
        mock_config.error_handling.timeout_seconds = 180
        mock_config.error_handling.max_retries = 3

        mock_loader.load_agent.return_value = mock_config
        mock_loader.load_prompt.return_value = "System prompt"
        mock_loader_class.return_value = mock_loader

        mock_get_tools.return_value = []
        mock_get_llm.return_value = MagicMock()

        # Mock agent to return test with syntax error first, then corrected
        mock_agent = AsyncMock()
        responses = [
            # First response: test with error (missing closing brace)
            AIMessage(
                content="""```java
package com.example;

import org.junit.jupiter.api.Test;

class CalculatorTest {
    @Test
    void shouldAdd() {
        // Missing closing brace
```"""
            ),
            # Second response: corrected test
            AIMessage(
                content="""```java
package com.example;

import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class CalculatorTest {
    @Test
    void shouldAdd() {
        Calculator calc = new Calculator();
        assertThat(calc.add(2, 3)).isEqualTo(5);
    }
}
```"""
            ),
        ]

        mock_agent.ainvoke = AsyncMock(side_effect=responses)
        mock_create_agent.return_value = mock_agent

        # Execute workflow
        result = await run_test_generation_with_agent(
            session_id=sample_session_id,
            project_path=sample_project_path,
            db_session=mock_db_session,
        )

        # Verify agent invoked multiple times for correction
        assert mock_agent.ainvoke.call_count >= 2

        # Verify result includes compilation status
        assert "generated_tests" in result
        if result["generated_tests"]:
            test = result["generated_tests"][0]
            assert "compiles" in test
            assert "correction_attempts" in test


@pytest.mark.asyncio
@patch("src.workflows.test_generation_agent.create_deep_agent")
@patch("src.workflows.test_generation_agent.get_llm")
@patch("src.workflows.test_generation_agent.get_tools_for_servers")
@patch("src.workflows.test_generation_agent.AgentLoader")
async def test_workflow_raises_error_on_llm_failure(
    mock_loader_class,
    mock_get_tools,
    mock_get_llm,
    mock_create_agent,
    mock_db_session,
    sample_session_id,
    sample_project_path,
):
    """
    Verify workflow handles LLM failures gracefully.

    Success criteria:
    - TestGenerationError raised on agent failure
    - Error message includes original exception
    - Session status updated to failed
    """
    # Setup mocks
    mock_loader = MagicMock()
    mock_config = MagicMock()
    mock_config.name = "test_gen_agent"
    mock_config.llm.provider = "google-genai"
    mock_config.llm.model = "gemini-2.5-flash-preview-09-2025"
    mock_config.llm.temperature = 0.2
    mock_config.llm.max_tokens = 8192
    mock_config.tools.mcp_servers = ["test-generator"]
    mock_config.error_handling.timeout_seconds = 180
    mock_config.error_handling.max_retries = 3

    mock_loader.load_agent.return_value = mock_config
    mock_loader.load_prompt.return_value = "System prompt"
    mock_loader_class.return_value = mock_loader

    mock_get_tools.return_value = []
    mock_get_llm.return_value = MagicMock()

    # Mock agent to raise error
    mock_agent = AsyncMock()
    mock_agent.ainvoke = AsyncMock(side_effect=Exception("LLM connection failed"))
    mock_create_agent.return_value = mock_agent

    # Execute workflow and expect error
    with pytest.raises(TestGenerationError) as exc_info:
        await run_test_generation_with_agent(
            session_id=sample_session_id,
            project_path=sample_project_path,
            db_session=mock_db_session,
        )

    # Verify error message
    assert "Test generation failed" in str(exc_info.value)
    assert "LLM connection failed" in str(exc_info.value)
