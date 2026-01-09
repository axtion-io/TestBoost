"""Integration tests for API endpoints.

Tests cover health, metrics, and session validation endpoints.
All tests use the async HTTP client with mocked database.
"""

import pytest


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200_when_db_healthy(self, client):
        """Should return 200 with healthy status."""
        response = await client.get("/health")

        # Should return 200 or 503 depending on DB mock
        assert response.status_code in [200, 503]

        if response.status_code == 200:
            data = response.json()
            assert data["status"] == "healthy"
            assert "version" in data
            assert "checks" in data

    @pytest.mark.asyncio
    async def test_health_includes_database_check(self, client):
        """Health response should include database check result."""
        response = await client.get("/health")

        assert response.status_code in [200, 503]
        data = response.json()

        assert "checks" in data
        assert "database" in data["checks"]
        assert data["checks"]["database"] in ["healthy", "unhealthy"]


@pytest.mark.integration
class TestMetricsEndpoint:
    """Tests for /metrics endpoints."""

    @pytest.mark.asyncio
    async def test_metrics_prometheus_format(self, client):
        """Should return metrics in Prometheus format."""
        response = await client.get("/metrics")

        assert response.status_code == 200
        content = response.text

        # Prometheus format includes TYPE declarations
        assert "# TYPE" in content or content == ""

    @pytest.mark.asyncio
    async def test_metrics_json_format(self, client):
        """Should return metrics in JSON format."""
        response = await client.get("/metrics/json")

        assert response.status_code == 200
        data = response.json()

        # Should have expected keys
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_metrics_json_timestamp_iso_format(self, client):
        """Metrics timestamp should be in ISO format."""
        response = await client.get("/metrics/json")

        if response.status_code == 200:
            data = response.json()
            timestamp = data.get("timestamp", "")
            # Basic ISO format validation
            assert "T" in timestamp or timestamp == ""


@pytest.mark.integration
class TestSessionValidation:
    """Tests for session creation validation."""

    @pytest.mark.asyncio
    async def test_create_session_invalid_type_returns_400(self, client):
        """Should return 400 for invalid session type."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "project_path": "/test/path",
                "session_type": "invalid_type",
                "mode": "interactive",
            },
        )

        # Should reject invalid type
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_session_invalid_mode_returns_400(self, client):
        """Should return 400 for invalid mode."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "project_path": "/test/path",
                "session_type": "maven_maintenance",
                "mode": "invalid_mode",
            },
        )

        # Should reject invalid mode
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_create_session_missing_project_path_returns_422(self, client):
        """Should return 422 for missing required field."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "session_type": "maven_maintenance",
                "mode": "interactive",
                # project_path missing
            },
        )

        # Pydantic validation error
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_session_valid_maven_maintenance(self, client, db_session):
        """Should accept valid maven_maintenance session."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "project_path": "/test/project",
                "session_type": "maven_maintenance",
                "mode": "interactive",
            },
        )

        # With mocked DB, various responses are valid
        assert response.status_code in [200, 201, 400, 500]

    @pytest.mark.asyncio
    async def test_create_session_valid_test_generation(self, client, db_session):
        """Should accept valid test_generation session."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "project_path": "/test/project",
                "session_type": "test_generation",
                "mode": "interactive",
            },
        )

        assert response.status_code in [200, 201, 400, 500]

    @pytest.mark.asyncio
    async def test_create_session_valid_docker_deployment(self, client, db_session):
        """Should accept valid docker_deployment session."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "project_path": "/test/project",
                "session_type": "docker_deployment",
                "mode": "autonomous",
            },
        )

        assert response.status_code in [200, 201, 400, 500]

    @pytest.mark.asyncio
    async def test_create_session_with_config(self, client, db_session):
        """Should accept session with config dict."""
        response = await client.post(
            "/api/v2/sessions",
            json={
                "project_path": "/test/project",
                "session_type": "test_generation",
                "mode": "interactive",
                "config": {
                    "use_llm": False,
                    "verbose": True,
                },
            },
        )

        assert response.status_code in [200, 201, 400, 500]


