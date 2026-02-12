"""Log classification taxonomy for TestBoost.

This module defines the semantic categories and severity levels used for
intelligent log classification and filtering.
"""

from enum import StrEnum


class LogCategory(StrEnum):
    """Semantic categories for log classification.

    Categories represent the domain or purpose of the log event:
    - BUSINESS: Core application logic (sessions, workflows, artifacts)
    - ACCESS: HTTP request/response activity
    - SYSTEM: Infrastructure and runtime (startup, DB connections, health)
    - DEBUG: Technical debugging information
    - AUDIT: Security-relevant user actions
    """

    BUSINESS = "business"
    ACCESS = "access"
    SYSTEM = "system"
    DEBUG = "debug"
    AUDIT = "audit"


class LogSeverity(StrEnum):
    """Log severity levels (log4j-style).

    Levels indicate the importance/urgency of the log event:
    - CRITICAL: System-breaking errors requiring immediate attention
    - ERROR: Application errors that prevent operations from completing
    - WARN: Potential issues or degraded functionality
    - INFO: Normal operational messages
    - DEBUG: Detailed information for debugging
    - TRACE: Very detailed trace information (disabled in production)
    """

    CRITICAL = "critical"
    ERROR = "error"
    WARN = "warn"
    INFO = "info"
    DEBUG = "debug"
    TRACE = "trace"


# Paths to exclude from access logs (monitoring endpoints)
EXCLUDED_PATHS = {
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
    "/api/v2/logs",  # Don't log the logs API itself
    "/api/v2/logs/stats",  # Don't log the logs stats endpoint
}


# Event name patterns for automatic categorization
EVENT_CATEGORY_MAPPING = {
    # Business events
    LogCategory.BUSINESS: [
        "session_",
        "workflow_",
        "step_",
        "artifact_",
        "llm_",
        "tests_",
        "analysis_",
    ],
    # Access events
    LogCategory.ACCESS: [
        "http_request",
        "http_response",
        "api_",
    ],
    # System events
    LogCategory.SYSTEM: [
        "startup",
        "shutdown",
        "database_",
        "migration_",
        "health_",
        "metrics_",
    ],
    # Debug events
    LogCategory.DEBUG: [
        "debug_",
        "trace_",
    ],
    # Audit events
    LogCategory.AUDIT: [
        "user_",
        "auth_",
        "permission_",
    ],
}


def categorize_event(event_name: str) -> LogCategory | None:
    """Automatically categorize an event based on its name.

    Args:
        event_name: The event name to categorize

    Returns:
        The matching category, or None if no match
    """
    if not event_name:
        return None

    event_lower = event_name.lower()

    for category, patterns in EVENT_CATEGORY_MAPPING.items():
        for pattern in patterns:
            if event_lower.startswith(pattern):
                return category

    return None


def map_log_level_to_severity(level: str) -> LogSeverity:
    """Map Python logging level names to our severity enum.

    Args:
        level: Python logging level name (e.g., "ERROR", "INFO")

    Returns:
        Corresponding LogSeverity value
    """
    level_mapping = {
        "CRITICAL": LogSeverity.CRITICAL,
        "ERROR": LogSeverity.ERROR,
        "WARNING": LogSeverity.WARN,
        "WARN": LogSeverity.WARN,
        "INFO": LogSeverity.INFO,
        "DEBUG": LogSeverity.DEBUG,
        "NOTSET": LogSeverity.TRACE,
    }

    return level_mapping.get(level.upper(), LogSeverity.INFO)
