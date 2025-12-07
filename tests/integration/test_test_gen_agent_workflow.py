"""Integration tests for Test Generation workflow with DeepAgents (US4, T050-T051)."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestTestGenAgentWorkflow:
    """Test Test Generation workflow integration (T050-T051)."""

    @pytest.mark.asyncio
    async def test_test_gen_workflow_uses_agent(self, tmp_path):
        """Test that test generation workflow creates and uses DeepAgents agent (T050)."""
        from src.workflows.test_generation_agent import run_test_generation_with_agent

        # Create a minimal Java project
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        # Create pom.xml
        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
    <properties>
        <java.version>17</java.version>
    </properties>
</project>
""")

        # Create a simple Java class
        src_dir = project_path / "src" / "main" / "java" / "com" / "example"
        src_dir.mkdir(parents=True)
        java_file = src_dir / "Calculator.java"
        java_file.write_text("""package com.example;
public class Calculator {
    public int add(int a, int b) { return a + b; }
}
""")

        # Mock database session and repositories
        mock_db_session = AsyncMock()
        mock_artifact_repo = MagicMock()
        mock_artifact_repo.create = AsyncMock(return_value=None)
        mock_session_repo = MagicMock()
        mock_session_repo.update = AsyncMock(return_value=None)

        # Track create_deep_agent calls
        agent_created = False

        def mock_create_deep_agent(*args, **kwargs):
            """Track that create_deep_agent was called."""
            nonlocal agent_created
            agent_created = True

            # Create a mock agent that returns a response
            mock_agent = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Generated tests for Calculator class"
            mock_response.tool_calls = []
            mock_response.response_metadata = {"model": "test-model", "usage": {}}
            mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300}
            mock_agent.ainvoke = AsyncMock(return_value=mock_response)
            return mock_agent

        # Patch create_deep_agent to track usage
        with (
            patch("src.workflows.test_generation_agent.create_deep_agent", side_effect=mock_create_deep_agent),
            patch("src.workflows.test_generation_agent.ArtifactRepository", return_value=mock_artifact_repo),
            patch("src.workflows.test_generation_agent.SessionRepository", return_value=mock_session_repo),
        ):
            # Run workflow
            session_id = uuid4()
            result = await run_test_generation_with_agent(
                session_id=session_id,
                project_path=str(project_path),
                db_session=mock_db_session,
                coverage_target=80.0
            )

            # Verify agent was created
            assert agent_created, "create_deep_agent should have been called"

            # Verify result structure
            assert result is not None
            assert isinstance(result, dict)

    @pytest.mark.asyncio
    async def test_test_gen_workflow_stores_artifacts(self, tmp_path):
        """Test that test generation workflow stores agent reasoning and metrics (T051)."""
        from src.workflows.test_generation_agent import run_test_generation_with_agent

        # Create a minimal Java project
        project_path = tmp_path / "test-project"
        project_path.mkdir()

        # Create pom.xml
        pom_xml = project_path / "pom.xml"
        pom_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
</project>
""")

        # Mock database session
        mock_db_session = AsyncMock()

        # Track artifact storage calls
        artifact_calls = []

        class MockArtifactRepo:
            async def create(self, **kwargs):
                artifact_calls.append(kwargs)
                return None

        mock_artifact_repo = MockArtifactRepo()

        mock_session_repo = MagicMock()
        mock_session_repo.update = AsyncMock(return_value=None)

        # Mock agent to return a simple response
        def mock_create_deep_agent(*args, **kwargs):
            mock_agent = MagicMock()
            mock_response = MagicMock()
            mock_response.content = "Generated test analysis"
            # Add required attributes for JSON serialization
            mock_response.tool_calls = []
            mock_response.response_metadata = {"model": "test-model", "usage": {}}
            mock_response.usage_metadata = {"input_tokens": 100, "output_tokens": 200, "total_tokens": 300}
            mock_agent.ainvoke = AsyncMock(return_value=mock_response)
            return mock_agent

        with (
            patch("src.workflows.test_generation_agent.create_deep_agent", side_effect=mock_create_deep_agent),
            patch("src.workflows.test_generation_agent.ArtifactRepository", return_value=mock_artifact_repo),
            patch("src.workflows.test_generation_agent.SessionRepository", return_value=mock_session_repo),
        ):
            # Run workflow
            session_id = uuid4()
            result = await run_test_generation_with_agent(
                session_id=session_id,
                project_path=str(project_path),
                db_session=mock_db_session,
                coverage_target=80.0
            )

            # Verify artifacts were stored
            assert len(artifact_calls) > 0, "Should have stored at least one artifact"

            # Check for reasoning artifact
            reasoning_artifacts = [a for a in artifact_calls if a.get("artifact_type") == "agent_reasoning"]
            assert len(reasoning_artifacts) > 0, "Should have stored agent reasoning artifact"

            # Check for metrics artifact
            metrics_artifacts = [a for a in artifact_calls if a.get("artifact_type") == "llm_metrics"]
            assert len(metrics_artifacts) > 0, "Should have stored LLM metrics artifact"

            # Verify result
            assert result is not None
            assert "metrics" in result
            assert "duration_seconds" in result["metrics"]
