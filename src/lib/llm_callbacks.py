"""LangChain callbacks for LLM call logging."""

import time
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from src.lib.logging import get_logger

logger = get_logger(__name__)


class LLMMetricsCallback(BaseCallbackHandler):
    """Callback handler to log LLM call metrics."""

    def __init__(self, provider: str, model: str):
        self.provider = provider
        self.model = model
        self.start_time: float | None = None

    def on_llm_start(
        self, serialized: dict[str, Any], prompts: list[str], **kwargs: Any
    ) -> None:
        self.start_time = time.time()
        logger.debug(
            "llm_call_start",
            provider=self.provider,
            model=self.model,
            prompt_count=len(prompts),
        )

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        duration = time.time() - self.start_time if self.start_time else None
        logger.debug(
            "llm_call_success",
            provider=self.provider,
            model=self.model,
            duration_seconds=duration,
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        duration = time.time() - self.start_time if self.start_time else None
        error_msg = str(error).lower()
        if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
            logger.warning(
                "llm_rate_limit",
                provider=self.provider,
                model=self.model,
                error=str(error)[:200],
            )
        else:
            logger.error(
                "llm_call_error",
                provider=self.provider,
                model=self.model,
                duration_seconds=duration,
                error=str(error)[:200],
            )


__all__ = ["LLMMetricsCallback"]
