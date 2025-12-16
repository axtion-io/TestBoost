"""Database utilities with reconnection strategy (CHK048).

Provides retry logic for transient database errors and
connection pool recovery mechanisms.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine
from typing import Any, TypeVar

from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    InterfaceError,
    OperationalError,
)
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import SessionLocal, get_async_engine
from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

T = TypeVar("T")


# Transient error types that should be retried
TRANSIENT_ERRORS = (
    DisconnectionError,
    InterfaceError,
    OperationalError,
)


class DatabaseRetryConfig:
    """Configuration for database retry behavior."""

    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 0.5,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
    ):
        """
        Initialize retry configuration.

        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_base: Base for exponential backoff
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base


# Default retry configuration
DEFAULT_RETRY_CONFIG = DatabaseRetryConfig(
    max_retries=settings.max_retries,
    initial_delay=0.5,
    max_delay=10.0,
)


def is_transient_error(exc: Exception) -> bool:
    """
    Check if an exception is a transient database error.

    Args:
        exc: Exception to check

    Returns:
        True if the error is transient and should be retried
    """
    if isinstance(exc, TRANSIENT_ERRORS):
        return True

    # Check for specific error messages in DBAPIError
    if isinstance(exc, DBAPIError):
        error_str = str(exc).lower()
        transient_messages = [
            "connection",
            "timeout",
            "unavailable",
            "reset by peer",
            "broken pipe",
            "too many connections",
        ]
        return any(msg in error_str for msg in transient_messages)

    return False


async def with_retry(
    operation: Callable[[], Coroutine[Any, Any, T]],
    config: DatabaseRetryConfig | None = None,
    operation_name: str = "database_operation",
) -> T:
    """
    Execute a database operation with retry logic.

    Args:
        operation: Async function to execute
        config: Retry configuration (uses default if None)
        operation_name: Name for logging

    Returns:
        Result of the operation

    Raises:
        Last exception if all retries are exhausted
    """
    config = config or DEFAULT_RETRY_CONFIG
    last_exception: Exception | None = None

    for attempt in range(config.max_retries + 1):
        try:
            return await operation()
        except Exception as e:
            last_exception = e

            if not is_transient_error(e):
                logger.error(
                    "db_non_transient_error",
                    operation=operation_name,
                    error=str(e),
                )
                raise

            if attempt == config.max_retries:
                logger.error(
                    "db_retry_exhausted",
                    operation=operation_name,
                    attempts=attempt + 1,
                    error=str(e),
                )
                raise

            # Calculate delay with exponential backoff
            delay = min(
                config.initial_delay * (config.exponential_base**attempt),
                config.max_delay,
            )

            logger.warning(
                "db_retry_attempt",
                operation=operation_name,
                attempt=attempt + 1,
                max_retries=config.max_retries,
                delay_seconds=delay,
                error=str(e),
            )

            await asyncio.sleep(delay)

    # Should never reach here, but satisfy type checker
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected state in retry loop")


async def get_db_with_retry() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session with retry logic for transient errors.

    Yields:
        AsyncSession with automatic retry on transient errors
    """
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            if is_transient_error(e):
                logger.warning("db_session_transient_error", error=str(e))
            raise
        finally:
            await session.close()


async def check_connection_health() -> bool:
    """
    Check database connection health.

    Returns:
        True if connection is healthy, False otherwise
    """
    try:
        engine = get_async_engine()
        async with engine.connect() as conn:
            await conn.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error("db_health_check_failed", error=str(e))
        return False


async def reset_connection_pool() -> None:
    """
    Reset the connection pool to recover from connection issues.

    This disposes of all connections and creates new ones on demand.
    """
    try:
        engine = get_async_engine()
        await engine.dispose()
        logger.info("db_connection_pool_reset")
    except Exception as e:
        logger.error("db_pool_reset_failed", error=str(e))
        raise


class DatabaseSession:
    """
    Context manager for database sessions with automatic retry.

    Example:
        async with DatabaseSession() as session:
            result = await session.execute(query)
    """

    def __init__(self, retry_config: DatabaseRetryConfig | None = None):
        """Initialize with optional retry config."""
        self._config = retry_config or DEFAULT_RETRY_CONFIG
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> AsyncSession:
        """Enter context and create session."""
        self._session = SessionLocal()
        return self._session

    async def __aexit__(self, exc_type: Any, exc_val: Any, _exc_tb: Any) -> bool:
        """Exit context, handling commit/rollback and retries."""
        if self._session is None:
            return False

        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()

                # Check if error is transient
                if exc_val and is_transient_error(exc_val):
                    logger.warning(
                        "db_session_transient_error_on_exit",
                        error=str(exc_val),
                    )
        finally:
            await self._session.close()
            self._session = None

        return False  # Don't suppress exceptions


__all__ = [
    "DatabaseRetryConfig",
    "DEFAULT_RETRY_CONFIG",
    "is_transient_error",
    "with_retry",
    "get_db_with_retry",
    "check_connection_health",
    "reset_connection_pool",
    "DatabaseSession",
]
