"""Health check endpoint."""

from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_db
from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    """
    Health check endpoint.

    Returns status, version, and database connectivity.
    Returns 503 if unhealthy.
    """
    health_status: dict[str, Any] = {
        "status": "healthy",
        "version": "0.1.0",
        "checks": {
            "database": "unknown",
        },
    }

    # Check database connectivity
    try:
        await db.execute(text("SELECT 1"))
        health_status["checks"]["database"] = "healthy"
    except Exception as e:
        logger.error("database_health_check_failed", error=str(e))
        health_status["checks"]["database"] = "unhealthy"
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=503,
            content=health_status,
        )

    return JSONResponse(
        status_code=200,
        content=health_status,
    )
