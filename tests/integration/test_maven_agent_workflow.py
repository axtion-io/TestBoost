"""Integration tests for Maven maintenance agent workflow (US2)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import BaseTool

from src.db.models.session import SessionStatus


class TestMavenWorkflowUsesAgent:
    """Test that Maven workflow uses DeepAgents create_deep_agent()."""

    @pytest.mark.asyncio
    async def test_maven_workflow_uses_agent(self):
        """Test Maven workflow creates and invokes agent with MCP tools."""
        # This test will fail until implementation exists
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        # Mock agent loader
        mock_config = MagicMock()
        mock_config.name = "maven_maintenance_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.5-flash-preview-09-2025"
        mock_config.llm.temperature = 0.3
        mock_config.tools.mcp_servers = ["maven-maintenance", "git-maintenance"]
        mock_config.prompts.system = "config/prompts/maven/dependency_update.md"
        mock_config.error_handling.max_retries = 3

        # Mock MCP tools
        mock_maven_tool = MagicMock(spec=BaseTool)
        mock_maven_tool.name = "analyze_dependencies"
        mock_maven_tool.description = "Analyze project dependencies for updates"

        mock_git_tool = MagicMock(spec=BaseTool)
        mock_git_tool.name = "create_branch"
        mock_git_tool.description = "Create a new Git branch"

        # Mock DeepAgents create_deep_agent
        mock_agent = AsyncMock()
        mock_agent_response = AIMessage(
            content="Analyzed dependencies: 5 outdated, 2 vulnerable",
            tool_calls=[
                {
                    "name": "analyze_dependencies",
                    "args": {"project_path": "/test/project"},
                    "id": "call_1"
                }
            ]
        )
        mock_agent.ainvoke.return_value = mock_agent_response

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            # Setup mocks
            mock_loader = MagicMock()
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "You are a Maven expert..."
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = [mock_maven_tool, mock_git_tool]
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            # Execute workflow
            result = await run_maven_maintenance_with_agent(
                project_path="/test/project",
                session_id="test-session-123"
            )

            # Verify agent was created with correct parameters
            mock_create_agent.assert_called_once()
            create_call = mock_create_agent.call_args

            # Verify tools were bound
            assert create_call.kwargs["tools"] == [mock_maven_tool, mock_git_tool]

            # Verify agent was invoked
            mock_agent.ainvoke.assert_called_once()

            # Verify result contains agent response
            assert "dependencies" in result.lower()

    @pytest.mark.asyncio
    async def test_maven_workflow_loads_config_from_yaml(self):
        """Test workflow loads agent config from maven_maintenance_agent.yaml."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["maven-maintenance"]
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = AIMessage(content="Done")
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            await run_maven_maintenance_with_agent(
                project_path="/test/project",
                session_id="test-session-123"
            )

            # Verify config was loaded
            mock_loader.load_agent.assert_called_once_with("maven_maintenance_agent")

    @pytest.mark.asyncio
    async def test_maven_workflow_loads_prompt_template(self):
        """Test workflow loads system prompt from config/prompts/maven/dependency_update.md."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["maven-maintenance"]
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Maven expert prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = AIMessage(content="Done")
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            await run_maven_maintenance_with_agent(
                project_path="/test/project",
                session_id="test-session-123"
            )

            # Verify prompt was loaded
            mock_loader.load_prompt.assert_called_once_with("dependency_update", category="maven")


class TestMavenWorkflowStoresArtifacts:
    """Test that Maven workflow stores agent artifacts in database."""

    @pytest.mark.asyncio
    async def test_maven_workflow_stores_artifacts(self, db_session):
        """Test workflow stores agent reasoning, tool calls, and metrics as artifacts."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
        from src.db.repository import Repository

        # Mock agent response with tool calls
        mock_agent_response = AIMessage(
            content="I analyzed the dependencies and found 5 outdated packages.",
            tool_calls=[
                {
                    "name": "analyze_dependencies",
                    "args": {"project_path": "/test/project"},
                    "id": "call_1"
                }
            ]
        )

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            # Setup mocks
            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["maven-maintenance"]
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = mock_agent_response
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            # Execute workflow
            session_id = "test-session-456"
            await run_maven_maintenance_with_agent(
                project_path="/test/project",
                session_id=session_id
            )

            # Query artifacts from database
            repo = Repository(db_session)
            artifacts = await repo.list_artifacts(session_id=session_id)

            # Verify artifact types are stored
            artifact_types = [a.artifact_type for a in artifacts]
            assert "agent_reasoning" in artifact_types
            assert "llm_tool_call" in artifact_types
            assert "llm_metrics" in artifact_types

            # Verify reasoning artifact contains LLM response
            reasoning_artifact = next(a for a in artifacts if a.artifact_type == "agent_reasoning")
            assert "dependencies" in reasoning_artifact.content.lower()

            # Verify tool call artifact
            tool_call_artifact = next(a for a in artifacts if a.artifact_type == "llm_tool_call")
            assert tool_call_artifact.content["tool_name"] == "analyze_dependencies"

            # Verify metrics artifact
            metrics_artifact = next(a for a in artifacts if a.artifact_type == "llm_metrics")
            assert "total_tokens" in metrics_artifact.content or "duration_ms" in metrics_artifact.content

    @pytest.mark.asyncio
    async def test_maven_workflow_stores_multiple_tool_calls(self, db_session):
        """Test workflow stores multiple tool calls as separate artifacts."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
        from src.db.repository import Repository

        # Mock agent response with multiple tool calls
        mock_agent_response = AIMessage(
            content="Analyzed and created branch",
            tool_calls=[
                {
                    "name": "analyze_dependencies",
                    "args": {"project_path": "/test/project"},
                    "id": "call_1"
                },
                {
                    "name": "create_branch",
                    "args": {"branch_name": "update-deps"},
                    "id": "call_2"
                }
            ]
        )

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["maven-maintenance", "git-maintenance"]
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = mock_agent_response
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            session_id = "test-session-789"
            await run_maven_maintenance_with_agent(
                project_path="/test/project",
                session_id=session_id
            )

            repo = Repository(db_session)
            artifacts = await repo.list_artifacts(session_id=session_id)

            # Should have multiple tool call artifacts
            tool_call_artifacts = [a for a in artifacts if a.artifact_type == "llm_tool_call"]
            assert len(tool_call_artifacts) >= 2


class TestMavenAgentToolCallRetry:
    """Test agent retries if no tools are called (A2 edge case)."""

    @pytest.mark.asyncio
    async def test_maven_agent_tool_call_retry(self):
        """Test agent retries with modified prompt if no tools called."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        # First response: no tool calls
        first_response = AIMessage(content="Let me think about this...")

        # Second response: includes tool call
        second_response = AIMessage(
            content="Now analyzing dependencies",
            tool_calls=[
                {
                    "name": "analyze_dependencies",
                    "args": {"project_path": "/test/project"},
                    "id": "call_1"
                }
            ]
        )

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["maven-maintenance"]
            mock_config.error_handling.max_retries = 3
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            # First call returns no tools, second call returns tools
            mock_agent.ainvoke.side_effect = [first_response, second_response]
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            result = await run_maven_maintenance_with_agent(
                project_path="/test/project",
                session_id="test-session-retry"
            )

            # Verify agent was invoked twice (retry logic)
            assert mock_agent.ainvoke.call_count == 2

            # Verify final result includes tool call
            assert "analyzing" in result.lower() or "dependencies" in result.lower()

    @pytest.mark.asyncio
    async def test_maven_agent_fails_after_max_retries(self):
        """Test agent fails if no tools called after max retries."""
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        # Always return response without tool calls
        no_tools_response = AIMessage(content="I don't know what to do")

        with patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.maven_maintenance_agent.create_deep_agent") as mock_create_agent, \
             patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["maven-maintenance"]
            mock_config.error_handling.max_retries = 3
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = no_tools_response
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            # Should raise error after exhausting retries
            with pytest.raises(Exception) as exc_info:
                await run_maven_maintenance_with_agent(
                    project_path="/test/project",
                    session_id="test-session-fail"
                )

            # Verify error mentions missing tool calls
            assert "tool" in str(exc_info.value).lower() or "retry" in str(exc_info.value).lower()


# Fixtures
@pytest.fixture
async def db_session():
    """Provide a mock database session for testing."""
    # In real implementation, this would be a test database session
    # For now, mock it
    mock_session = MagicMock()
    return mock_session
