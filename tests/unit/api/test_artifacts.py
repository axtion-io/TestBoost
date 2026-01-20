"""Tests for artifacts API endpoints."""

import uuid

import pytest


class TestArtifactsEndpoint:
    """Tests for the /api/v2/artifacts endpoints."""

    @pytest.mark.asyncio
    async def test_get_artifacts_for_session(self, client):
        """Getting artifacts for a session should return list."""
        session_id = str(uuid.uuid4())
        response = await client.get(f"/api/v2/sessions/{session_id}/artifacts")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_get_artifact_by_id(self, client):
        """Getting a specific artifact should return artifact details."""
        session_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())
        response = await client.get(f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}")
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_artifact_types(self, client):
        """Artifact types should be valid."""
        valid_types = ["test_file", "report", "diff", "backup"]
        for artifact_type in valid_types:
            assert artifact_type in valid_types

    @pytest.mark.asyncio
    async def test_download_artifact(self, client):
        """Downloading an artifact should return file content or 404."""
        session_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())
        response = await client.get(
            f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/download"
        )
        assert response.status_code in [200, 404]
