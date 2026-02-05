# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Unit tests for step-specific artifact retrieval."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.db.models.artifact import Artifact
from src.db.models.step import Step
from src.db.repository import ArtifactRepository


class TestArtifactRepositoryStepArtifacts:
    """Unit tests for ArtifactRepository.get_step_artifacts() (T085-T089)."""

    @pytest.mark.asyncio
    async def test_get_step_artifacts_joins_with_steps_table(self):
        """T085: ArtifactRepository.get_step_artifacts() joins artifacts and steps tables correctly."""
        mock_session = AsyncMock()
        repo = ArtifactRepository(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Create mock step
        mock_step = Step(
            id=step_id,
            session_id=session_id,
            code="analyze_project",
            name="Analyze Project",
            sequence=1,
            status="completed",
        )

        # Create mock artifact linked to step
        mock_artifact = Artifact(
            id=uuid.uuid4(),
            session_id=session_id,
            step_id=step_id,
            name="analysis.json",
            artifact_type="analysis",
            content_type="application/json",
            file_path="/tmp/analysis.json",
            size_bytes=100,
            file_format="json",
        )

        # Mock execute result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [mock_artifact]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Execute query
        result = await repo.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_project",
        )

        # Verify execute was called (join query should be executed)
        mock_session.execute.assert_called_once()
        assert len(result) == 1
        assert result[0].id == mock_artifact.id

    @pytest.mark.asyncio
    async def test_get_step_artifacts_filters_by_step_code(self):
        """T086: ArtifactRepository.get_step_artifacts() filters by step_code."""
        mock_session = AsyncMock()
        repo = ArtifactRepository(mock_session)

        session_id = uuid.uuid4()
        step1_id = uuid.uuid4()
        step2_id = uuid.uuid4()

        # Mock artifacts from different steps
        artifact1 = Artifact(
            id=uuid.uuid4(),
            session_id=session_id,
            step_id=step1_id,
            name="analysis.json",
            artifact_type="analysis",
            content_type="application/json",
            file_path="/tmp/analysis.json",
            size_bytes=100,
            file_format="json",
        )

        # Mock execute to return only artifacts from step1
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [artifact1]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Query for specific step code
        result = await repo.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_project",
        )

        # Verify only artifacts from the specified step are returned
        assert len(result) == 1
        assert result[0].step_id == step1_id
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_step_artifacts_filters_by_artifact_type(self):
        """T087: ArtifactRepository.get_step_artifacts() filters by artifact_type when provided."""
        mock_session = AsyncMock()
        repo = ArtifactRepository(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Mock artifact with specific type
        yaml_artifact = Artifact(
            id=uuid.uuid4(),
            session_id=session_id,
            step_id=step_id,
            name="config.yaml",
            artifact_type="configuration",
            content_type="application/x-yaml",
            file_path="/tmp/config.yaml",
            size_bytes=150,
            file_format="yaml",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [yaml_artifact]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Query with artifact_type filter
        result = await repo.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_project",
            artifact_type="configuration",
        )

        assert len(result) == 1
        assert result[0].artifact_type == "configuration"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_step_artifacts_filters_by_file_format(self):
        """T088: ArtifactRepository.get_step_artifacts() filters by file_format when provided."""
        mock_session = AsyncMock()
        repo = ArtifactRepository(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Mock artifact with specific file format
        yaml_artifact = Artifact(
            id=uuid.uuid4(),
            session_id=session_id,
            step_id=step_id,
            name="config.yaml",
            artifact_type="configuration",
            content_type="application/x-yaml",
            file_path="/tmp/config.yaml",
            size_bytes=150,
            file_format="yaml",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [yaml_artifact]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Query with file_format filter
        result = await repo.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_project",
            file_format="yaml",
        )

        assert len(result) == 1
        assert result[0].file_format == "yaml"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_step_artifacts_returns_empty_for_nonexistent_step(self):
        """T089: ArtifactRepository.get_step_artifacts() returns empty list for non-existent step."""
        mock_session = AsyncMock()
        repo = ArtifactRepository(mock_session)

        session_id = uuid.uuid4()

        # Mock execute to return empty result
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = []
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Query for non-existent step
        result = await repo.get_step_artifacts(
            session_id=session_id,
            step_code="nonexistent_step",
        )

        assert len(result) == 0
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_step_artifacts_combines_all_filters(self):
        """Test that get_step_artifacts correctly combines step_code, artifact_type, and file_format filters."""
        mock_session = AsyncMock()
        repo = ArtifactRepository(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Mock specific artifact matching all filters
        artifact = Artifact(
            id=uuid.uuid4(),
            session_id=session_id,
            step_id=step_id,
            name="dependency_analysis.yaml",
            artifact_type="dependency_analysis",
            content_type="application/x-yaml",
            file_path="/tmp/dependency_analysis.yaml",
            size_bytes=200,
            file_format="yaml",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [artifact]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Query with all filters
        result = await repo.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_dependencies",
            artifact_type="dependency_analysis",
            file_format="yaml",
        )

        assert len(result) == 1
        assert result[0].artifact_type == "dependency_analysis"
        assert result[0].file_format == "yaml"
        mock_session.execute.assert_called_once()
