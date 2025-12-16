"""Structured logging configuration using structlog."""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from structlog.types import Processor

# Configure once flag
_configured = False

# Log directory
LOG_DIR = Path(__file__).parent.parent.parent / "logs"


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
    root_logger.addHandler(file_handler)

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
