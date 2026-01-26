"""Tests for API main module, including LangSmith initialization."""

import os
from unittest.mock import MagicMock, patch


class TestLangSmithInitialization:
    """Tests for LangSmith tracing initialization."""

    def test_langsmith_tracing_enabled(self) -> None:
        """Test that LangSmith env vars are set when tracing is enabled."""
        mock_settings = MagicMock()
        mock_settings.langsmith_tracing = True
        mock_settings.langsmith_api_key = "test-api-key"
        mock_settings.langsmith_project = "test-project"

        with patch("src.api.main.settings", mock_settings):
            # Clear any existing env vars
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

            # Import and call the function
            from src.api.main import _initialize_langsmith_tracing

            _initialize_langsmith_tracing()

            # Verify env vars are set
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
            assert os.environ.get("LANGCHAIN_API_KEY") == "test-api-key"
            assert os.environ.get("LANGCHAIN_PROJECT") == "test-project"

            # Clean up
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

    def test_langsmith_tracing_disabled_no_flag(self) -> None:
        """Test that LangSmith env vars are not set when tracing is disabled."""
        mock_settings = MagicMock()
        mock_settings.langsmith_tracing = False
        mock_settings.langsmith_api_key = "test-api-key"
        mock_settings.langsmith_project = "test-project"

        with patch("src.api.main.settings", mock_settings):
            # Clear any existing env vars
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

            from src.api.main import _initialize_langsmith_tracing

            _initialize_langsmith_tracing()

            # Verify env vars are NOT set
            assert os.environ.get("LANGCHAIN_TRACING_V2") is None
            assert os.environ.get("LANGCHAIN_API_KEY") is None
            assert os.environ.get("LANGCHAIN_PROJECT") is None

    def test_langsmith_tracing_disabled_no_api_key(self) -> None:
        """Test that LangSmith env vars are not set when API key is missing."""
        mock_settings = MagicMock()
        mock_settings.langsmith_tracing = True
        mock_settings.langsmith_api_key = None
        mock_settings.langsmith_project = "test-project"

        with patch("src.api.main.settings", mock_settings):
            # Clear any existing env vars
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

            from src.api.main import _initialize_langsmith_tracing

            _initialize_langsmith_tracing()

            # Verify env vars are NOT set
            assert os.environ.get("LANGCHAIN_TRACING_V2") is None
            assert os.environ.get("LANGCHAIN_API_KEY") is None
            assert os.environ.get("LANGCHAIN_PROJECT") is None


class TestAppConfiguration:
    """Tests for FastAPI app configuration."""

    def test_app_title(self) -> None:
        """Test that app has correct title."""
        from src.api.main import app

        assert app.title == "TestBoost API"

    def test_app_version(self) -> None:
        """Test that app has version set."""
        from src.api.main import app

        assert app.version == "0.1.0"

    def test_app_docs_url(self) -> None:
        """Test that docs URL is configured."""
        from src.api.main import app

        assert app.docs_url == "/docs"

    def test_app_openapi_url(self) -> None:
        """Test that OpenAPI URL is configured."""
        from src.api.main import app

        assert app.openapi_url == "/openapi.json"


class TestOpenAPIExport:
    """Tests for OpenAPI schema export functionality."""

    def test_generate_openapi_schema(self) -> None:
        """Test that OpenAPI schema can be generated."""
        from src.api.main import generate_openapi_schema

        schema = generate_openapi_schema()

        assert isinstance(schema, dict)
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        assert schema["info"]["title"] == "TestBoost API"
