"""Settings: provider selection from MODEL and per-provider API keys.

docs/llm-providers.md: `MODEL=<provider>/<model>` selects the provider; a
bare model name keeps LLM_PROVIDER; filesystem paths (local vLLM models)
are passed through untouched.
"""

import pytest

from src.lib.config import Settings


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch):
    for var in ("MODEL", "LLM_PROVIDER", "ANTHROPIC_API_KEY", "GOOGLE_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)


def _settings(**env) -> Settings:
    return Settings(_env_file=None, **env)


@pytest.mark.parametrize(
    ("model", "provider", "name"),
    [
        ("google-genai/gemini-2.5-flash", "google-genai", "gemini-2.5-flash"),
        ("google/gemini-2.5-pro", "google-genai", "gemini-2.5-pro"),
        ("openai/gpt-4o", "openai", "gpt-4o"),
        ("anthropic/claude-sonnet-4-6", "anthropic", "claude-sonnet-4-6"),
    ],
)
def test_provider_prefix_selects_provider(model, provider, name):
    s = _settings(model=model, llm_provider="anthropic")
    assert (s.llm_provider, s.model) == (provider, name)


@pytest.mark.parametrize("model", ["/data/models/Qwen3/", "C:\\models\\qwen", "Qwen/Qwen3-8B"])
def test_paths_and_unknown_prefixes_are_left_untouched(model):
    s = _settings(model=model, llm_provider="openai")
    assert (s.llm_provider, s.model) == ("openai", model)


def test_api_key_follows_the_selected_provider():
    s = _settings(model="openai/gpt-4o", anthropic_api_key="a", openai_api_key="o")
    assert s.get_api_key_for_provider() == "o"
    assert s.get_api_key_for_provider("anthropic") == "a"
    assert s.get_api_key_for_provider("google-genai") is None


def test_environment_variables_are_read(monkeypatch):
    monkeypatch.setenv("MODEL", "google/gemini-2.5-flash")
    monkeypatch.setenv("GOOGLE_API_KEY", "g")
    s = Settings(_env_file=None)
    assert s.llm_provider == "google-genai"
    assert s.get_api_key_for_provider() == "g"
