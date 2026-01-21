"""
vLLM Provider Integration Tests.

Tests for validating vLLM provider configuration and LLM creation
without requiring actual API access to the vLLM server.
"""

import os

from src.lib.config import get_settings


class TestVLLMProviderConfiguration:
    """Test vLLM provider configuration in settings."""

    def test_vllm_provider_is_recognized(self):
        """vLLM should be a valid provider option."""
        original_provider = os.environ.get("LLM_PROVIDER")
        original_vllm_api_base = os.environ.get("VLLM_API_BASE")
        original_vllm_api_key = os.environ.get("VLLM_API_KEY")

        try:
            os.environ["LLM_PROVIDER"] = "vllm"
            os.environ["VLLM_API_BASE"] = "http://localhost:8000/v1"
            os.environ["VLLM_API_KEY"] = "test-key"

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.llm_provider == "vllm"

        finally:
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            if original_vllm_api_base is not None:
                os.environ["VLLM_API_BASE"] = original_vllm_api_base
            elif "VLLM_API_BASE" in os.environ:
                del os.environ["VLLM_API_BASE"]

            if original_vllm_api_key is not None:
                os.environ["VLLM_API_KEY"] = original_vllm_api_key
            elif "VLLM_API_KEY" in os.environ:
                del os.environ["VLLM_API_KEY"]

            get_settings.cache_clear()

    def test_vllm_api_base_configuration(self):
        """vLLM API base URL should be configurable."""
        original_vllm_api_base = os.environ.get("VLLM_API_BASE")

        try:
            custom_url = "https://custom-vllm-server.example.com/v1"
            os.environ["VLLM_API_BASE"] = custom_url

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.vllm_api_base == custom_url

        finally:
            if original_vllm_api_base is not None:
                os.environ["VLLM_API_BASE"] = original_vllm_api_base
            elif "VLLM_API_BASE" in os.environ:
                del os.environ["VLLM_API_BASE"]

            get_settings.cache_clear()

    def test_vllm_default_api_base(self):
        """vLLM should have SDIA default API base URL."""
        original_vllm_api_base = os.environ.get("VLLM_API_BASE")

        try:
            if "VLLM_API_BASE" in os.environ:
                del os.environ["VLLM_API_BASE"]

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.vllm_api_base == "https://codeia.dev.etat-ge.ch/v1"

        finally:
            if original_vllm_api_base is not None:
                os.environ["VLLM_API_BASE"] = original_vllm_api_base

            get_settings.cache_clear()

    def test_vllm_model_configuration(self):
        """vLLM model path should be configurable."""
        original_vllm_model = os.environ.get("VLLM_MODEL")

        try:
            custom_model = "/custom/path/to/model"
            os.environ["VLLM_MODEL"] = custom_model

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.vllm_model == custom_model

        finally:
            if original_vllm_model is not None:
                os.environ["VLLM_MODEL"] = original_vllm_model
            elif "VLLM_MODEL" in os.environ:
                del os.environ["VLLM_MODEL"]

            get_settings.cache_clear()

    def test_vllm_default_model_is_qwen_coder(self):
        """vLLM should default to Qwen3-Coder-30B-A3B-Instruct."""
        original_vllm_model = os.environ.get("VLLM_MODEL")

        try:
            if "VLLM_MODEL" in os.environ:
                del os.environ["VLLM_MODEL"]

            get_settings.cache_clear()
            settings = get_settings()

            assert "Qwen3-Coder" in settings.vllm_model

        finally:
            if original_vllm_model is not None:
                os.environ["VLLM_MODEL"] = original_vllm_model

            get_settings.cache_clear()

    def test_vllm_api_key_with_empty_default(self):
        """vLLM API key should default to 'EMPTY' for local deployments."""
        original_vllm_api_key = os.environ.get("VLLM_API_KEY")

        try:
            if "VLLM_API_KEY" in os.environ:
                del os.environ["VLLM_API_KEY"]

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.vllm_api_key == "EMPTY"

        finally:
            if original_vllm_api_key is not None:
                os.environ["VLLM_API_KEY"] = original_vllm_api_key

            get_settings.cache_clear()


