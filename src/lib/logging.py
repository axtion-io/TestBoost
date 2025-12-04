"""Logging configuration using structlog."""

from typing import Any

import structlog
from structlog.types import EventDict, Processor


def mask_sensitive_data(
    logger: structlog.types.WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Mask sensitive data in log messages."""
    sensitive_keys = {
        "password",
        "api_key",
        "secret",
        "token",
        "authorization",
        "credential",
    }

    for key in list(event_dict.keys()):
        if any(s in key.lower() for s in sensitive_keys):
            event_dict[key] = "***MASKED***"

    return event_dict


def configure_logging(log_level: str = "INFO", environment: str = "development") -> None:
    """Configure structlog for the application."""
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        mask_sensitive_data,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if environment == "production":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback,
            )
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(structlog, log_level.upper(), structlog.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a configured logger instance."""
    return structlog.get_logger(name)


__all__ = ["configure_logging", "get_logger", "mask_sensitive_data"]
