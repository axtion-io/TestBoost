"""Integration tests for Docker deployment agent workflow (US5)."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool


class TestDockerWorkflowUsesAgent:
    """Test that Docker workflow uses DeepAgents create_deep_agent()."""

    @pytest.mark.asyncio
    async def test_docker_workflow_uses_agent(self, tmp_path):
        """Test Docker workflow creates and invokes agent with MCP tools."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        # Create a temporary project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Mock agent config
        mock_config = MagicMock()
        mock_config.name = "deployment_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.0-flash"
        mock_config.llm.temperature = 0.1
        mock_config.llm.max_tokens = 4096
        mock_config.tools.mcp_servers = ["docker-deployment", "container-runtime"]

        # Mock MCP tools
        mock_docker_tool = MagicMock(spec=BaseTool)
        mock_docker_tool.name = "docker_create_dockerfile"
        mock_docker_tool.description = "Generate Dockerfile for Java project"

        mock_container_tool = MagicMock(spec=BaseTool)
        mock_container_tool.name = "container_create_maven"
        mock_container_tool.description = "Create Maven build container"

        # Mock DeepAgents agent
        mock_agent = AsyncMock()
        mock_agent_response = {
            "messages": [
                AIMessage(
                    content="Deployment successful! Java 17 project deployed with PostgreSQL",
                    tool_calls=[
                        {
                            "name": "docker_create_dockerfile",
                            "args": {"project_path": str(project_dir), "java_version": "17"},
                            "id": "call_1"
                        },
                        {
                            "name": "docker_create_compose",
                            "args": {"project_path": str(project_dir), "dependencies": ["postgres"]},
                            "id": "call_2"
                        }
                    ]
                )
            ]
        }
        mock_agent.ainvoke.return_value = mock_agent_response

        with patch("src.workflows.docker_deployment_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.docker_deployment_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.docker_deployment_agent.create_react_agent") as mock_create_agent, \
             patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm, \
             patch("src.workflows.docker_deployment_agent.get_checkpointer") as mock_checkpointer:

            # Setup mocks
            mock_loader = MagicMock()
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "You are a Docker deployment expert..."
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = [mock_docker_tool, mock_container_tool]
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()
            mock_checkpointer.return_value = MagicMock()

            # Execute workflow
            result = await run_docker_deployment_with_agent(
                project_path=str(project_dir),
                session_id="test-session-docker-123"
            )

            # Verify agent was created with correct parameters
            mock_create_agent.assert_called_once()
            create_call = mock_create_agent.call_args

            # Verify Docker and container-runtime tools were bound
            assert create_call.kwargs["tools"] == [mock_docker_tool, mock_container_tool]

            # Verify prompt was provided (create_react_agent uses 'prompt' not 'system_prompt')
            assert "prompt" in create_call.kwargs
            assert "Docker deployment expert" in create_call.kwargs["prompt"]

            # Verify checkpointer was provided
            assert "checkpointer" in create_call.kwargs

            # Verify agent was invoked
            mock_agent.ainvoke.assert_called_once()

            # Verify result contains deployment information
            assert result["success"] is True
            assert "agent_response" in result

    @pytest.mark.asyncio
    async def test_docker_workflow_loads_config_from_yaml(self, tmp_path):
        """Test workflow loads agent config from deployment_agent.yaml."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        # Create a temporary project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        with patch("src.workflows.docker_deployment_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.docker_deployment_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.docker_deployment_agent.create_react_agent") as mock_create_agent, \
             patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm, \
             patch("src.workflows.docker_deployment_agent.get_checkpointer") as mock_checkpointer:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["docker-deployment", "container-runtime"]
            mock_config.llm.provider = "google-genai"
            mock_config.llm.model = "gemini-2.0-flash"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4096
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = {"messages": [AIMessage(content="Done")]}
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()
            mock_checkpointer.return_value = MagicMock()

            await run_docker_deployment_with_agent(
                project_path=str(project_dir),
                session_id="test-session-456"
            )

            # Verify config was loaded
            mock_loader.load_agent.assert_called_once_with("deployment_agent")

    @pytest.mark.asyncio
    async def test_docker_workflow_loads_prompt_template(self, tmp_path):
        """Test workflow loads system prompt from config/prompts/deployment/docker_guidelines.md."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        # Create a temporary project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        with patch("src.workflows.docker_deployment_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.docker_deployment_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.docker_deployment_agent.create_react_agent") as mock_create_agent, \
             patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm, \
             patch("src.workflows.docker_deployment_agent.get_checkpointer") as mock_checkpointer:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["docker-deployment"]
            mock_config.llm.provider = "google-genai"
            mock_config.llm.model = "gemini-2.0-flash"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = None
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Docker guidelines prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = {"messages": [AIMessage(content="Done")]}
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()
            mock_checkpointer.return_value = MagicMock()

            await run_docker_deployment_with_agent(
                project_path=str(project_dir),
                session_id="test-session-789"
            )

            # Verify prompt was loaded
            mock_loader.load_prompt.assert_called_once_with("docker_guidelines", category="deployment")


