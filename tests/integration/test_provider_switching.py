"""
Provider Switching Integration Tests (T102c-e).

Tests for validating LLM provider switching behavior without requiring
actual API keys. These tests mock the LLM calls and verify the configuration
and startup behavior.
"""

import os

import pytest

from src.lib.config import get_settings


class TestProviderSwitchingWithInvalidKey:
    """T102c: Test provider switching with invalid API key."""

    def test_switch_provider_with_invalid_api_key_raises_error(self):
        """Changing provider to anthropic with invalid key should fail at startup."""
        from src.lib.llm import LLMProviderError, get_llm

        # Save original env vars
        original_provider = os.environ.get("LLM_PROVIDER")
        original_google_key = os.environ.get("GOOGLE_API_KEY")
        original_anthropic_key = os.environ.get("ANTHROPIC_API_KEY")

        try:
            # Set provider to anthropic without valid key
            os.environ["LLM_PROVIDER"] = "anthropic"
            # Remove Google key to force anthropic
            if "GOOGLE_API_KEY" in os.environ:
                del os.environ["GOOGLE_API_KEY"]
            # Set invalid anthropic key
            os.environ["ANTHROPIC_API_KEY"] = ""

            # Clear settings cache to force reload
            get_settings.cache_clear()

            # Attempting to get LLM should raise LLMProviderError
            with pytest.raises(LLMProviderError) as exc_info:
                get_llm()

            # Error should mention API key or configuration issue
            error_msg = str(exc_info.value).lower()
            assert any(
                term in error_msg for term in ["api key", "not configured", "missing", "empty"]
            )

        finally:
            # Restore original env vars
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            if original_google_key is not None:
                os.environ["GOOGLE_API_KEY"] = original_google_key

            if original_anthropic_key is not None:
                os.environ["ANTHROPIC_API_KEY"] = original_anthropic_key
            elif "ANTHROPIC_API_KEY" in os.environ:
                del os.environ["ANTHROPIC_API_KEY"]

            get_settings.cache_clear()

    def test_get_llm_validates_provider_setting(self):
        """get_llm should use the configured provider from settings."""
        from src.lib.llm import get_llm

        # Just verify get_llm can be called with valid configuration
        # The actual API key validation happens at invocation time
        original_provider = os.environ.get("LLM_PROVIDER")
        original_google_key = os.environ.get("GOOGLE_API_KEY")

        try:
            # Ensure we have a valid provider set
            os.environ["LLM_PROVIDER"] = "google-genai"
            if "GOOGLE_API_KEY" not in os.environ:
                os.environ["GOOGLE_API_KEY"] = "test-key-for-instantiation"

            get_settings.cache_clear()

            # get_llm should return an LLM instance without raising
            llm = get_llm()
            assert llm is not None

        finally:
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            if original_google_key is not None:
                os.environ["GOOGLE_API_KEY"] = original_google_key

            get_settings.cache_clear()


class TestProviderSwitchingWithoutRestart:
    """T102d: Test that env var changes during runtime have no effect until restart."""

    def test_env_var_change_during_runtime_no_effect(self):
        """Changing LLM_PROVIDER env var during runtime should not affect cached settings."""
        original_provider = os.environ.get("LLM_PROVIDER")

        try:
            # Set initial provider (use valid provider name)
            os.environ["LLM_PROVIDER"] = "google-genai"
            get_settings.cache_clear()

            # Get initial settings (this caches)
            settings1 = get_settings()
            initial_provider = settings1.llm_provider

            # Change env var (simulating runtime change without restart)
            os.environ["LLM_PROVIDER"] = "openai"

            # Settings should still return cached value (no restart)
            settings2 = get_settings()
            current_provider = settings2.llm_provider

            # Provider should be the same (cached) - no effect without restart
            assert initial_provider == current_provider
            assert current_provider == "google-genai"

            # Only after cache clear (simulating restart) should it change
            get_settings.cache_clear()
            settings3 = get_settings()
            new_provider = settings3.llm_provider

            assert new_provider == "openai"

        finally:
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            get_settings.cache_clear()

    def test_settings_caching_prevents_runtime_changes(self):
        """Settings should be cached, preventing runtime env var changes from taking effect."""
        # Clear cache first
        get_settings.cache_clear()

        # Get settings - this should cache
        settings1 = get_settings()

        # Get settings again - should return cached instance
        settings2 = get_settings()

        # Should be the same cached instance
        assert settings1 is settings2
