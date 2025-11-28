"""FastAPI application with CORS, middleware, and exception handlers."""

import json
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.api.middleware.auth import api_key_auth_middleware
from src.api.middleware.error import ErrorHandlerMiddleware
from src.api.middleware.logging import request_logging_middleware
from src.api.routers import health, sessions
from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    logger.info("application_startup", version=app.version)
    yield
    logger.info("application_shutdown")


app = FastAPI(
    title="TestBoost API",
    description="AI-powered Java test generation and maintenance platform",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
class RequestIDMiddleware(BaseHTTPMiddleware):
    """Add request ID to each request."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


app.add_middleware(RequestIDMiddleware)

# Error handler middleware (catches all exceptions)
app.add_middleware(ErrorHandlerMiddleware)

# Custom middleware
app.middleware("http")(request_logging_middleware)
app.middleware("http")(api_key_auth_middleware)

# Include routers
app.include_router(health.router)
app.include_router(sessions.router)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler for unhandled errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(
        "unhandled_exception",
        request_id=request_id,
        error=str(exc),
        path=request.url.path,
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "request_id": request_id,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Handle ValueError exceptions."""
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


def export_openapi_schema(output_path: str | None = None) -> dict:
    """
    Export the OpenAPI schema to a file.

    Args:
        output_path: Path to write the schema file. If None, uses default path.

    Returns:
        OpenAPI schema dictionary
    """
    schema = app.openapi()

    if output_path:
        output_file = Path(output_path)
    else:
        # Default to specs directory
        output_file = (
            Path(__file__).parent.parent.parent.parent
            / "specs"
            / "001-testboost-core"
            / "contracts"
            / "openapi.json"
        )

    # Ensure directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Write schema
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2)

    logger.info(
        "openapi_schema_exported",
        output_path=str(output_file),
        paths_count=len(schema.get("paths", {})),
    )

    return schema


def generate_openapi_schema() -> dict:
    """
    Generate the OpenAPI schema without writing to file.

    Returns:
        OpenAPI schema dictionary
    """
    return app.openapi()


__all__ = [
    "app",
    "export_openapi_schema",
    "generate_openapi_schema",
]
