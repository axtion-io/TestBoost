"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from src.lib.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["health"])


def _build_unhealthy_response(health_status: dict[str, Any]) -> JSONResponse:
    """Build a 503 unhealthy response with the given status."""
    health_status["checks"]["database"] = "unhealthy"
    health_status["status"] = "unhealthy"
    return JSONResponse(status_code=503, content=health_status)


async def _check_database_health(health_status: dict[str, Any]) -> bool:
    """
    Check database connectivity, handling stale connections.

    Returns True if healthy, False otherwise.
    """
    from src.db import get_async_engine

    engine = get_async_engine()

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except AttributeError as e:
        # Stale connection from pool with closed event loop (after server restart)
        if "'NoneType' object has no attribute 'send'" not in str(e):
            logger.error("database_health_check_failed", error=str(e))
            return False

        # Dispose pool and retry once
        try:
            await engine.dispose()
            engine = get_async_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception as retry_error:
            logger.error("database_health_check_failed_after_retry", error=str(retry_error))
            return False
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        return False


@router.get("/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint.

    Returns status, version, and database connectivity.
    Returns 503 if unhealthy.

    Note: Uses a direct connection pool checkout (not a session) to avoid
    transaction conflicts during concurrent health checks.
    """
    health_status: dict[str, Any] = {
        "status": "healthy",
        "version": "0.1.0",
        "checks": {
            "database": "unknown",
        },
    }

    if await _check_database_health(health_status):
        health_status["checks"]["database"] = "healthy"
        return JSONResponse(status_code=200, content=health_status)

    return _build_unhealthy_response(health_status)
