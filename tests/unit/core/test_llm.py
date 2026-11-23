"""LLM factory, metrics callback and connection diagnostics.

docs/llm-providers.md: one of Anthropic / Gemini / OpenAI(-compatible,
e.g. vLLM via OPENAI_API_BASE) is selected from the settings; a missing key
or unreachable provider must fail loudly with an actionable message.
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.lib.config import Settings
from src.lib.llm import LLMError, LLMProviderError, get_llm
from src.lib.llm_callbacks import LLMMetricsCallback
from src.lib.startup_checks import check_llm_connection


def _with_settings(**values):
    settings = Settings(_env_file=None, **values)
    return patch("src.lib.llm.get_settings", return_value=settings)


class TestFactory:
    def test_anthropic_model_with_metrics_callback(self):
        with _with_settings(model="anthropic/claude-sonnet-4-6", anthropic_api_key="k"):
            llm = get_llm()
        assert type(llm).__name__ == "ChatAnthropic"
        assert llm.model == "claude-sonnet-4-6"
        assert any(isinstance(cb, LLMMetricsCallback) for cb in llm.callbacks)

    def test_openai_compatible_endpoint_uses_base_url(self):
        with _with_settings(model="openai/qwen3", openai_api_key="k",
                            openai_api_base="http://vllm.local:8000/v1"):
            llm = get_llm()
        assert type(llm).__name__ == "ChatOpenAI"
        assert str(llm.openai_api_base) == "http://vllm.local:8000/v1"

    def test_google_provider_with_a_non_gemini_default_model(self):
        """LLM_PROVIDER=google-genai with the (Claude) default MODEL must not
        send a Claude model name to Gemini."""
        with _with_settings(llm_provider="google-genai", google_api_key="k"):
            llm = get_llm()
        assert type(llm).__name__ == "ChatGoogleGenerativeAI"
        assert "gemini" in llm.model

    def test_missing_key_names_the_variables_to_set(self):
        with _with_settings(model="openai/gpt-4o"), pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            get_llm()


class TestMetricsCallback:
    def _logs(self, error):
        cb = LLMMetricsCallback(provider="openai", model="m")
        with patch("src.lib.llm_callbacks.logger") as logger:
            cb.on_llm_start({}, ["p"])
            cb.on_llm_error(error)
        return logger

    def test_rate_limits_are_warnings(self):
        logger = self._logs(RuntimeError("429 quota exceeded"))
        assert logger.warning.call_args.args[0] == "llm_rate_limit"
        logger.error.assert_not_called()

    def test_other_errors_keep_the_cause_chain(self):
        try:
            try:
                raise ConnectionError("proxy refused")
            except ConnectionError as cause:
                raise RuntimeError("request failed") from cause
        except RuntimeError as err:
            logger = self._logs(err)
        kwargs = logger.error.call_args.kwargs
        assert kwargs["cause_chain"] == ["ConnectionError: proxy refused"]
        assert kwargs["duration_seconds"] is not None


class TestConnectionDiagnostics:
    @pytest.mark.parametrize(
        ("raised", "hint"),
        [
            (FileNotFoundError("/etc/ssl/corp.pem"), "SSL_CERT_FILE"),
            (OSError("network unreachable"), "proxy"),
            (RuntimeError("boom"), "boom"),
        ],
    )
    @pytest.mark.asyncio
    async def test_setup_errors_become_actionable_llm_errors(self, raised, hint):
        with patch("src.lib.startup_checks.get_llm", side_effect=raised), \
             pytest.raises(LLMError, match=hint):
            await check_llm_connection()

    @pytest.mark.asyncio
    async def test_successful_ping(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = "pong"
        with patch("src.lib.startup_checks.get_llm", return_value=llm):
            await check_llm_connection()
        llm.ainvoke.assert_awaited_once()
