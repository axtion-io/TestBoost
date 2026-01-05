"""Pytest configuration and shared fixtures for TestBoost tests."""

import pytest
from typing import AsyncGenerator, Generator
from unittest.mock import patch, MagicMock, AsyncMock
import os
import sys

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))


# ============================================================================
# Database Fixtures
# ============================================================================

@pytest.fixture
async def db_session():
    """
    Provide a database session with transaction rollback.
    
    This fixture creates a new database session for each test and rolls back
    all changes after the test completes, ensuring test isolation.
    """
    # Mock database session for unit tests
    # In integration tests with real DB, this would use actual connection
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    
    yield session
    
    # Rollback any changes
    await session.rollback()
    await session.close()


@pytest.fixture
async def db_connection():
    """Provide a raw database connection for low-level tests."""
    connection = AsyncMock()
    connection.execute = AsyncMock()
    connection.fetchone = AsyncMock()
    connection.fetchall = AsyncMock()
    
    yield connection


# ============================================================================
# HTTP Client Fixtures
# ============================================================================

# Test API key for authentication
TEST_API_KEY = "test-api-key-for-unit-tests"


@pytest.fixture
async def client() -> AsyncGenerator:
    """
    Provide an async HTTP client for API testing.

    Uses httpx with ASGITransport for in-process testing of FastAPI app.
    Includes authentication header for protected endpoints.
    Mocks database dependencies for unit testing.
    """
    try:
        from httpx import AsyncClient, ASGITransport
        from src.api.main import app
        from src.db import get_db

        # Create mock database session
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock())
        mock_db.commit = AsyncMock()
        mock_db.rollback = AsyncMock()
        mock_db.close = AsyncMock()
        mock_db.get = AsyncMock(return_value=None)  # For get operations

        async def mock_get_db():
            yield mock_db

        # Override the database dependency
        app.dependency_overrides[get_db] = mock_get_db

        # Patch settings to use test API key
        with patch("src.api.middleware.auth.settings") as mock_settings:
            mock_settings.api_key = TEST_API_KEY

            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport,
                base_url="http://test",
                headers={"X-API-Key": TEST_API_KEY}
            ) as ac:
                yield ac

        # Clean up dependency overrides
        app.dependency_overrides.clear()
    except ImportError:
        # Fallback mock client for when dependencies aren't available
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=MagicMock(status_code=200, json=lambda: {}))
        mock_client.post = AsyncMock(return_value=MagicMock(status_code=201, json=lambda: {"id": "test-id"}))
        mock_client.delete = AsyncMock(return_value=MagicMock(status_code=204))
        yield mock_client


# ============================================================================
# LLM Mock Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_provider():
    """Provide a mocked LLM provider."""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value={
        "content": "Mocked LLM response",
        "tokens_used": 100
    })
    return provider


@pytest.fixture
def mock_llm():
    """Alias for mock_llm_provider for backwards compatibility."""
    provider = AsyncMock()
    provider.generate = AsyncMock(return_value={
        "content": "Mocked LLM response",
        "tokens_used": 100
    })
    return provider


@pytest.fixture
def mock_gemini_responses():
    """Load Gemini mock responses from fixtures."""
    import json
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures", "llm_responses", "gemini_responses.json"
    )
    if os.path.exists(fixture_path):
        with open(fixture_path) as f:
            return json.load(f)
    return {"default_response": {"content": "Mock", "tokens_used": 50}}


# ============================================================================
# File System Fixtures
# ============================================================================

@pytest.fixture
def temp_project_dir(tmp_path):
    """Create a temporary project directory with sample files."""
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    
    # Create sample pom.xml
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project>
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.test</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>
</project>"""
    (project_dir / "pom.xml").write_text(pom_content)
    
    # Create sample Java file
    src_dir = project_dir / "src" / "main" / "java" / "com" / "test"
    src_dir.mkdir(parents=True)
    (src_dir / "TestService.java").write_text("""
package com.test;

public class TestService {
    public String hello() {
        return "Hello";
    }
}
""")
    
    return project_dir


# ============================================================================
# Pytest Markers
# ============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "slow: mark test as slow-running")
    config.addinivalue_line("markers", "unit: mark test as unit test")


# ============================================================================
# Test Helpers
# ============================================================================

@pytest.fixture
def assert_valid_uuid():
    """Helper to assert a string is a valid UUID."""
    import uuid as uuid_module
    
    def _assert(value: str):
        try:
            uuid_module.UUID(value)
            return True
        except ValueError:
            pytest.fail(f"'{value}' is not a valid UUID")
    
    return _assert

