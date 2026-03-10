"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.

    Environment variables take precedence over .env file values.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application settings
    app_name: str = Field(description="Application name")
    debug: bool = Field(description="Debug mode")
    log_level: str = Field(description="Logging level")



    # LLM Provider settings
    llm_provider: Literal["anthropic", "google-genai", "openai"] = Field(
        description="LLM provider to use",
    )
    model: str = Field(
        description="Default LLM model",
    )

    # API Keys (loaded from environment only for security)
    anthropic_api_key: str | None = Field(
        description="Anthropic API key",
    )
    google_api_key: str | None = Field(
        description="Google API key for Gemini",
    )
    openai_api_key: str | None = Field(
        description="OpenAI API key",
    )
    openai_api_base: str | None = Field(
        description="OpenAI-compatible API base URL (for vLLM, Ollama, etc.)",
    )

    # LangSmith tracing (optional)
    langsmith_api_key: str | None = Field(
        description="LangSmith API key for tracing",
    )
    langsmith_tracing: bool = Field(
        description="Enable LangSmith tracing",
    )
    langsmith_project: str = Field(
        description="LangSmith project name",
    )

    # Timeout settings
    llm_timeout: int = Field(
        description="LLM request timeout in seconds",
    )
    startup_timeout: int = Field(
        description="Startup check timeout in seconds",
    )

    # Retry settings
    max_retries: int = Field(
        description="Maximum retry attempts for transient errors",
    )

    # Data retention settings
    session_retention_days: int = Field(
        description="Number of days to retain session data",
    )

    # Locking settings
    project_lock_timeout_seconds: int = Field(
        description="Project lock timeout in seconds",
    )

    # API authentication
    api_key: str | None = Field(
        description="API key for authentication",
    )

    @model_validator(mode="after")
    def parse_model_provider(self) -> "Settings":
        """
        Parse provider from model string if format is 'provider/model-name'.

        Examples:
            MODEL=google-genai/gemini-2.0-flash -> llm_provider=google-genai, model=gemini-2.0-flash
            MODEL=anthropic/claude-sonnet-4-5 -> llm_provider=anthropic, model=claude-sonnet-4-5
        """
        if "/" in self.model:
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
