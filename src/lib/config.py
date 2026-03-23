"""Application configuration using pydantic-settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve .env relative to this file so it works regardless of CWD
_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    Environment variables take precedence over .env file values.
    """

    model_config = SettingsConfigDict(
        env_file=str(_ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(default="TestBoost Lite", description="Application name")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # LLM Provider settings
    llm_provider: Literal["anthropic", "google-genai", "openai"] = Field(
        default="anthropic",
        description="LLM provider to use",
    )
    model: str = Field(
        default="claude-sonnet-4-6",
        description="Default LLM model",
    )

    # API Keys (loaded from environment only for security)
    anthropic_api_key: str | None = Field(
        default=None,
        description="Anthropic API key",
    )
    google_api_key: str | None = Field(
        default=None,
        description="Google API key for Gemini",
    )
    openai_api_key: str | None = Field(
        default=None,
        description="OpenAI API key",
    )
    openai_api_base: str | None = Field(
        default=None,
        description="OpenAI-compatible API base URL (for vLLM, Ollama, etc.)",
    )

    # LangSmith tracing (optional)
    langsmith_api_key: str | None = Field(
        default=None,
        description="LangSmith API key for tracing",
    )
    langsmith_tracing: bool = Field(
        default=False,
        description="Enable LangSmith tracing",
    )
    langsmith_project: str = Field(
        default="testboost",
        description="LangSmith project name",
    )

    # Timeout settings
    llm_timeout: int = Field(
        default=120,
        description="LLM request timeout in seconds",
    )
    startup_timeout: int = Field(
        default=15,
        description="Startup check timeout in seconds (Gemini requires min 10s)",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for transient errors",
    )

    # Data retention settings
    session_retention_days: int = Field(
        default=30,
        description="Number of days to retain session data",
    )

    # Locking settings
    project_lock_timeout_seconds: int = Field(
        default=3600,
        description="Project lock timeout in seconds",
    )

    # API authentication
    api_key: str | None = Field(
        default=None,
        description="API key for authentication",
    )

    @model_validator(mode="after")
    def parse_model_provider(self) -> "Settings":
        """
        Parse provider from model string if format is 'provider/model-name'.

        Filesystem paths (starting with '/' or containing '\\') are left as-is.

        Examples:
            MODEL=google-genai/gemini-2.0-flash -> llm_provider=google-genai, model=gemini-2.0-flash
            MODEL=anthropic/claude-sonnet-4-5 -> llm_provider=anthropic, model=claude-sonnet-4-5
            MODEL=/data/models/Qwen3/ -> left unchanged (filesystem path)
        """
        if "/" in self.model and not self.model.startswith("/") and "\\" not in self.model:
            provider_part, model_part = self.model.split("/", 1)
            provider_mapping = {
                "google-genai": "google-genai",
                "google": "google-genai",
                "anthropic": "anthropic",
                "openai": "openai",
            }
            if provider_part in provider_mapping:
                # Override with parsed values (use object.__setattr__ for frozen model)
                object.__setattr__(self, "llm_provider", provider_mapping[provider_part])
                object.__setattr__(self, "model", model_part)
        return self

    def get_api_key_for_provider(self, provider: str | None = None) -> str | None:
        """
        Get API key for the specified or default provider.

        Args:
            provider: LLM provider name (defaults to configured provider)

        Returns:
            API key or None if not configured
        """
        provider = provider or self.llm_provider

        api_keys = {
            "anthropic": self.anthropic_api_key,
            "google-genai": self.google_api_key,
            "openai": self.openai_api_key,
        }
        return api_keys.get(provider)


@lru_cache
def get_settings() -> Settings:
    """
    Get cached application settings.

    Returns:
        Settings instance (cached for performance)

    Example:
        >>> settings = get_settings()
        >>> print(settings.llm_provider)
        'anthropic'
    """
    return Settings()


__all__ = ["Settings", "get_settings"]
