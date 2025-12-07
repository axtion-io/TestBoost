"""Request logging middleware."""

import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.responses import Response

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

    return response
