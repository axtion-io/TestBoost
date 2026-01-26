"""Tests for CLI main module, including LangSmith initialization."""

import os
from unittest.mock import MagicMock, patch

import pytest


class TestCLILangSmithInitialization:
    """Tests for CLI LangSmith tracing initialization."""

    def test_langsmith_tracing_enabled(self) -> None:
        """Test that LangSmith env vars are set when tracing is enabled."""
        mock_settings = MagicMock()
        mock_settings.langsmith_tracing = True
        mock_settings.langsmith_api_key = "test-cli-api-key"
        mock_settings.langsmith_project = "test-cli-project"

        with patch("src.cli.main.settings", mock_settings):
            # Clear any existing env vars
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

            # Import and call the function
            from src.cli.main import _initialize_langsmith_tracing

            _initialize_langsmith_tracing()

            # Verify env vars are set
            assert os.environ.get("LANGCHAIN_TRACING_V2") == "true"
            assert os.environ.get("LANGCHAIN_API_KEY") == "test-cli-api-key"
            assert os.environ.get("LANGCHAIN_PROJECT") == "test-cli-project"

            # Clean up
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

    def test_langsmith_tracing_disabled_no_flag(self) -> None:
        """Test that LangSmith env vars are not set when tracing is disabled."""
        mock_settings = MagicMock()
        mock_settings.langsmith_tracing = False
        mock_settings.langsmith_api_key = "test-api-key"
        mock_settings.langsmith_project = "test-project"

        with patch("src.cli.main.settings", mock_settings):
            # Clear any existing env vars
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

            from src.cli.main import _initialize_langsmith_tracing

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

        with patch("src.cli.main.settings", mock_settings):
            # Clear any existing env vars
            for key in ["LANGCHAIN_TRACING_V2", "LANGCHAIN_API_KEY", "LANGCHAIN_PROJECT"]:
                os.environ.pop(key, None)

            from src.cli.main import _initialize_langsmith_tracing

            _initialize_langsmith_tracing()

            # Verify env vars are NOT set
            assert os.environ.get("LANGCHAIN_TRACING_V2") is None
            assert os.environ.get("LANGCHAIN_API_KEY") is None
            assert os.environ.get("LANGCHAIN_PROJECT") is None


class TestCLIAppConfiguration:
    """Tests for Typer CLI app configuration."""

    def test_app_name(self) -> None:
        """Test that CLI app has correct name."""
        from src.cli.main import app

        assert app.info.name == "testboost"

    def test_app_help(self) -> None:
        """Test that CLI app has help text."""
        from src.cli.main import app

        assert "AI-powered" in app.info.help

    def test_app_no_args_is_help(self) -> None:
        """Test that CLI shows help when no args provided."""
        from src.cli.main import app

        assert app.info.no_args_is_help is True


class TestVersionCallback:
    """Tests for version callback."""

    def test_version_callback_prints_version(self) -> None:
        """Test that version callback prints version."""
        import typer

        from src.cli.main import version_callback

        with pytest.raises(typer.Exit):
            version_callback(True)

    def test_version_callback_no_action_when_false(self) -> None:
        """Test that version callback does nothing when False."""
        from src.cli.main import version_callback

        # Should not raise
        result = version_callback(False)
        assert result is None
