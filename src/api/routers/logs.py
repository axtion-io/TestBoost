"""API endpoints for querying application logs."""

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from src.lib.log_taxonomy import LogCategory, LogSeverity
from src.lib.logging import LOG_DIR, get_logger

router = APIRouter(prefix="/logs", tags=["Logs"])
logger = get_logger(__name__)


class LogEntry(BaseModel):
    """A single log entry with classification."""

    timestamp: datetime = Field(..., description="When the log event occurred")
    level: str = Field(..., description="Python log level (ERROR, INFO, etc.)")
    event: str = Field(..., description="Event name")
    category: str | None = Field(None, description="Semantic category (business, access, etc.)")
    severity: str | None = Field(None, description="log4j-style severity (error, info, etc.)")
    logger_name: str | None = Field(None, description="Python logger name")
    session_id: str | None = Field(None, description="Session UUID if applicable")
    request_id: str | None = Field(None, description="HTTP request UUID")
    message: str | None = Field(None, description="Human-readable message")
    extra: dict[str, Any] = Field(default_factory=dict, description="All other fields")


class LogsResponse(BaseModel):
    """Paginated response for log queries."""

    logs: list[LogEntry] = Field(..., description="List of matching log entries")
    total: int = Field(..., description="Total number of matching logs")
    page: int = Field(..., description="Current page number")
    per_page: int = Field(..., description="Items per page")
    filters_applied: dict[str, Any] = Field(..., description="Summary of filters applied")


class LogStatsResponse(BaseModel):
    """Statistics about logs for a given date."""

    date: str = Field(..., description="Date in YYYYMMDD format")
    total_lines: int = Field(..., description="Total number of log lines")
    by_level: dict[str, int] = Field(..., description="Count by log level")
    by_category: dict[str, int] = Field(..., description="Count by category")
    top_events: list[dict[str, Any]] = Field(..., description="Top 10 most frequent events")
    recent_errors: list[dict[str, Any]] = Field(..., description="Last 10 error events")


