"""Request logging middleware."""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

from src.api.routers.metrics import record_request
from src.lib.logging import get_logger

logger = get_logger(__name__)


async def request_logging_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log request details including method, path, duration, and status."""
    start_time = time.time()
    request_id = getattr(request.state, "request_id", "unknown")

    # Log request start
    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        query=str(request.query_params) if request.query_params else None,
    )

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = (time.time() - start_time) * 1000

    # Log request completion
    logger.info(
        "request_completed",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration_ms, 2),
    )

    # Record Prometheus metrics for HTTP requests
    # Normalize path for metrics (avoid high cardinality from UUIDs)
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
