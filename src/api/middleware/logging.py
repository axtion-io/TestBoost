"""Request logging middleware."""

import time
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request
from starlette.responses import Response

from src.api.routers.metrics import record_request
from src.lib.logging import get_logger
from src.lib.log_taxonomy import EXCLUDED_PATHS

logger = get_logger(__name__)


def _is_polling_endpoint(request: Request) -> bool:
    """Check if request is a polling endpoint that should use DEBUG level logging."""
    return (
        request.method == "GET"
        and ("/api/v2/sessions" in request.url.path or "/events" in request.url.path)
    )


def _get_log_level(is_error: bool, is_polling: bool) -> Callable[..., Any]:
    """Determine appropriate log level based on response status and endpoint type."""
    if is_error:
        return logger.error
    if is_polling:
        return logger.debug
    return logger.info


async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log request details including method, path, duration, and status.

    Implements intelligent filtering:
    - Monitoring endpoints (/health, /metrics, /docs, etc.) are NOT logged on success
    - All endpoints ARE logged if response status >= 400 (errors)
    - All other endpoints are always logged
    """
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")

    is_monitoring_endpoint = request.url.path in EXCLUDED_PATHS
    is_polling = _is_polling_endpoint(request)

    # Log request start (unless it's a monitoring endpoint)
    if not is_monitoring_endpoint:
        log_level = logger.debug if is_polling else logger.info
        log_level(
            "request_started",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query=str(request.query_params) if request.query_params else None,
        )

    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Log completion: always log errors, skip successful monitoring endpoints
    is_error = response.status_code >= 400
    if (not is_monitoring_endpoint) or is_error:
        log_level = _get_log_level(is_error, is_polling)
        log_level(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=round(duration_ms, 2),
            excluded_path=is_monitoring_endpoint,
        )

    # Record Prometheus metrics (normalize path to avoid high cardinality)
    normalized_path = _normalize_path_for_metrics(request.url.path)
    record_request(
        method=request.method,
        path=normalized_path,
        status_code=response.status_code,
        duration_seconds=duration_ms / 1000,
    )

    return response


def _normalize_path_for_metrics(path: str) -> str:
    """
    Normalize path for Prometheus metrics to avoid high cardinality.

    Replaces UUIDs and IDs with placeholders.

    Args:
        path: Original request path

    Returns:
        Normalized path suitable for metrics labels
    """
    import re

    # Replace UUIDs with placeholder
    path = re.sub(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        "{id}",
        path,
        flags=re.IGNORECASE,
    )

    # Replace numeric IDs with placeholder
    path = re.sub(r"/\d+(?=/|$)", "/{id}", path)

    return path