def _get_log_file_path(date: str | None) -> Path:
    """Get the path to the log file for a given date.

    Args:
        date: Date in YYYYMMDD format, or None for today

    Returns:
        Path to the log file

    Raises:
        HTTPException: If date format is invalid or file doesn't exist
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    else:
        # Validate date format
        if not re.match(r"^\d{8}$", date):
            raise HTTPException(status_code=400, detail="Date must be in YYYYMMDD format")

        # Validate date is parseable
        try:
            datetime.strptime(date, "%Y%m%d")
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid date: {date}")

    log_file = LOG_DIR / f"testboost_{date}.log"

    if not log_file.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Log file for date {date} not found. Available dates can be found by listing {LOG_DIR}",
        )

    return log_file


def _parse_log_line(line: str) -> dict[str, Any] | None:
    """Parse a JSON log line into a dictionary.

    Args:
        line: Raw log line (should be JSON)

    Returns:
        Parsed log dictionary, or None if parsing fails
    """
    try:
        return json.loads(line.strip())
    except (json.JSONDecodeError, AttributeError):
        # Skip non-JSON lines (shouldn't happen with structlog, but defensive)
        return None


def _matches_filters(
    log_entry: dict[str, Any],
    level: str | None,
    category: str | None,
    session_id: str | None,
    event_pattern: str | None,
    since: datetime | None,
    until: datetime | None,
) -> bool:
    """Check if a log entry matches all specified filters.

    Args:
        log_entry: Parsed log entry dictionary
        level: Filter by severity level
        category: Filter by category
        session_id: Filter by session UUID
        event_pattern: Regex pattern for event name
        since: Minimum timestamp
        until: Maximum timestamp

    Returns:
        True if the log entry matches all filters
    """
    # Level filter (check both 'level' and 'severity')
    if level:
        entry_level = log_entry.get("severity") or log_entry.get("level", "").lower()
        if entry_level.lower() != level.lower():
            return False

    # Category filter
    if category:
        entry_category = log_entry.get("category")
        if not entry_category or entry_category.lower() != category.lower():
            return False

    # Session ID filter
    if session_id:
        entry_session_id = log_entry.get("session_id")
        if not entry_session_id or session_id not in str(entry_session_id):
            return False

    # Event pattern filter (regex)
    if event_pattern:
        event_name = log_entry.get("event", "")
        try:
            if not re.search(event_pattern, event_name, re.IGNORECASE):
                return False
        except re.error:
            # Invalid regex pattern - skip this filter
            pass

    # Timestamp filters
    timestamp_str = log_entry.get("timestamp")
    if timestamp_str and (since or until):
        try:
            # Parse ISO 8601 timestamp
            log_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

            if since and log_timestamp < since:
                return False

            if until and log_timestamp > until:
                return False
        except (ValueError, AttributeError):
            # Invalid timestamp format - can't filter by time
            pass

    return True


def _convert_to_log_entry(log_dict: dict[str, Any]) -> LogEntry:
    """Convert a parsed log dictionary to a LogEntry model.

    Args:
        log_dict: Parsed log dictionary

    Returns:
        LogEntry model instance
    """
    # Extract known fields
    timestamp_str = log_dict.get("timestamp", "")
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        timestamp = datetime.now(timezone.utc)

    level = log_dict.get("level", "info")
    event = log_dict.get("event", "unknown")
    category = log_dict.get("category")
    severity = log_dict.get("severity")
    logger_name = log_dict.get("logger")
    session_id = log_dict.get("session_id")
    request_id = log_dict.get("request_id")
    message = log_dict.get("message")

    # Extract all other fields as "extra"
    known_fields = {
        "timestamp",
        "level",
        "event",
        "category",
        "severity",
        "logger",
        "session_id",
        "request_id",
        "message",
    }
    extra = {k: v for k, v in log_dict.items() if k not in known_fields}

    return LogEntry(
        timestamp=timestamp,
        level=level,
        event=event,
        category=category,
        severity=severity,
        logger_name=logger_name,
        session_id=session_id,
        request_id=request_id,
        message=message,
        extra=extra,
    )


@router.get("", response_model=LogsResponse)
async def get_logs(
    request: Request,
    level: str | None = Query(
        None, description="Filter by severity level (critical, error, warn, info, debug, trace)"
    ),
    category: str | None = Query(
        None, description="Filter by category (business, access, system, debug, audit)"
    ),
    session_id: str | None = Query(None, description="Filter by session UUID"),
    event: str | None = Query(None, description="Filter by event name (regex pattern)"),
    since: datetime | None = Query(None, description="Filter logs after this timestamp (ISO 8601)"),
    until: datetime | None = Query(None, description="Filter logs before this timestamp (ISO 8601)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(100, ge=1, le=1000, description="Items per page"),
    date: str | None = Query(None, description="Log file date (YYYYMMDD, defaults to today)"),
) -> LogsResponse:
    """Query application logs with filtering and pagination.

    Reads the log file for the specified date and returns matching entries.

    **Filtering**:
    - All filters are optional and can be combined
    - `event` parameter accepts regex patterns (e.g., "workflow_.*", "session_(created|completed)")
    - `since`/`until` accept ISO 8601 timestamps with timezone

    **Performance**:
    - Reads entire log file into memory (acceptable for daily log rotation)
    - Filters in Python (future: consider indexing for large files)

    **Examples**:
    - All errors: `?level=error`
    - Session events: `?category=business&event=session_.*`
    - Errors since 2pm: `?level=error&since=2026-01-13T14:00:00Z`
    """
    # Get log file path
    log_file = _get_log_file_path(date)

    # Read and parse log file
    matching_logs: list[LogEntry] = []

    with log_file.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            log_dict = _parse_log_line(line)
            if not log_dict:
                continue

            # Apply filters
            if _matches_filters(log_dict, level, category, session_id, event, since, until):
                matching_logs.append(_convert_to_log_entry(log_dict))

    # Sort by timestamp descending (newest first)
    matching_logs.sort(key=lambda x: x.timestamp, reverse=True)

    # Paginate
    total = len(matching_logs)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_logs = matching_logs[start_idx:end_idx]

    return LogsResponse(
        logs=page_logs,
        total=total,
        page=page,
        per_page=per_page,
        filters_applied={
            "level": level,
            "category": category,
            "session_id": session_id,
            "event": event,
            "since": since.isoformat() if since else None,
            "until": until.isoformat() if until else None,
            "date": date or datetime.now().strftime("%Y%m%d"),
        },
    )


@router.get("/stats", response_model=LogStatsResponse)
async def get_log_stats(
    request: Request,
    date: str | None = Query(None, description="Log file date (YYYYMMDD, defaults to today)"),
) -> LogStatsResponse:
    """Get aggregated statistics about logs for a given date.

    Returns:
    - Total number of log lines
    - Count by severity level
    - Count by category
    - Top 10 most frequent events
    - Last 10 error events

    **Performance**: Scans entire log file, suitable for daily logs up to ~100MB.
    """
    # Get log file path
    log_file = _get_log_file_path(date)
    date_str = date or datetime.now().strftime("%Y%m%d")

    # Initialize counters
    total_lines = 0
    by_level: dict[str, int] = {}
    by_category: dict[str, int] = {}
    event_counts: dict[str, int] = {}
    recent_errors: list[dict[str, Any]] = []

    # Read and analyze log file
    with log_file.open("r", encoding="utf-8") as f:
        for line in f:
            total_lines += 1
            log_dict = _parse_log_line(line)
            if not log_dict:
                continue

            # Count by level
            level = log_dict.get("severity") or log_dict.get("level", "unknown")
            by_level[level] = by_level.get(level, 0) + 1

            # Count by category (handle None by converting to "uncategorized")
            category = log_dict.get("category") or "uncategorized"
            by_category[category] = by_category.get(category, 0) + 1

            # Count events
            event = log_dict.get("event", "unknown")
            event_counts[event] = event_counts.get(event, 0) + 1

            # Collect errors
            if level.lower() in ("error", "critical"):
                recent_errors.append(
                    {
                        "timestamp": log_dict.get("timestamp"),
                        "event": event,
                        "session_id": log_dict.get("session_id"),
                        "message": log_dict.get("message"),
                        "error": log_dict.get("error"),
                    }
                )

    # Sort and limit top events
    top_events = [
        {"event": event, "count": count}
        for event, count in sorted(event_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    ]

    # Keep only last 10 errors
    recent_errors = recent_errors[-10:]

    return LogStatsResponse(
        date=date_str,
        total_lines=total_lines,
        by_level=by_level,
        by_category=by_category,
        top_events=top_events,
        recent_errors=recent_errors,
    )
