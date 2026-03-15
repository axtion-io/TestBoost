"""LangChain callbacks for LLM call logging."""

import time
import traceback
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

        # Extract token usage from LLM output when available
        token_usage: dict[str, Any] = {}
        if response.llm_output:
            token_usage = response.llm_output.get("token_usage", {}) or {}

        logger.debug(
            "llm_call_success",
            provider=self.provider,
            model=self.model,
            duration_seconds=round(duration, 2) if duration else None,
            prompt_tokens=token_usage.get("prompt_tokens"),
            completion_tokens=token_usage.get("completion_tokens"),
            total_tokens=token_usage.get("total_tokens"),
        )

    def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
        duration = time.time() - self.start_time if self.start_time else None
        error_msg = str(error).lower()
        cause = error.__cause__
        cause_chain = []
        e = error.__cause__
        while e is not None:
            cause_chain.append(f"{type(e).__name__}: {e}")
            e = e.__cause__
        if "rate" in error_msg or "quota" in error_msg or "429" in error_msg:
            logger.warning(
                "llm_rate_limit",
                provider=self.provider,
                model=self.model,
                error=str(error),
                cause_chain=cause_chain,
            )
        else:
            logger.error(
                "llm_call_error",
                provider=self.provider,
                model=self.model,
                duration_seconds=duration,
                error=str(error),
                error_type=type(error).__name__,
                cause=str(cause) if cause else None,
                cause_type=type(cause).__name__ if cause else None,
                cause_chain=cause_chain,
                traceback="".join(traceback.format_exception(error)),
            )


__all__ = ["LLMMetricsCallback"]
