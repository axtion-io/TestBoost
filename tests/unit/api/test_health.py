"""Tests for health endpoint."""

import pytest
from unittest.mock import patch, MagicMock


class TestHealthEndpoint:
    """Tests for the /health endpoint."""

    @pytest.mark.asyncio
    async def test_health_returns_200(self, client):
        """Health endpoint should return 200 status code."""
        response = await client.get("/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_health_returns_healthy_status(self, client):
        """Health endpoint should return healthy status in response body."""
        response = await client.get("/health")
        data = response.json()
        assert data.get("status") == "healthy"

    @pytest.mark.asyncio
    async def test_health_returns_version(self, client):
        """Health endpoint should include version information."""
        response = await client.get("/health")
        data = response.json()
        assert "version" in data

    @pytest.mark.asyncio
    async def test_health_response_format(self, client):
        """Health endpoint should return expected JSON structure."""
        response = await client.get("/health")
        data = response.json()
        assert isinstance(data, dict)
        required_fields = {"status"}
        assert required_fields.issubset(data.keys())
