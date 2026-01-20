"""API key authentication middleware."""

import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Paths that bypass authentication
BYPASS_PATHS = {
    "/health",
    "/metrics",
    "/metrics/json",
    "/docs",
    "/redoc",
    "/openapi.json",
}


async def api_key_auth_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Verify API key for protected endpoints."""
    # Check if path should bypass authentication
    if request.url.path in BYPASS_PATHS or request.url.path.startswith("/docs"):
        return await call_next(request)

    # Get API key from header
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        logger.warning(
            "missing_api_key",
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "Missing API key"},
        )

    if settings.api_key is None or not secrets.compare_digest(api_key, settings.api_key):
        logger.warning(
            "invalid_api_key",
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid API key"},
        )

    return await call_next(request)
