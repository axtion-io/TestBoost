"""LangChain callbacks for LLM metrics tracking."""

import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from src.api.routers.metrics import record_llm_call, record_llm_duration, record_llm_rate_limit
from src.lib.logging import get_logger

logger = get_logger(__name__)


class LLMMetricsCallback(BaseCallbackHandler):
    """Callback handler to track LLM metrics in Prometheus.

    Captures:
    - LLM call count (success/failure)
    - LLM request duration
    - Rate limit errors
    """

    def __init__(self, provider: str, model: str):
        """Initialize callback with provider and model info.

        Args:
            provider: LLM provider name (anthropic, google-genai, openai)
            model: Model name
        """
        self.provider = provider
        self.model = model
        self.start_time: float | None = None

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        """Called when LLM starts running."""
        self.start_time = time.time()
        logger.debug(
            "llm_call_start",
            provider=self.provider,
            model=self.model,
            prompt_count=len(prompts),
        )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        """Called when LLM ends running successfully."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            record_llm_duration(self.provider, duration)

        record_llm_call(self.provider, self.model, success=True)

        logger.debug(
            "llm_call_success",
            provider=self.provider,
            model=self.model,
            duration_seconds=duration if self.start_time else None,
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        """Called when LLM errors out."""
        if self.start_time is not None:
            duration = time.time() - self.start_time
            record_llm_duration(self.provider, duration)

        # Check if it's a rate limit error
        error_msg = str(error).lower()
        if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
            record_llm_rate_limit(self.provider)
            logger.warning(
                "llm_rate_limit",
                provider=self.provider,
                model=self.model,
                error=str(error)[:200],
            )
        else:
            record_llm_call(self.provider, self.model, success=False)
            logger.error(
                "llm_call_error",
                provider=self.provider,
                model=self.model,
                error=str(error)[:200],
            )


__all__ = ["LLMMetricsCallback"]
