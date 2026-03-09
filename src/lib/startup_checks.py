"""Startup validation checks for TestBoost Lite."""

import asyncio
from typing import Any

from langchain_core.messages import HumanMessage

from src.lib.config import get_settings
from src.lib.llm import LLMError, LLMProviderError, LLMTimeoutError, get_llm
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Startup check timeout — configurable via STARTUP_TIMEOUT in .env (default 5s)
STARTUP_TIMEOUT = settings.startup_timeout

# Retry configuration for intermittent errors
MAX_RETRIES = 3
MIN_WAIT = 1  # seconds
MAX_WAIT = 10  # seconds


class StartupCheckError(Exception):
    """Base exception for startup check failures."""
    pass


class LLMConnectionError(StartupCheckError):
    """Raised when LLM connection check fails."""
    pass


def _is_retryable_error(exception: Exception) -> bool:
    """Determine if an error is retryable."""
    if isinstance(exception, TimeoutError | asyncio.TimeoutError | LLMTimeoutError):
        return True
    if isinstance(exception, ConnectionError):
        return True
    error_msg = str(exception).lower()
    if any(keyword in error_msg for keyword in ["401", "403", "unauthorized", "forbidden", "invalid api key"]):
        return False
    if "429" in error_msg or "rate limit" in error_msg:
        return False
    return "not configured" not in error_msg and "missing" not in error_msg


async def _ping_llm_with_retry(llm: Any, timeout: int = STARTUP_TIMEOUT, max_retries: int = MAX_RETRIES) -> None:
    """Ping LLM with retry logic for intermittent connectivity."""
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            messages = [HumanMessage(content="ping")]
            response = await asyncio.wait_for(
                llm.ainvoke(messages),
                timeout=timeout
            )
            if response is None:
                raise LLMConnectionError("LLM returned None response")
            logger.debug("llm_ping_success", response_length=len(str(response)), attempt=attempt)
            return

        except TimeoutError as e:
            logger.warning("llm_ping_timeout", timeout=timeout, attempt=attempt, max_retries=max_retries)
            last_error = LLMTimeoutError(f"LLM ping timed out after {timeout}s")
            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), MAX_WAIT)
                logger.info("llm_ping_retry", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise last_error from e

        except ConnectionError as e:
            logger.warning("llm_ping_connection_error", error=str(e), attempt=attempt, max_retries=max_retries)
            last_error = e
            if attempt < max_retries:
                wait_time = min(2 ** (attempt - 1), MAX_WAIT)
                logger.info("llm_ping_retry", attempt=attempt, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                continue
            raise LLMConnectionError(f"LLM ping failed after {max_retries} attempts: {e}") from e

        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "rate limit" in error_msg.lower():
                import re
                retry_after = "unknown"
                match = re.search(r"retry after (\d+)", error_msg, re.IGNORECASE)
                if match:
                    retry_after = f"{match.group(1)} seconds"
                logger.error("llm_rate_limited", retry_after=retry_after, error=error_msg)
                raise LLMConnectionError(
                    f"LLM rate limit exceeded. Retry after {retry_after}. Error: {error_msg}"
                ) from e
            if "401" in error_msg or "403" in error_msg or "unauthorized" in error_msg.lower():
                logger.error("llm_auth_failed", error=error_msg)
                raise LLMConnectionError(f"LLM authentication failed: {error_msg}") from e
            logger.error("llm_ping_failed", error=str(e), error_type=type(e).__name__)
            raise LLMConnectionError(f"LLM ping failed: {e}") from e


async def check_llm_connection(model: str | None = None) -> None:
    """
    Check LLM provider connectivity at startup.

    Called by testboost_lite/lib/cli.py before LLM-dependent commands.

    Raises:
        LLMProviderError: If API key not configured
        LLMConnectionError: If connection fails after retries
        LLMTimeoutError: If ping times out
    """
    try:
        logger.info("llm_connection_check_start", model=model or settings.model)
        llm = get_llm(model=model, timeout=STARTUP_TIMEOUT)
        await _ping_llm_with_retry(llm, timeout=STARTUP_TIMEOUT)
        logger.info("llm_connection_ok", model=model or settings.model)

    except LLMProviderError as e:
        logger.error("llm_connection_failed", reason="missing_api_key", error=str(e))
        raise

    except LLMConnectionError as e:
        logger.error("llm_connection_failed", reason="connection_error", error=str(e))
        raise LLMError(f"LLM not available: {e}") from e

    except LLMTimeoutError as e:
        logger.error("llm_connection_failed", reason="timeout", error=str(e))
        raise

    except Exception as e:
        logger.error("llm_connection_failed", reason="unexpected", error=str(e), error_type=type(e).__name__)
        raise LLMError(f"LLM connection check failed: {e}") from e


__all__ = [
    "check_llm_connection",
    "StartupCheckError",
    "LLMConnectionError",
]
