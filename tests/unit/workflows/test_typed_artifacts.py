# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Unit tests for workflow typed artifact creation."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.step_executor import StepExecutor


class TestMavenMaintenanceTypedArtifacts:
    """Unit tests for maven_maintenance workflow typed artifacts (T053)."""

    @pytest.mark.asyncio
    async def test_analyze_dependencies_creates_yaml_artifact(self):
        """T053: _analyze_dependencies creates dependency_analysis artifact with file_format='yaml'."""
        # Setup mocks
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        # Mock the analyze_dependencies tool
        mock_result = '{"success": true, "dependencies": [], "available_updates": []}'
        with patch('src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies',
                   return_value=mock_result):
            # Mock create_artifact
            executor.session_service.create_artifact = AsyncMock()

            # Execute step
            result = await executor._analyze_dependencies(
                session_id=session_id,
                project_path="/test/project",
                db_session=mock_session,
                inputs={},
                previous_outputs={},
            )

            # Verify artifact was created with correct file_format
            executor.session_service.create_artifact.assert_called_once()
            call_args = executor.session_service.create_artifact.call_args
            assert call_args.kwargs["name"] == "dependency_analysis"
            assert call_args.kwargs["artifact_type"] == "dependency_analysis"
            assert call_args.kwargs["file_format"] == "yaml"
            assert call_args.kwargs["content_type"] == "application/x-yaml"

    @pytest.mark.asyncio
    async def test_identify_vulnerabilities_creates_md_artifact(self):
        """T053: _identify_vulnerabilities creates vulnerability_report artifact with file_format='md'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._identify_vulnerabilities(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "vulnerability_report"
        assert call_args.kwargs["artifact_type"] == "vulnerability_report"
        assert call_args.kwargs["file_format"] == "md"
        assert call_args.kwargs["content_type"] == "text/markdown"

    @pytest.mark.asyncio
    async def test_plan_updates_creates_json_artifact(self):
        """T053: _plan_updates creates update_plan artifact with file_format='json'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._plan_updates(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "update_plan"
        assert call_args.kwargs["artifact_type"] == "update_plan"
        assert call_args.kwargs["file_format"] == "json"
        assert call_args.kwargs["content_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_apply_updates_creates_xml_artifact(self):
        """T053: _apply_updates creates pom_modification artifact with file_format='xml'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._apply_updates(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "pom_modification"
        assert call_args.kwargs["artifact_type"] == "pom_modification"
        assert call_args.kwargs["file_format"] == "xml"
        assert call_args.kwargs["content_type"] == "application/xml"

    @pytest.mark.asyncio
    async def test_validate_changes_creates_json_artifact(self):
        """T053: _validate_changes creates validation_results artifact with file_format='json'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._validate_changes(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "validation_results"
        assert call_args.kwargs["artifact_type"] == "validation_results"
        assert call_args.kwargs["file_format"] == "json"
        assert call_args.kwargs["content_type"] == "application/json"


class TestDockerDeploymentTypedArtifacts:
    """Unit tests for docker_deployment workflow typed artifacts (T054)."""

    @pytest.mark.asyncio
    async def test_analyze_dockerfile_creates_json_artifact(self):
        """T054: _analyze_dockerfile creates dockerfile_analysis artifact with file_format='json'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        with patch('pathlib.Path.exists', return_value=False):
            result = await executor._analyze_dockerfile(
                session_id=session_id,
                project_path="/test/project",
                db_session=mock_session,
                inputs={},
                previous_outputs={},
            )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "dockerfile_analysis"
        assert call_args.kwargs["artifact_type"] == "dockerfile_analysis"
        assert call_args.kwargs["file_format"] == "json"
        assert call_args.kwargs["content_type"] == "application/json"

    @pytest.mark.asyncio
    async def test_optimize_image_creates_txt_artifact(self):
        """T054: _optimize_image creates build_logs artifact with file_format='txt'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._optimize_image(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "build_logs"
        assert call_args.kwargs["artifact_type"] == "build_logs"
        assert call_args.kwargs["file_format"] == "txt"
        assert call_args.kwargs["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_generate_compose_creates_yaml_and_txt_artifacts(self):
        """T054: _generate_compose creates docker-compose (yaml) and deployment_logs (txt) artifacts."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._generate_compose(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        # Verify 2 artifacts were created
        assert executor.session_service.create_artifact.call_count == 2

        # First call: docker-compose.yml (yaml)
        first_call = executor.session_service.create_artifact.call_args_list[0]
        assert first_call.kwargs["name"] == "docker-compose"
        assert first_call.kwargs["artifact_type"] == "docker_compose"
        assert first_call.kwargs["file_format"] == "yaml"
        assert first_call.kwargs["content_type"] == "application/x-yaml"

        # Second call: deployment_logs.txt (txt)
        second_call = executor.session_service.create_artifact.call_args_list[1]
        assert second_call.kwargs["name"] == "deployment_logs"
        assert second_call.kwargs["artifact_type"] == "deployment_logs"
        assert second_call.kwargs["file_format"] == "txt"
        assert second_call.kwargs["content_type"] == "text/plain"

    @pytest.mark.asyncio
    async def test_validate_deployment_creates_json_artifact(self):
        """T054: _validate_deployment creates test_results artifact with file_format='json'."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        result = await executor._validate_deployment(
            session_id=session_id,
            project_path="/test/project",
            db_session=mock_session,
            inputs={},
            previous_outputs={},
        )

        executor.session_service.create_artifact.assert_called_once()
        call_args = executor.session_service.create_artifact.call_args
        assert call_args.kwargs["name"] == "test_results"
        assert call_args.kwargs["artifact_type"] == "test_results"
        assert call_args.kwargs["file_format"] == "json"
        assert call_args.kwargs["content_type"] == "application/json"


class TestTypedArtifactValidation:
    """Tests for typed artifact validation (T055-T057)."""

    @pytest.mark.asyncio
    async def test_all_maven_artifacts_have_correct_file_formats(self):
        """T055: Verify all maven_maintenance artifacts use correct file_format values."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        expected_formats = {
            "_analyze_dependencies": "yaml",
            "_identify_vulnerabilities": "md",
            "_plan_updates": "json",
            "_apply_updates": "xml",
            "_validate_changes": "json",
        }

        executor.session_service.create_artifact = AsyncMock()

        # Test each workflow step
        with patch('src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies',
                   return_value='{"success": true, "dependencies": []}'):
            await executor._analyze_dependencies(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "yaml"

        executor.session_service.create_artifact.reset_mock()
        await executor._identify_vulnerabilities(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "md"

        executor.session_service.create_artifact.reset_mock()
        await executor._plan_updates(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "json"

        executor.session_service.create_artifact.reset_mock()
        await executor._apply_updates(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "xml"

        executor.session_service.create_artifact.reset_mock()
        await executor._validate_changes(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "json"

    @pytest.mark.asyncio
    async def test_all_docker_artifacts_have_correct_file_formats(self):
        """T055: Verify all docker_deployment artifacts use correct file_format values."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        executor.session_service.create_artifact = AsyncMock()

        # Test each workflow step
        with patch('pathlib.Path.exists', return_value=False):
            await executor._analyze_dockerfile(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "json"

        executor.session_service.create_artifact.reset_mock()
        await executor._optimize_image(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "txt"

        executor.session_service.create_artifact.reset_mock()
        await executor._generate_compose(session_id, "/test", mock_session, {}, {})
        # First artifact is yaml, second is txt
        assert executor.session_service.create_artifact.call_args_list[0].kwargs["file_format"] == "yaml"
        assert executor.session_service.create_artifact.call_args_list[1].kwargs["file_format"] == "txt"

        executor.session_service.create_artifact.reset_mock()
        await executor._validate_deployment(session_id, "/test", mock_session, {}, {})
        assert executor.session_service.create_artifact.call_args.kwargs["file_format"] == "json"

    @pytest.mark.asyncio
    async def test_artifact_content_type_matches_file_format(self):
        """T056: Verify artifact content_type is appropriate for file_format."""
        mock_session = AsyncMock()
        executor = StepExecutor(mock_session)
        session_id = uuid.uuid4()

        format_to_content_type = {
            "json": "application/json",
            "yaml": "application/x-yaml",
            "xml": "application/xml",
            "md": "text/markdown",
            "txt": "text/plain",
        }

        executor.session_service.create_artifact = AsyncMock()

        # Test yaml artifact
        with patch('src.mcp_servers.maven_maintenance.tools.analyze.analyze_dependencies',
                   return_value='{"success": true}'):
            await executor._analyze_dependencies(session_id, "/test", mock_session, {}, {})
        call_args = executor.session_service.create_artifact.call_args.kwargs
        assert call_args["file_format"] == "yaml"
        assert call_args["content_type"] == "application/x-yaml"

        # Test md artifact
        executor.session_service.create_artifact.reset_mock()
        await executor._identify_vulnerabilities(session_id, "/test", mock_session, {}, {})
        call_args = executor.session_service.create_artifact.call_args.kwargs
        assert call_args["file_format"] == "md"
        assert call_args["content_type"] == "text/markdown"

        # Test xml artifact
        executor.session_service.create_artifact.reset_mock()
        await executor._apply_updates(session_id, "/test", mock_session, {}, {})
        call_args = executor.session_service.create_artifact.call_args.kwargs
        assert call_args["file_format"] == "xml"
        assert call_args["content_type"] == "application/xml"

        # Test txt artifact
        executor.session_service.create_artifact.reset_mock()
        await executor._optimize_image(session_id, "/test", mock_session, {}, {})
        call_args = executor.session_service.create_artifact.call_args.kwargs
        assert call_args["file_format"] == "txt"
        assert call_args["content_type"] == "text/plain"
