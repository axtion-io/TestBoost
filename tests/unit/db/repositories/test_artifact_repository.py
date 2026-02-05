# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Unit tests for ArtifactRepository file_format functionality."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.db.models.artifact import Artifact
from src.db.repository import ArtifactRepository


class TestArtifactRepositoryFileFormat:
    """Unit tests for file_format support in ArtifactRepository."""

    @pytest.mark.asyncio
    async def test_create_accepts_file_format_parameter(self):
        """T044: ArtifactRepository.create() accepts file_format parameter."""
        # Create a mock session
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        # Create repository
        repo = ArtifactRepository(mock_session)

        # Create artifact with file_format using kwargs
        result = await repo.create(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            name="test_artifact.yaml",
            artifact_type="config",
            content_type="application/yaml",
            file_path="/tmp/config.yaml",
            size_bytes=200,
            file_format="yaml",
        )

        # Verify file_format was preserved
        assert result.file_format == "yaml"
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_without_file_format_allows_database_default(self):
        """ArtifactRepository.create() can create artifacts without specifying file_format.

        Note: The database default='json' is applied at the database level during INSERT,
        not at the Python object level. This test verifies the repository accepts artifacts
        without file_format. The actual default value will be tested in integration tests.
        """
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        repo = ArtifactRepository(mock_session)

        # Create artifact without file_format (should succeed)
        result = await repo.create(
            id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            name="test_artifact",
            artifact_type="analysis",
            content_type="application/json",
            file_path="/tmp/test.json",
            size_bytes=100,
        )

        # Verify artifact was created (database default will be applied on insert)
        assert result is not None
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_artifacts_filters_by_file_format(self):
        """T045: ArtifactRepository.get_artifacts() filters by file_format."""
        # Create mock session
        mock_session = AsyncMock()

        # Create mock artifacts with different formats
        session_id = uuid.uuid4()
        artifacts = [
            Artifact(
                id=uuid.uuid4(),
                session_id=session_id,
                name="config.yaml",
                artifact_type="config",
                content_type="application/yaml",
                file_path="/tmp/config.yaml",
                size_bytes=100,
                file_format="yaml",
            ),
            Artifact(
                id=uuid.uuid4(),
                session_id=session_id,
                name="data.json",
                artifact_type="data",
                content_type="application/json",
                file_path="/tmp/data.json",
                size_bytes=200,
                file_format="json",
            ),
            Artifact(
                id=uuid.uuid4(),
                session_id=session_id,
                name="doc.md",
                artifact_type="documentation",
                content_type="text/markdown",
                file_path="/tmp/doc.md",
                size_bytes=300,
                file_format="md",
            ),
        ]

        # Mock the execute result to return only yaml artifacts
        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [artifacts[0]]  # Only yaml
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        # Create repository
        repo = ArtifactRepository(mock_session)

        # Query for yaml artifacts
        result = await repo.get_artifacts(
            session_id=session_id,
            file_format="yaml",
        )

        # Verify execute was called
        mock_session.execute.assert_called_once()

        # Verify result contains only yaml artifacts
        assert len(result) == 1
        assert result[0].file_format == "yaml"

    @pytest.mark.asyncio
    async def test_get_artifacts_filters_by_session_and_file_format(self):
        """ArtifactRepository.get_artifacts() filters by both session_id and file_format."""
        mock_session = AsyncMock()

        session_id = uuid.uuid4()
        xml_artifact = Artifact(
            id=uuid.uuid4(),
            session_id=session_id,
            name="pom.xml",
            artifact_type="build",
            content_type="application/xml",
            file_path="/tmp/pom.xml",
            size_bytes=500,
            file_format="xml",
        )

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = [xml_artifact]
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = ArtifactRepository(mock_session)

        result = await repo.get_artifacts(
            session_id=session_id,
            file_format="xml",
        )

        assert len(result) == 1
        assert result[0].file_format == "xml"
        assert result[0].session_id == session_id

    @pytest.mark.asyncio
    async def test_get_artifacts_returns_all_when_no_filters(self):
        """ArtifactRepository.get_artifacts() returns all artifacts when no filters specified."""
        mock_session = AsyncMock()

        all_artifacts = [
            Artifact(
                id=uuid.uuid4(),
                session_id=uuid.uuid4(),
                name=f"file{i}.{fmt}",
                artifact_type="test",
                content_type="text/plain",
                file_path=f"/tmp/file{i}.{fmt}",
                size_bytes=100,
                file_format=fmt,
            )
            for i, fmt in enumerate(["json", "yaml", "xml"])
        ]

        mock_result = MagicMock()
        mock_scalars = MagicMock()
        mock_scalars.all.return_value = all_artifacts
        mock_result.scalars.return_value = mock_scalars
        mock_session.execute.return_value = mock_result

        repo = ArtifactRepository(mock_session)

        result = await repo.get_artifacts()

        assert len(result) == 3
        formats = {a.file_format for a in result}
        assert formats == {"json", "yaml", "xml"}
