"""Structured logging configuration using structlog."""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, Processor, WrappedLogger

from src.lib.log_taxonomy import (
    categorize_event,
    map_log_level_to_severity,
)

# Configure once flag
_configured = False

# Log directory
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


def add_log_categorization(
    logger: WrappedLogger, method_name: str, event_dict: EventDict
) -> EventDict:
    """Structlog processor that adds category and severity classification.

    This processor enriches log events with:
    - category: Semantic category based on event name (business, access, system, etc.)
    - severity: Log4j-style severity level (critical, error, warn, info, debug, trace)

    Args:
        logger: The wrapped logger instance
        method_name: The name of the method called (e.g., "info", "error")
        event_dict: The event dictionary being logged

    Returns:
        Enriched event dictionary with category and severity fields
    """
    # Add severity based on log level
    log_level = event_dict.get("level", "info")
    if isinstance(log_level, str):
        severity = map_log_level_to_severity(log_level)
        event_dict["severity"] = severity.value

    # Add category based on event name
    event_name = event_dict.get("event")
    if event_name:
        category = categorize_event(event_name)
        if category:
            event_dict["category"] = category.value

    return event_dict


def _configure_structlog() -> None:
    """Configure structlog for the application."""
    global _configured
    if _configured:
        return

    # Create logs directory if it doesn't exist
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Get log level from environment
    log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Configure root logger with handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    root_logger.addHandler(console_handler)

    # Add filter to suppress SQLAlchemy connection termination errors with closed event loops
    # These occur when cleaning up stale connections from previous server instances
    class SupressSQLAlchemyEventLoopErrors(logging.Filter):
        """Filter out harmless SQLAlchemy connection cleanup errors."""

        def filter(self, record: logging.LogRecord) -> bool:
            # Suppress "Exception terminating/closing connection" with "Event loop is closed"
            if "Exception terminating connection" in record.getMessage():
                return False
            if "Exception closing connection" in record.getMessage():
                return False
            return not (
                "RuntimeWarning: coroutine" in record.getMessage()
                and "_cancel" in record.getMessage()
            )

    sqlalchemy_filter = SupressSQLAlchemyEventLoopErrors()

    # File handler with rotation (JSON format for log analysis)
    log_file = LOG_DIR / f"testboost_{datetime.now().strftime('%Y%m%d')}.log"
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setLevel(log_level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))
    file_handler.addFilter(sqlalchemy_filter)
    root_logger.addHandler(file_handler)

    # Also add filter to console handler
    console_handler.addFilter(sqlalchemy_filter)

    # Determine if we're in development or production
    # In development, use colored console output
    # In production, use JSON output
    is_development = sys.stderr.isatty()

    # Common processors for all environments
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        add_log_categorization,  # Add category and severity classification
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_development:
        # Development: colored console output
        processors: list[Processor] = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        processors = [
            *shared_processors,
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    _configured = True


def get_logger(name: str | None = None, **initial_context: Any) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)
        **initial_context: Initial context values to bind to the logger

    Returns:
        Bound structlog logger

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("workflow_started", session_id="abc123")

        >>> logger = get_logger(__name__, service="maven")
        >>> logger.info("dependency_analyzed", count=5)
    """
    _configure_structlog()

    logger: structlog.stdlib.BoundLogger = structlog.get_logger(name)

    if initial_context:
        logger = logger.bind(**initial_context)

    return logger


def bind_context(**context: Any) -> None:
    """
    Bind context variables that will be included in all log messages.

    Useful for request-scoped context like request_id, session_id, etc.

    Args:
        **context: Key-value pairs to bind to the context

    Example:
        >>> bind_context(request_id="req-123", user_id="user-456")
        >>> logger.info("processing")  # Will include request_id and user_id
    """
    structlog.contextvars.bind_contextvars(**context)


def clear_context() -> None:
    """
    Clear all bound context variables.

    Call this at the end of a request or workflow to clean up context.
    """
    structlog.contextvars.clear_contextvars()


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    This function ensures structlog is properly configured.
    Safe to call multiple times (idempotent).

    Example:
        >>> configure_logging()  # Called at startup
    """
    _configure_structlog()


__all__ = ["get_logger", "bind_context", "clear_context", "configure_logging"]
