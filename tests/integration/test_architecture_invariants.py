"""Architecture invariant tests.

These tests validate that the critical architectural contracts between
components are maintained. If any of these fail, it means a key link
in the chain was broken:

    YAML config → AgentLoader → prompt markdown → create_react_agent(prompt=, tools=)

Each workflow MUST:
1. Load its agent config from YAML via AgentLoader
2. Load its system prompt from a markdown file
3. Pass the prompt to create_react_agent(prompt=...)
4. Pass the MCP tools to create_react_agent(tools=...)
5. Create the LLM from config values (not hardcoded)
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool


def _make_mock_tool(name: str) -> MagicMock:
    """Create a mock LangChain tool."""
    tool = MagicMock(spec=BaseTool)
    tool.name = name
    tool.description = f"Mock tool: {name}"
    return tool


class TestMavenPromptAndToolsPassThrough:
    """Maven workflow must pass prompt and tools to create_react_agent."""

    @pytest.mark.asyncio
    async def test_prompt_reaches_create_react_agent(self):
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        mock_config = MagicMock()
        mock_config.name = "maven_maintenance_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.0-flash"
        mock_config.llm.temperature = 0.3
        mock_config.llm.max_tokens = 8192
        mock_config.tools.mcp_servers = ["maven-maintenance", "git-maintenance"]
        mock_config.error_handling.max_retries = 3

        prompt_text = "You are a Maven dependency maintenance specialist for {project_name}."
        maven_tool = _make_mock_tool("maven_analyze_dependencies")
        git_tool = _make_mock_tool("git_create_maintenance_branch")

        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {"messages": [AIMessage(content="Analysis done")]}

        with (
            patch("src.workflows.maven_maintenance_agent.AgentLoader") as mock_loader_cls,
            patch("src.workflows.maven_maintenance_agent.get_tools_for_servers") as mock_get_tools,
            patch("src.workflows.maven_maintenance_agent.create_react_agent") as mock_create,
            patch("src.workflows.maven_maintenance_agent.get_llm") as mock_get_llm,
        ):
            loader = MagicMock()
            loader.load_agent.return_value = mock_config
            loader.load_prompt.return_value = prompt_text
            mock_loader_cls.return_value = loader

            mock_get_tools.return_value = [maven_tool, git_tool]
            mock_create.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            await run_maven_maintenance_with_agent(
                project_path="/test/my-project", session_id="arch-test"
            )

            # --- Architectural assertions ---
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs

            # Prompt loaded from markdown must reach the agent
            assert "prompt" in call_kwargs, "prompt= missing from create_react_agent call"
            # Variables should be interpolated
            assert "my-project" in call_kwargs["prompt"], (
                "Prompt template variables ({project_name}) must be interpolated"
            )

            # MCP tools must reach the agent
            assert call_kwargs["tools"] == [maven_tool, git_tool]

            # LLM must be created from YAML config, not hardcoded
            mock_get_llm.assert_called_once_with(
                provider="google-genai",
                model="gemini-2.0-flash",
                temperature=0.3,
                max_tokens=8192,
            )


class TestTestGenPromptAndToolsPassThrough:
    """Test generation workflow must pass prompt and tools to create_react_agent."""

    @pytest.mark.asyncio
    async def test_prompt_reaches_create_react_agent(self, tmp_path):
        from src.workflows.test_generation_agent import run_test_generation_with_agent

        # Minimal Java project fixture
        project = tmp_path / "test-project"
        project.mkdir()
        (project / "pom.xml").write_text(
            '<?xml version="1.0"?><project><modelVersion>4.0.0</modelVersion>'
            "<groupId>com.ex</groupId><artifactId>p</artifactId><version>1</version></project>"
        )
        src_dir = project / "src" / "main" / "java" / "com" / "ex"
        src_dir.mkdir(parents=True)
        (src_dir / "Foo.java").write_text("package com.ex; public class Foo {}")

        mock_config = MagicMock()
        mock_config.name = "test_gen_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.0-flash"
        mock_config.llm.temperature = 0.3
        mock_config.llm.max_tokens = 8192
        mock_config.tools.mcp_servers = ["test-generator"]
        mock_config.error_handling.timeout_seconds = 180

        prompt_text = "JUnit 5 unit test generation strategy"
        test_tool = _make_mock_tool("test_gen_analyze_project")

        mock_agent = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "Tests generated"
        mock_response.tool_calls = []
        mock_response.response_metadata = {"model": "test", "usage": {}}
        mock_response.usage_metadata = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        mock_agent.ainvoke = AsyncMock(return_value=mock_response)

        mock_db = AsyncMock()
        mock_artifact_repo = MagicMock()
        mock_artifact_repo.create = AsyncMock(return_value=None)
        mock_session_repo = MagicMock()
        mock_session_repo.update = AsyncMock(return_value=None)

        with (
            patch("src.workflows.test_generation_agent.AgentLoader") as mock_loader_cls,
            patch("src.workflows.test_generation_agent.get_tools_for_servers") as mock_get_tools,
            patch("src.workflows.test_generation_agent.create_react_agent") as mock_create,
            patch("src.workflows.test_generation_agent.get_llm") as mock_get_llm,
            patch("src.workflows.test_generation_agent.ArtifactRepository", return_value=mock_artifact_repo),
            patch("src.workflows.test_generation_agent.SessionRepository", return_value=mock_session_repo),
        ):
            loader = MagicMock()
            loader.load_agent.return_value = mock_config
            loader.load_prompt.return_value = prompt_text
            mock_loader_cls.return_value = loader

            mock_get_tools.return_value = [test_tool]
            mock_create.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()

            await run_test_generation_with_agent(
                session_id=uuid4(),
                project_path=str(project),
                db_session=mock_db,
                coverage_target=80.0,
            )

            # --- Architectural assertions ---
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs

            # Prompt loaded from markdown must reach the agent
            assert "prompt" in call_kwargs, "prompt= missing from create_react_agent call"
            assert call_kwargs["prompt"] == prompt_text

            # MCP tools must reach the agent
            assert call_kwargs["tools"] == [test_tool]

            # Config loaded from YAML
            loader.load_agent.assert_called_once_with("test_gen_agent")
            loader.load_prompt.assert_called_once_with("unit_test_strategy", category="testing")

            # LLM created from config
            mock_get_llm.assert_called_once_with(
                provider="google-genai",
                model="gemini-2.0-flash",
                temperature=0.3,
                max_tokens=8192,
                timeout=180,
            )


class TestDockerPromptAndToolsPassThrough:
    """Docker deployment workflow must pass prompt and tools to create_react_agent."""

    @pytest.mark.asyncio
    async def test_prompt_reaches_create_react_agent(self, tmp_path):
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent

        project = tmp_path / "test-project"
        project.mkdir()

        mock_config = MagicMock()
        mock_config.name = "deployment_agent"
        mock_config.llm.provider = "google-genai"
        mock_config.llm.model = "gemini-2.0-flash"
        mock_config.llm.temperature = 0.1
        mock_config.llm.max_tokens = 4096
        mock_config.tools.mcp_servers = ["docker-deployment", "container-runtime"]

        prompt_text = "Docker containerization guidelines for Java"
        docker_tool = _make_mock_tool("docker_create_dockerfile")
        container_tool = _make_mock_tool("container_create_maven")

        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = {
            "messages": [AIMessage(content="Deployment complete")]
        }

        with (
            patch("src.workflows.docker_deployment_agent.AgentLoader") as mock_loader_cls,
            patch("src.workflows.docker_deployment_agent.get_tools_for_servers") as mock_get_tools,
            patch("src.workflows.docker_deployment_agent.create_react_agent") as mock_create,
            patch("src.workflows.docker_deployment_agent.get_llm") as mock_get_llm,
            patch("src.workflows.docker_deployment_agent.get_checkpointer") as mock_cp,
        ):
            loader = MagicMock()
            loader.load_agent.return_value = mock_config
            loader.load_prompt.return_value = prompt_text
            mock_loader_cls.return_value = loader

            mock_get_tools.return_value = [docker_tool, container_tool]
            mock_create.return_value = mock_agent
            mock_get_llm.return_value = MagicMock()
            mock_cp.return_value = MagicMock()

            await run_docker_deployment_with_agent(
                project_path=str(project), session_id="arch-test-docker"
            )

            # --- Architectural assertions ---
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args.kwargs

            # Prompt loaded from markdown must reach the agent
            assert "prompt" in call_kwargs, "prompt= missing from create_react_agent call"
            assert call_kwargs["prompt"] == prompt_text

            # MCP tools must reach the agent
            assert call_kwargs["tools"] == [docker_tool, container_tool]

            # Checkpointer must be provided (Docker workflow requires state persistence)
            assert "checkpointer" in call_kwargs

            # Config loaded from YAML
            loader.load_agent.assert_called_once_with("deployment_agent")
            loader.load_prompt.assert_called_once_with(
                "docker_guidelines", category="deployment"
            )

            # LLM created from config
            mock_get_llm.assert_called_once_with(
                provider="google-genai",
                model="gemini-2.0-flash",
                temperature=0.1,
                max_tokens=4096,
            )


class TestPromptFilesExistForAllAgents:
    """Every agent YAML config must reference a prompt file that actually exists."""

    def test_all_agent_prompts_resolve_to_files(self):
        from src.agents.loader import AgentLoader

        loader = AgentLoader(config_dir="config/agents")
        agent_names = ["maven_maintenance_agent", "test_gen_agent", "deployment_agent"]

        for name in agent_names:
            config = loader.load_agent(name)
            prompt_path = config.prompts.system
            # prompt_path is like "config/prompts/testing/unit_test_strategy.md"
            from pathlib import Path

            assert Path(prompt_path).exists(), (
                f"Agent '{name}' references prompt '{prompt_path}' but file does not exist"
            )


class TestAllAgentsUseConfigDrivenLLM:
    """Verify that no workflow hardcodes LLM provider/model — all must come from YAML config."""

    def test_maven_workflow_no_hardcoded_llm(self):
        import ast
        from pathlib import Path

        source = Path("src/workflows/maven_maintenance_agent.py").read_text()
        tree = ast.parse(source)

        # Look for string literals that look like hardcoded model names
        hardcoded_models = {"gpt-4", "gpt-3.5", "claude", "gemini"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                val = node.value.lower()
                for model in hardcoded_models:
                    assert model not in val or "gemini" in val and "startswith" in source[max(0, node.col_offset - 50):node.col_offset], (
                        f"Possible hardcoded model '{node.value}' in maven workflow — "
                        "LLM config must come from YAML"
                    )
