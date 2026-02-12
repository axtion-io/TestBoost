# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Unit tests for SessionService step artifact methods."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.session import SessionService
from src.db.models.artifact import Artifact
from src.db.models.step import Step


class TestSessionServiceStepArtifacts:
    """Unit tests for SessionService step artifact methods (T090-T092)."""

    @pytest.mark.asyncio
    async def test_get_step_by_code_returns_step_when_found(self):
        """T090: SessionService.get_step_by_code() returns step when found."""
        mock_session = AsyncMock()
        service = SessionService(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Mock step
        mock_step = Step(
            id=step_id,
            session_id=session_id,
            code="analyze_project",
            name="Analyze Project",
            sequence=1,
            status="completed",
        )

        # Mock the repository query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_step
        mock_session.execute.return_value = mock_result

        # Call get_step_by_code
        result = await service.get_step_by_code(session_id, "analyze_project")

        assert result is not None
        assert result.id == step_id
        assert result.code == "analyze_project"
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_step_by_code_returns_none_when_not_found(self):
        """T091: SessionService.get_step_by_code() returns None when not found."""
        mock_session = AsyncMock()
        service = SessionService(mock_session)

        session_id = uuid.uuid4()

        # Mock empty result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        # Call get_step_by_code for non-existent step
        result = await service.get_step_by_code(session_id, "nonexistent_step")

        assert result is None
        mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_step_artifacts_delegates_to_repository(self):
        """T092: SessionService.get_step_artifacts() delegates to repository correctly."""
        mock_session = AsyncMock()
        service = SessionService(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Mock artifacts
        mock_artifacts = [
            Artifact(
                id=uuid.uuid4(),
                session_id=session_id,
                step_id=step_id,
                name="analysis.json",
                artifact_type="analysis",
                content_type="application/json",
                file_path="/tmp/analysis.json",
                size_bytes=100,
                file_format="json",
            ),
            Artifact(
                id=uuid.uuid4(),
                session_id=session_id,
                step_id=step_id,
                name="metrics.json",
                artifact_type="metrics",
                content_type="application/json",
                file_path="/tmp/metrics.json",
                size_bytes=50,
                file_format="json",
            ),
        ]

        # Mock repository method
        service.artifact_repo.get_step_artifacts = AsyncMock(return_value=mock_artifacts)

        # Call get_step_artifacts
        result = await service.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_project",
        )

        # Verify delegation to repository
        service.artifact_repo.get_step_artifacts.assert_called_once_with(
            session_id=session_id,
            step_code="analyze_project",
            artifact_type=None,
            file_format=None,
        )
        assert len(result) == 2
        assert result[0].name == "analysis.json"
        assert result[1].name == "metrics.json"

    @pytest.mark.asyncio
    async def test_get_step_artifacts_passes_all_filters(self):
        """Test that get_step_artifacts passes all filter parameters to repository."""
        mock_session = AsyncMock()
        service = SessionService(mock_session)

        session_id = uuid.uuid4()
        step_id = uuid.uuid4()

        # Mock single filtered artifact
        mock_artifact = Artifact(
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

        # Mock repository method
        service.artifact_repo.get_step_artifacts = AsyncMock(return_value=[mock_artifact])

        # Call with all filters
        result = await service.get_step_artifacts(
            session_id=session_id,
            step_code="analyze_dependencies",
            artifact_type="dependency_analysis",
            file_format="yaml",
        )

        # Verify all parameters passed to repository
        service.artifact_repo.get_step_artifacts.assert_called_once_with(
            session_id=session_id,
            step_code="analyze_dependencies",
            artifact_type="dependency_analysis",
            file_format="yaml",
        )
        assert len(result) == 1
        assert result[0].file_format == "yaml"
        assert result[0].artifact_type == "dependency_analysis"

    @pytest.mark.asyncio
    async def test_get_step_artifacts_returns_empty_for_step_without_artifacts(self):
        """Test that get_step_artifacts returns empty list when step has no artifacts."""
        mock_session = AsyncMock()
        service = SessionService(mock_session)

        session_id = uuid.uuid4()

        # Mock empty result
        service.artifact_repo.get_step_artifacts = AsyncMock(return_value=[])

        # Call for step without artifacts
        result = await service.get_step_artifacts(
            session_id=session_id,
            step_code="empty_step",
        )

        assert len(result) == 0
        service.artifact_repo.get_step_artifacts.assert_called_once()
