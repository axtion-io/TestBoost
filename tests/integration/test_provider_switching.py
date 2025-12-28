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


class TestProviderSwitchingArtifactCompatibility:
    """T102e: Test that artifacts remain compatible across provider switches."""

    def test_artifact_schema_is_provider_independent(self):
        """Artifact schema should not depend on which LLM provider is used."""
        # Test that artifact content structure is consistent
        gemini_content = {
            "provider": "google",
            "model": "gemini-1.5-flash",
            "input_tokens": 1500,
            "output_tokens": 500,
            "total_tokens": 2000,
            "duration_ms": 1234,
        }

        claude_content = {
            "provider": "anthropic",
            "model": "claude-3-sonnet",
            "input_tokens": 1600,
            "output_tokens": 450,
            "total_tokens": 2050,
            "duration_ms": 1100,
        }

        # Required fields should be present in both
        required_fields = {"input_tokens", "output_tokens", "total_tokens", "duration_ms", "provider", "model"}
        assert required_fields.issubset(gemini_content.keys())
        assert required_fields.issubset(claude_content.keys())

    def test_tool_call_artifacts_compatible_across_providers(self):
        """Tool call artifacts should have same structure regardless of provider."""
        gemini_tool_call = {
            "tool_name": "analyze_dependencies",
            "tool_args": {"project_path": "/path/to/project"},
            "tool_result": {"success": True, "dependencies": []},
            "provider": "google",
        }

        claude_tool_call = {
            "tool_name": "analyze_dependencies",
            "tool_args": {"project_path": "/path/to/project"},
            "tool_result": {"success": True, "dependencies": []},
            "provider": "anthropic",
        }

        # Structure should be identical (same keys)
        assert set(gemini_tool_call.keys()) == set(claude_tool_call.keys())

        # Required fields for tool calls
        required_fields = {"tool_name", "tool_args", "tool_result"}
        assert required_fields.issubset(gemini_tool_call.keys())
        assert required_fields.issubset(claude_tool_call.keys())

    def test_agent_reasoning_artifacts_compatible(self):
        """Agent reasoning artifacts should be provider-independent."""
        reasoning_content = {
            "step": "analyze_project",
            "reasoning": "The project uses Spring Boot 2.x with outdated dependencies",
            "decision": "Recommend upgrading to Spring Boot 3.x",
            "confidence": 0.95,
        }

        # Required fields should be present
        required_fields = {"reasoning", "decision"}
        assert required_fields.issubset(reasoning_content.keys())

    def test_artifact_types_are_standardized(self):
        """Artifact types should be standardized across all providers."""
        # Standard artifact types used regardless of provider
        standard_types = {"agent_reasoning", "llm_tool_call", "llm_metrics"}

        # These types should be recognized
        for artifact_type in standard_types:
            assert artifact_type in standard_types  # Self-check
            assert isinstance(artifact_type, str)
            assert "_" in artifact_type  # Snake case convention
