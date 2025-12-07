"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
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
    app_name: str = Field(default="TestBoost", description="Application name")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database settings
    database_url: str = Field(
        default="postgresql+asyncpg://testboost:testboost@localhost:5433/testboost",
        description="PostgreSQL connection URL",
    )

    # LLM Provider settings
    llm_provider: Literal["anthropic", "google-genai", "openai"] = Field(
        default="anthropic",
        description="LLM provider to use",
    )
    model: str = Field(
        default="claude-sonnet-4-5-20250929",
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
        default=5,
        description="Startup check timeout in seconds",
    )

    # Retry settings
    max_retries: int = Field(
        default=3,
        description="Maximum retry attempts for transient errors",
    )

    # Data retention settings
    session_retention_days: int = Field(
        default=365,
        description="Number of days to retain session data",
    )

    # Locking settings
    project_lock_timeout_seconds: int = Field(
        default=300,
        description="Project lock timeout in seconds",
    )

    # API authentication
    api_key: str | None = Field(
        default=None,
        description="API key for authentication",
    )

    def get_api_key_for_provider(self, provider: str | None = None) -> str | None:
        """
        Get API key for the specified or default provider.

        Args:
            provider: LLM provider name (defaults to configured provider)

        Returns:
            API key or None if not configured
        """
        provider = provider or self.llm_provider

        if provider == "anthropic":
            return self.anthropic_api_key
        elif provider == "google-genai":
            return self.google_api_key
        elif provider == "openai":
            return self.openai_api_key

        return None


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