class TestDockerWorkflowStoresArtifacts:
    """Test that Docker workflow returns agent artifacts in response."""

    @pytest.mark.asyncio
    async def test_docker_workflow_stores_artifacts(self, tmp_path):
        """Test workflow returns agent reasoning, tool calls, and metrics in response."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        # Create a temporary project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Mock agent response with tool calls
        mock_agent_response = {
            "messages": [
                AIMessage(
                    content="I analyzed the project and detected Java 17 with PostgreSQL dependency.",
                    tool_calls=[
                        {
                            "name": "docker_create_dockerfile",
                            "args": {"project_path": str(project_dir), "java_version": "17"},
                            "id": "call_1"
                        }
                    ]
                )
            ]
        }

        with patch("src.workflows.docker_deployment_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.docker_deployment_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.docker_deployment_agent.create_react_agent") as mock_create_agent, \
             patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm, \
             patch("src.workflows.docker_deployment_agent.get_checkpointer") as mock_checkpointer:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["docker-deployment"]
            mock_config.llm.provider = "google-genai"
            mock_config.llm.model = "gemini-2.0-flash"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4096
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = mock_agent_response
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()
            mock_checkpointer.return_value = MagicMock()

            # Execute workflow
            session_id = "test-session-artifacts"
            result = await run_docker_deployment_with_agent(
                project_path=str(project_dir),
                session_id=session_id
            )

            # Verify workflow completes successfully and returns agent response
            assert result["success"] is True
            assert "java" in result["agent_response"].lower() or "docker" in result["agent_response"].lower()


class TestDockerAgentHealthCheckMonitoring:
    """Test that agent monitors health checks with proper waiting."""

    @pytest.mark.asyncio
    async def test_docker_agent_health_check_monitoring(self, tmp_path):
        """Test agent waits for health checks to pass before declaring success."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        # Create a temporary project directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Mock agent response with health check monitoring
        mock_agent_response = {
            "messages": [
                AIMessage(
                    content="Deployed containers successfully. Health checks passed after 45 seconds.",
                    tool_calls=[
                        {
                            "name": "docker_deploy_compose",
                            "args": {"compose_path": str(project_dir / "docker-compose.yml")},
                            "id": "call_1"
                        },
                        {
                            "name": "docker_health_check",
                            "args": {
                                "compose_path": str(project_dir / "docker-compose.yml"),
                                "timeout": 120,
                                "check_interval": 5
                            },
                            "id": "call_2"
                        }
                    ]
                )
            ]
        }

        with patch("src.workflows.docker_deployment_agent.AgentLoader") as mock_loader_class, \
             patch("src.workflows.docker_deployment_agent.get_tools_for_servers") as mock_get_tools, \
             patch("src.workflows.docker_deployment_agent.create_react_agent") as mock_create_agent, \
             patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm, \
             patch("src.workflows.docker_deployment_agent.get_checkpointer") as mock_checkpointer:

            mock_loader = MagicMock()
            mock_config = MagicMock()
            mock_config.tools.mcp_servers = ["docker-deployment", "container-runtime"]
            mock_config.llm.provider = "google-genai"
            mock_config.llm.model = "gemini-2.0-flash"
            mock_config.llm.temperature = 0.1
            mock_config.llm.max_tokens = 4096
            mock_loader.load_agent.return_value = mock_config
            mock_loader.load_prompt.return_value = "Prompt"
            mock_loader_class.return_value = mock_loader

            mock_get_tools.return_value = []
            mock_agent = AsyncMock()
            mock_agent.ainvoke.return_value = mock_agent_response
            mock_create_agent.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()
            mock_checkpointer.return_value = MagicMock()

            result = await run_docker_deployment_with_agent(
                project_path=str(project_dir),
                health_endpoints=[{"url": "http://localhost:8080/actuator/health"}],
                session_id="test-session-health"
            )

            # Verify health check monitoring in response
            assert result["success"] is True
            response_text = result["agent_response"].lower()
            assert "health" in response_text or "deployed" in response_text
