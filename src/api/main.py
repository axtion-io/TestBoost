"""FastAPI application with CORS, middleware, and exception handlers."""

import json
import os
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from src.api.middleware.auth import api_key_auth_middleware
from src.api.middleware.error import ErrorHandlerMiddleware
from src.api.middleware.logging import request_logging_middleware
from src.api.routers import audit, health, logs, metrics, sessions
from src.lib.config import get_settings
from src.lib.logging import get_logger
from src.lib.startup_checks import StartupCheckError, run_all_startup_checks

logger = get_logger(__name__)
settings = get_settings()


def _initialize_langsmith_tracing() -> None:
    """
    Initialize LangSmith tracing if configured.

    Sets required environment variables for LangChain tracing integration.
    Implements 002-deepagents-integration tracing requirement.
    """
    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langsmith_project
        logger.info(
            "langsmith_tracing_enabled",
            project=settings.langsmith_project,
        )
    else:
        logger.debug("langsmith_tracing_disabled")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan events.

    Implements T008: Check LLM connectivity at startup before accepting commands.
    Constitutional principle: "Zéro Complaisance" - No workflows execute without LLM.
    """
    logger.info("application_startup", version=app.version)

    # Initialize LangSmith tracing before any LLM operations
    _initialize_langsmith_tracing()

    # Check if startup checks should be skipped (already done by CLI)
    skip_checks = os.environ.get("TESTBOOST_SKIP_API_STARTUP_CHECKS", "").lower() in ("1", "true", "yes")

    if skip_checks:
        logger.info("startup_checks_skipped", reason="TESTBOOST_SKIP_API_STARTUP_CHECKS set")
    else:
        try:
            # T008: Run all startup checks (currently LLM connectivity only)
            await run_all_startup_checks()
            logger.info("startup_checks_passed")
        except StartupCheckError as e:
            logger.error("startup_checks_failed", error=str(e))
            # Application MUST fail if startup checks fail (FR-010)
            raise RuntimeError(f"Application startup failed: {e}") from e

    yield

    # Graceful shutdown: dispose database engine to close all connections properly
    logger.info("application_shutdown_start")
    try:
        from src.db import engine
        await engine.dispose()
        logger.info("database_engine_disposed")
    except Exception as e:
        logger.error("database_engine_dispose_failed", error=str(e))

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

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


# Middleware order (CRITICAL):
# Both add_middleware and app.middleware("http") execute in REVERSE/LIFO order
# (last added = first executed in the request chain)
#
# Desired execution order:
# 1. RequestIDMiddleware - adds request_id FIRST
# 2. ErrorHandlerMiddleware - can use request_id for error logs
# 3. api_key_auth_middleware - auth with request_id
# 4. request_logging_middleware - logs requests with valid request_id
#
# So we add them in REVERSE order:

app.middleware("http")(request_logging_middleware)  # Executes LAST (4th)
app.middleware("http")(api_key_auth_middleware)      # Executes 3rd

app.add_middleware(ErrorHandlerMiddleware)           # Executes 2nd
app.add_middleware(RequestIDMiddleware)              # Executes FIRST (1st)

# Include routers
app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(metrics.router)
app.include_router(audit.router)
app.include_router(logs.router, prefix="/api/v2")


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


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """
    Handle Pydantic validation errors with structured logging.

    Logs validation failures to help identify:
    - Which fields are failing validation
    - What values were provided
    - API usage patterns and common mistakes
    """
    request_id = getattr(request.state, "request_id", "unknown")

    # Extract validation errors
    errors = exc.errors()

    # Log with context
    logger.warning(
        "validation_error",
        request_id=request_id,
        path=request.url.path,
        method=request.method,
        error_count=len(errors),
        errors=[
            {
                "field": " -> ".join(str(loc) for loc in error["loc"]),
                "message": error["msg"],
                "type": error["type"],
            }
            for error in errors
        ],
    )

    return JSONResponse(
        status_code=422,
        content={
            "detail": errors,
            "request_id": request_id,
        },
    )


def export_openapi_schema(output_path: str | None = None) -> dict[str, Any]:
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


def generate_openapi_schema() -> dict[str, Any]:
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
