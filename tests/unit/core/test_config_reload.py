"""Tests for configuration functionality."""

import os
from unittest.mock import patch


class TestSettings:
    """Tests for application settings."""

    def test_settings_class_exists(self):
        """Settings class should be importable."""
        from src.lib.config import Settings

        assert Settings is not None

    def test_get_settings_function_exists(self):
        """get_settings function should exist."""
        from src.lib.config import get_settings

        assert callable(get_settings)

    def test_settings_has_default_values(self):
        """Settings should have sensible defaults."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings.app_name == "TestBoost"
        assert settings.log_level in ["DEBUG", "INFO", "WARNING", "ERROR"]

    def test_settings_database_url_default(self):
        """Settings should have default database URL."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings.database_url is not None
        assert "postgresql" in settings.database_url

    def test_settings_llm_provider_default(self):
        """Settings should have default LLM provider."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings.llm_provider in ["anthropic", "google-genai", "openai"]

    def test_settings_timeout_values(self):
        """Settings should have timeout values."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings.llm_timeout > 0
        assert settings.startup_timeout > 0

    def test_settings_retry_config(self):
        """Settings should have retry configuration."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings.max_retries > 0

    def test_settings_retention_config(self):
        """Settings should have data retention configuration."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings.session_retention_days > 0

    def test_settings_can_be_overridden_by_env(self):
        """Settings should respect environment variables."""
        with patch.dict(os.environ, {"DEBUG": "true"}):
            # Force reload of settings
            from src.lib.config import Settings

            settings = Settings()
            assert settings.debug is True


class TestConfigCaching:
    """Tests for configuration caching."""

    def test_get_settings_cached(self):
        """get_settings should return cached instance."""
        from src.lib.config import get_settings

        settings1 = get_settings()
        settings2 = get_settings()
        # Should be the same cached instance
        assert settings1 is settings2
