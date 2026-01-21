"""LLM provider factory and exceptions."""

from typing import Any

from langchain_core.language_models import BaseChatModel

from src.lib.config import get_settings
from src.lib.llm_callbacks import LLMMetricsCallback
from src.lib.logging import get_logger

logger = get_logger(__name__)


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, provider: str | None = None):
        self.message = message
        self.provider = provider
        super().__init__(message)


class LLMProviderError(LLMError):
    """Raised when LLM provider is not configured or API key is missing."""

    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""

    pass


class LLMRateLimitError(LLMError):
    """Raised when LLM provider rate limit is exceeded."""

    def __init__(self, message: str, provider: str | None = None, retry_after: int | None = None):
        super().__init__(message, provider)
        self.retry_after = retry_after


def get_llm(
    model: str | None = None,
    provider: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout: int | None = None,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Get an LLM instance for the specified or default provider.

    Args:
        model: Model name (defaults to settings.model)
        provider: LLM provider (defaults to settings.llm_provider)
        temperature: Model temperature (defaults to 0.0)
        max_tokens: Maximum tokens to generate
        timeout: Request timeout in seconds
        **kwargs: Additional provider-specific arguments

    Returns:
        LangChain chat model instance

    Raises:
        LLMProviderError: If provider not configured or API key missing

    Example:
        >>> llm = get_llm()
        >>> response = await llm.ainvoke([HumanMessage(content="Hello")])

        >>> llm = get_llm(provider="openai", model="gpt-4o")
        >>> response = await llm.ainvoke(messages)
    """
    settings = get_settings()

    # Use provided values or defaults from settings
    provider = provider or settings.llm_provider
    model = model or settings.model
    timeout = timeout or settings.llm_timeout
    temperature = temperature if temperature is not None else 0.0

    logger.debug(
        "get_llm_called",
        provider=provider,
        model=model,
        temperature=temperature,
        timeout=timeout,
    )

    # Get API key for provider
    api_key = settings.get_api_key_for_provider(provider)

    if not api_key:
        logger.error("llm_api_key_missing", provider=provider)
        raise LLMProviderError(
            f"API key not configured for provider '{provider}'. "
            f"Set the appropriate environment variable "
            f"(ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY).",
            provider=provider,
        )

    # Create LLM instance based on provider
    if provider == "anthropic":
        return _create_anthropic_llm(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
    elif provider == "google-genai":
        return _create_google_llm(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
    elif provider == "openai":
        return _create_openai_llm(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
    elif provider == "vllm":
        return _create_vllm_llm(
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs,
        )
    else:
        raise LLMProviderError(
            f"Unknown LLM provider: '{provider}'. "
            f"Supported providers: anthropic, google-genai, openai, vllm",
            provider=provider,
        )


def _add_metrics_callback(provider: str, model: str, kwargs: dict[str, Any]) -> list[Any]:
    """Create metrics callback and add to callbacks list."""
    callbacks = kwargs.pop("callbacks", [])
    callbacks.append(LLMMetricsCallback(provider=provider, model=model))
    return callbacks


def _create_anthropic_llm(
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
    timeout: int,
    **kwargs: Any,
) -> BaseChatModel:
    """Create Anthropic Claude LLM instance."""
    from langchain_anthropic import ChatAnthropic

    logger.debug("creating_anthropic_llm", model=model)
    callbacks = _add_metrics_callback("anthropic", model, kwargs)

    return ChatAnthropic(  # type: ignore[call-arg]
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens or 8192,
        timeout=float(timeout),
        callbacks=callbacks,
        **kwargs,
    )


def _create_google_llm(
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
    timeout: int,
    **kwargs: Any,
) -> BaseChatModel:
    """Create Google Gemini LLM instance."""
    from langchain_google_genai import ChatGoogleGenerativeAI

    # Map model names if needed
    if not model.startswith("gemini"):
        model = "gemini-2.0-flash"

    logger.debug("creating_google_llm", model=model)
    callbacks = _add_metrics_callback("google-genai", model, kwargs)

    return ChatGoogleGenerativeAI(
        google_api_key=api_key,
        model=model,
        temperature=temperature,
        max_output_tokens=max_tokens,
        timeout=timeout,
        callbacks=callbacks,
        **kwargs,
    )


def _create_openai_llm(
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
    timeout: int,
    **kwargs: Any,
) -> BaseChatModel:
    """Create OpenAI GPT LLM instance."""
    from langchain_openai import ChatOpenAI

    logger.debug("creating_openai_llm", model=model)
    callbacks = _add_metrics_callback("openai", model, kwargs)

    return ChatOpenAI(  # type: ignore[call-arg]
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=float(timeout),
        callbacks=callbacks,
        **kwargs,
    )


def _create_vllm_llm(
    api_key: str,
    model: str,
    temperature: float,
    max_tokens: int | None,
    timeout: int,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Create vLLM LLM instance using OpenAI-compatible API.

    vLLM exposes an OpenAI-compatible API, so we use ChatOpenAI
    with a custom base_url pointing to the vLLM server.

    Supports local models like Qwen3-Coder-30B-A3B-Instruct.
    """
    from langchain_openai import ChatOpenAI

    settings = get_settings()

    # Use vLLM-specific model if not overridden
    if model == settings.model and settings.llm_provider == "vllm":
        model = settings.vllm_model

    logger.debug(
        "creating_vllm_llm",
        model=model,
        api_base=settings.vllm_api_base,
    )
    callbacks = _add_metrics_callback("vllm", model, kwargs)

    # vLLM uses OpenAI-compatible API with custom base_url
    return ChatOpenAI(  # type: ignore[call-arg]
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=float(timeout),
        base_url=settings.vllm_api_base,
        callbacks=callbacks,
        # Qwen3-Coder specific: enable thinking mode for better reasoning
        # Can be disabled via extra_body if needed
        **kwargs,
    )


__all__ = [
    "get_llm",
    "LLMError",
    "LLMProviderError",
    "LLMTimeoutError",
    "LLMRateLimitError",
]