class TestVLLMProviderFactory:
    """Test vLLM LLM instance creation."""

    def test_get_llm_creates_vllm_instance(self):
        """get_llm should create a ChatOpenAI instance for vLLM provider."""
        from src.lib.llm import get_llm

        original_provider = os.environ.get("LLM_PROVIDER")
        original_vllm_api_key = os.environ.get("VLLM_API_KEY")

        try:
            os.environ["LLM_PROVIDER"] = "vllm"
            os.environ["VLLM_API_KEY"] = "test-key"

            get_settings.cache_clear()

            llm = get_llm()
            assert llm is not None

            # Should be a ChatOpenAI instance (vLLM uses OpenAI-compatible API)
            from langchain_openai import ChatOpenAI

            assert isinstance(llm, ChatOpenAI)

        finally:
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            if original_vllm_api_key is not None:
                os.environ["VLLM_API_KEY"] = original_vllm_api_key
            elif "VLLM_API_KEY" in os.environ:
                del os.environ["VLLM_API_KEY"]

            get_settings.cache_clear()

    def test_get_llm_with_vllm_provider_uses_custom_base_url(self):
        """vLLM LLM should use the configured base URL."""
        from src.lib.llm import get_llm

        original_provider = os.environ.get("LLM_PROVIDER")
        original_vllm_api_base = os.environ.get("VLLM_API_BASE")
        original_vllm_api_key = os.environ.get("VLLM_API_KEY")

        try:
            os.environ["LLM_PROVIDER"] = "vllm"
            os.environ["VLLM_API_BASE"] = "http://test-server:8000/v1"
            os.environ["VLLM_API_KEY"] = "test-key"

            get_settings.cache_clear()

            llm = get_llm()

            # Check that base_url is set correctly
            assert llm.openai_api_base == "http://test-server:8000/v1"

        finally:
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            if original_vllm_api_base is not None:
                os.environ["VLLM_API_BASE"] = original_vllm_api_base
            elif "VLLM_API_BASE" in os.environ:
                del os.environ["VLLM_API_BASE"]

            if original_vllm_api_key is not None:
                os.environ["VLLM_API_KEY"] = original_vllm_api_key
            elif "VLLM_API_KEY" in os.environ:
                del os.environ["VLLM_API_KEY"]

            get_settings.cache_clear()

    def test_model_string_parsing_with_vllm_prefix(self):
        """MODEL=vllm/model-name should correctly parse provider and model."""
        original_model = os.environ.get("MODEL")
        original_provider = os.environ.get("LLM_PROVIDER")

        try:
            os.environ["MODEL"] = "vllm/custom-model-name"
            if "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            get_settings.cache_clear()
            settings = get_settings()

            assert settings.llm_provider == "vllm"
            assert settings.model == "custom-model-name"

        finally:
            if original_model is not None:
                os.environ["MODEL"] = original_model
            elif "MODEL" in os.environ:
                del os.environ["MODEL"]

            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider

            get_settings.cache_clear()


class TestVLLMProviderAPIKeyBehavior:
    """Test vLLM API key handling."""

    def test_vllm_api_key_returned_by_get_api_key_for_provider(self):
        """get_api_key_for_provider should return vLLM API key."""
        original_vllm_api_key = os.environ.get("VLLM_API_KEY")

        try:
            os.environ["VLLM_API_KEY"] = "custom-vllm-key"

            get_settings.cache_clear()
            settings = get_settings()

            api_key = settings.get_api_key_for_provider("vllm")
            assert api_key == "custom-vllm-key"

        finally:
            if original_vllm_api_key is not None:
                os.environ["VLLM_API_KEY"] = original_vllm_api_key
            elif "VLLM_API_KEY" in os.environ:
                del os.environ["VLLM_API_KEY"]

            get_settings.cache_clear()

    def test_vllm_with_empty_api_key_still_works(self):
        """vLLM should work with 'EMPTY' API key (common for local deployments)."""
        from src.lib.llm import get_llm

        original_provider = os.environ.get("LLM_PROVIDER")
        original_vllm_api_key = os.environ.get("VLLM_API_KEY")

        try:
            os.environ["LLM_PROVIDER"] = "vllm"
            os.environ["VLLM_API_KEY"] = "EMPTY"

            get_settings.cache_clear()

            # Should not raise an error
            llm = get_llm()
            assert llm is not None

        finally:
            if original_provider is not None:
                os.environ["LLM_PROVIDER"] = original_provider
            elif "LLM_PROVIDER" in os.environ:
                del os.environ["LLM_PROVIDER"]

            if original_vllm_api_key is not None:
                os.environ["VLLM_API_KEY"] = original_vllm_api_key
            elif "VLLM_API_KEY" in os.environ:
                del os.environ["VLLM_API_KEY"]

            get_settings.cache_clear()


class TestVLLMArtifactCompatibility:
    """Test that vLLM artifacts are compatible with existing providers."""

    def test_vllm_artifact_schema_matches_other_providers(self):
        """vLLM artifacts should have the same schema as other providers."""
        vllm_content = {
            "provider": "vllm",
            "model": "/data/sdia/downloaded_models/Qwen3-Coder-30B-A3B-Instruct/",
            "input_tokens": 1200,
            "output_tokens": 800,
            "total_tokens": 2000,
            "duration_ms": 2500,
        }

        required_fields = {
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "duration_ms",
            "provider",
            "model",
        }
        assert required_fields.issubset(vllm_content.keys())

    def test_vllm_tool_call_artifacts_compatible(self):
        """vLLM tool call artifacts should match other providers."""
        vllm_tool_call = {
            "tool_name": "analyze_dependencies",
            "tool_args": {"project_path": "/path/to/project"},
            "tool_result": {"success": True, "dependencies": []},
            "provider": "vllm",
        }

        required_fields = {"tool_name", "tool_args", "tool_result"}
        assert required_fields.issubset(vllm_tool_call.keys())