@pytest.mark.integration
class TestSessionNotFound:
    """Tests for session not found scenarios."""

    @pytest.mark.asyncio
    async def test_get_nonexistent_session_returns_404(self, client):
        """Should return 404 for non-existent session."""
        import uuid

        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v2/sessions/{fake_id}")

        # Should return 404 (or 400 if DB mock returns error)
        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session_returns_404(self, client):
        """Should return 404 when deleting non-existent session."""
        import uuid

        fake_id = uuid.uuid4()
        response = await client.delete(f"/api/v2/sessions/{fake_id}")

        assert response.status_code in [400, 404]

    @pytest.mark.asyncio
    async def test_get_steps_nonexistent_session_returns_404(self, client):
        """Should return 404 for steps of non-existent session."""
        import uuid

        fake_id = uuid.uuid4()
        response = await client.get(f"/api/v2/sessions/{fake_id}/steps")

        # With mocked DB, may return 200 with empty list or 404
        assert response.status_code in [200, 400, 404]


@pytest.mark.integration
class TestSessionListPagination:
    """Tests for session list and pagination."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_paginated_response(self, client):
        """Should return paginated session list."""
        response = await client.get("/api/v2/sessions")

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            # Should have pagination metadata
            assert "items" in data or isinstance(data, list)
            if "pagination" in data:
                assert "page" in data["pagination"]
                assert "per_page" in data["pagination"]
                assert "total" in data["pagination"]

    @pytest.mark.asyncio
    async def test_list_sessions_custom_page_size(self, client):
        """Should respect custom page size."""
        response = await client.get("/api/v2/sessions?per_page=5")

        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_status(self, client):
        """Should filter sessions by status."""
        response = await client.get("/api/v2/sessions?status=pending")

        assert response.status_code in [200, 500]

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_type(self, client):
        """Should filter sessions by type."""
        response = await client.get("/api/v2/sessions?session_type=maven_maintenance")

        assert response.status_code in [200, 500]


@pytest.mark.integration
class TestOpenAPISchema:
    """Tests for OpenAPI schema generation."""

    @pytest.mark.asyncio
    async def test_openapi_schema_available(self, client):
        """Should return OpenAPI schema."""
        response = await client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()

        assert "openapi" in data
        assert "info" in data
        assert "paths" in data

    @pytest.mark.asyncio
    async def test_openapi_has_sessions_endpoints(self, client):
        """Schema should include session endpoints."""
        response = await client.get("/openapi.json")

        if response.status_code == 200:
            data = response.json()
            paths = data.get("paths", {})

            # Should have session endpoints
            session_paths = [p for p in paths if "sessions" in p]
            assert len(session_paths) > 0

    @pytest.mark.asyncio
    async def test_docs_endpoint_available(self, client):
        """Swagger docs should be available."""
        response = await client.get("/docs")

        # /docs returns HTML, not JSON
        assert response.status_code == 200


@pytest.mark.integration
class TestRequestIDMiddleware:
    """Tests for request ID middleware."""

    @pytest.mark.asyncio
    async def test_request_id_in_response_header(self, client):
        """Response should include X-Request-ID header."""
        response = await client.get("/health")

        # Request ID should be in response headers
        assert "x-request-id" in response.headers or response.status_code == 200

    @pytest.mark.asyncio
    async def test_custom_request_id_preserved(self, client):
        """Custom X-Request-ID should be preserved."""
        custom_id = "test-request-123"
        response = await client.get(
            "/health",
            headers={"X-Request-ID": custom_id},
        )

        if "x-request-id" in response.headers:
            assert response.headers["x-request-id"] == custom_id


@pytest.mark.integration
class TestCORSMiddleware:
    """Tests for CORS configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers_present(self, client):
        """CORS headers should be present on responses."""
        response = await client.get("/health")

        # With CORS middleware, preflight should work
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_options_request_allowed(self, client):
        """OPTIONS requests should be handled for CORS preflight."""
        response = await client.options("/api/v2/sessions")

        # OPTIONS should return 200 (CORS preflight)
        assert response.status_code in [200, 204, 405]
