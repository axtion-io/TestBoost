"""Integration tests for artifact content download endpoint.

Tests cover the GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content endpoint.
Feature: 006-file-modifications-api
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_session():
    """Create a mock session object."""
    session = MagicMock()
    session.id = uuid.uuid4()
    session.status = "in_progress"
    session.project_path = "/test/project"
    return session


@pytest.fixture
def mock_artifact():
    """Create a mock artifact object."""
    artifact = MagicMock()
    artifact.id = uuid.uuid4()
    artifact.session_id = uuid.uuid4()
    artifact.name = "pom.xml"
    artifact.artifact_type = "file_modification"
    artifact.content_type = "application/xml"
    artifact.file_path = "pom.xml"
    artifact.size_bytes = 1024
    artifact.artifact_metadata = {
        "file_path": "pom.xml",
        "operation": "modify",
        "original_content": "<project><version>1.0.0</version></project>",
        "modified_content": "<project><version>1.1.0</version></project>",
        "diff": "--- a/pom.xml\n+++ b/pom.xml\n@@ -1 +1 @@\n-<version>1.0.0</version>\n+<version>1.1.0</version>",
    }
    return artifact


@pytest.fixture
def mock_large_artifact():
    """Create a mock artifact that exceeds size limit."""
    artifact = MagicMock()
    artifact.id = uuid.uuid4()
    artifact.session_id = uuid.uuid4()
    artifact.name = "large_file.txt"
    artifact.artifact_type = "file_modification"
    artifact.content_type = "text/plain"
    artifact.file_path = "large_file.txt"
    artifact.size_bytes = 11 * 1024 * 1024  # 11MB, exceeds 10MB limit
    artifact.artifact_metadata = {}
    return artifact


@pytest.fixture
def mock_binary_artifact():
    """Create a mock artifact with binary content."""
    artifact = MagicMock()
    artifact.id = uuid.uuid4()
    artifact.session_id = uuid.uuid4()
    artifact.name = "image.png"
    artifact.artifact_type = "file_modification"
    artifact.content_type = "image/png"
    artifact.file_path = "image.png"
    artifact.size_bytes = 1024
    # Binary content with null bytes
    artifact.artifact_metadata = {
        "file_path": "image.png",
        "operation": "create",
        "modified_content": "PNG\x00\x00\x00\x0D\x00\x00\x00binary data",
    }
    return artifact


@pytest.mark.integration
class TestArtifactContentDownload:
    """Tests for GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content endpoint."""

    @pytest.mark.asyncio
    async def test_content_download_success(self, client, mock_session, mock_artifact):
        """T008: Should return artifact content with correct Content-Type."""
        session_id = mock_session.id
        artifact_id = mock_artifact.id
        mock_artifact.session_id = session_id

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifact.return_value = mock_artifact
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content"
            )

            # Verify success response
            assert response.status_code == 200
            assert "application/xml" in response.headers.get("content-type", "")
            assert "<project>" in response.text

    @pytest.mark.asyncio
    async def test_content_download_artifact_not_found(self, client, mock_session):
        """T009: Should return 404 when artifact not found."""
        session_id = mock_session.id
        artifact_id = uuid.uuid4()

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifact.return_value = None
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content"
            )

            assert response.status_code == 404
            assert "Artifact not found" in response.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_content_download_session_not_found(self, client):
        """Should return 404 when session not found."""
        session_id = uuid.uuid4()
        artifact_id = uuid.uuid4()

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = None
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content"
            )

            assert response.status_code == 404
            assert "Session not found" in response.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_content_download_binary_rejected(
        self, client, mock_session, mock_binary_artifact
    ):
        """T010: Should return 400 when artifact contains binary content."""
        session_id = mock_session.id
        artifact_id = mock_binary_artifact.id
        mock_binary_artifact.session_id = session_id

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifact.return_value = mock_binary_artifact
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content"
            )

            assert response.status_code == 400
            assert "binary" in response.json().get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_content_download_too_large(
        self, client, mock_session, mock_large_artifact
    ):
        """T011: Should return 413 when content exceeds 10MB."""
        session_id = mock_session.id
        artifact_id = mock_large_artifact.id
        mock_large_artifact.session_id = session_id

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifact.return_value = mock_large_artifact
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content"
            )

            assert response.status_code == 413
            assert "10MB" in response.json().get("detail", "")

    @pytest.mark.asyncio
    async def test_content_download_delete_operation(self, client, mock_session, mock_artifact):
        """Should return original_content for delete operations."""
        session_id = mock_session.id
        artifact_id = mock_artifact.id
        mock_artifact.session_id = session_id
        mock_artifact.artifact_metadata = {
            "file_path": "deleted.xml",
            "operation": "delete",
            "original_content": "<deleted>content</deleted>",
            "modified_content": None,
        }

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifact.return_value = mock_artifact
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content"
            )

            assert response.status_code == 200
            assert "<deleted>" in response.text


@pytest.mark.integration
class TestArtifactContentValidation:
    """Tests for UUID validation on content endpoint."""

    @pytest.mark.asyncio
    async def test_invalid_session_uuid_format(self, client):
        """Should return 422 for invalid session UUID format."""
        response = await client.get(
            "/api/v2/sessions/not-a-uuid/artifacts/12345678-1234-1234-1234-123456789012/content"
        )

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_artifact_uuid_format(self, client):
        """Should return 422 for invalid artifact UUID format."""
        session_id = uuid.uuid4()
        response = await client.get(
            f"/api/v2/sessions/{session_id}/artifacts/not-a-uuid/content"
        )

        # FastAPI returns 422 for validation errors
        assert response.status_code == 422


@pytest.fixture
def mock_modify_artifact():
    """Create a mock file_modification artifact for modify operation."""
    artifact = MagicMock()
    artifact.id = uuid.uuid4()
    artifact.session_id = uuid.uuid4()
    artifact.step_id = None
    artifact.name = "pom.xml"
    artifact.artifact_type = "file_modification"
    artifact.content_type = "application/xml"
    artifact.file_path = "pom.xml"
    artifact.size_bytes = 2048
    artifact.created_at = "2026-01-10T12:00:00Z"
    artifact.artifact_metadata = {
        "file_path": "pom.xml",
        "operation": "modify",
        "original_content": "<version>1.0.0</version>",
        "modified_content": "<version>1.1.0</version>",
        "diff": "--- a/pom.xml\n+++ b/pom.xml\n@@ -1 +1 @@\n-<version>1.0.0</version>\n+<version>1.1.0</version>\n",
    }
    return artifact


@pytest.fixture
def mock_create_artifact():
    """Create a mock file_modification artifact for create operation."""
    artifact = MagicMock()
    artifact.id = uuid.uuid4()
    artifact.session_id = uuid.uuid4()
    artifact.step_id = None
    artifact.name = "NewTest.java"
    artifact.artifact_type = "file_modification"
    artifact.content_type = "text/x-java"
    artifact.file_path = "src/test/java/NewTest.java"
    artifact.size_bytes = 512
    artifact.created_at = "2026-01-10T12:00:00Z"
    artifact.artifact_metadata = {
        "file_path": "src/test/java/NewTest.java",
        "operation": "create",
        "original_content": None,
        "modified_content": "public class NewTest {}",
        "diff": "--- a/src/test/java/NewTest.java\n+++ b/src/test/java/NewTest.java\n@@ -0,0 +1 @@\n+public class NewTest {}\n",
    }
    return artifact


@pytest.fixture
def mock_delete_artifact():
    """Create a mock file_modification artifact for delete operation."""
    artifact = MagicMock()
    artifact.id = uuid.uuid4()
    artifact.session_id = uuid.uuid4()
    artifact.step_id = None
    artifact.name = "OldFile.java"
    artifact.artifact_type = "file_modification"
    artifact.content_type = "text/x-java"
    artifact.file_path = "src/main/java/OldFile.java"
    artifact.size_bytes = 256
    artifact.created_at = "2026-01-10T12:00:00Z"
    artifact.artifact_metadata = {
        "file_path": "src/main/java/OldFile.java",
        "operation": "delete",
        "original_content": "public class OldFile {}",
        "modified_content": None,
        "diff": "--- a/src/main/java/OldFile.java\n+++ b/src/main/java/OldFile.java\n@@ -1 +0,0 @@\n-public class OldFile {}\n",
    }
    return artifact


@pytest.mark.integration
class TestArtifactDiffVisualization:
    """Tests for User Story 3 - View File Diff in Frontend (T031-T033)."""

    @pytest.mark.asyncio
    async def test_artifact_response_includes_diff(self, client, mock_session, mock_modify_artifact):
        """T031: Verify diff field is included in artifact response."""
        session_id = mock_session.id
        mock_modify_artifact.session_id = session_id

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifacts.return_value = [mock_modify_artifact]
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts?artifact_type=file_modification"
            )

            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert len(data["items"]) == 1

            artifact = data["items"][0]
            assert artifact["artifact_type"] == "file_modification"
            assert "metadata" in artifact
            assert artifact["metadata"]["diff"] is not None
            # Verify unified diff format
            assert "---" in artifact["metadata"]["diff"]
            assert "+++" in artifact["metadata"]["diff"]

    @pytest.mark.asyncio
    async def test_diff_format_create_operation(self, client, mock_session, mock_create_artifact):
        """T032: Verify diff shows all lines as additions for create operation."""
        session_id = mock_session.id
        mock_create_artifact.session_id = session_id

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifacts.return_value = [mock_create_artifact]
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts?artifact_type=file_modification"
            )

            assert response.status_code == 200
            data = response.json()
            artifact = data["items"][0]

            # Verify create operation metadata
            assert artifact["metadata"]["operation"] == "create"
            assert artifact["metadata"]["original_content"] is None
            assert artifact["metadata"]["modified_content"] is not None
            # Diff should show additions
            assert "+" in artifact["metadata"]["diff"]

    @pytest.mark.asyncio
    async def test_diff_format_delete_operation(self, client, mock_session, mock_delete_artifact):
        """T033: Verify diff shows all lines as deletions for delete operation."""
        session_id = mock_session.id
        mock_delete_artifact.session_id = session_id

        with patch("src.api.routers.sessions.SessionService") as MockService:
            service_instance = AsyncMock()
            service_instance.get_session.return_value = mock_session
            service_instance.get_artifacts.return_value = [mock_delete_artifact]
            MockService.return_value = service_instance

            response = await client.get(
                f"/api/v2/sessions/{session_id}/artifacts?artifact_type=file_modification"
            )

            assert response.status_code == 200
            data = response.json()
            artifact = data["items"][0]

            # Verify delete operation metadata
            assert artifact["metadata"]["operation"] == "delete"
            assert artifact["metadata"]["original_content"] is not None
            assert artifact["metadata"]["modified_content"] is None
            # Diff should show deletions
            assert "-" in artifact["metadata"]["diff"]
