"""Global exception handler middleware with contextual error messages (FR-032)."""

import traceback
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from src.lib.logging import get_logger

logger = get_logger(__name__)


class TestBoostError(Exception):
    """Base exception for TestBoost errors with context."""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        context: dict[str, Any] | None = None,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
    ):
        """
        Initialize TestBoost error.

        Args:
            message: Human-readable error message
            error_code: Machine-readable error code
            context: Additional context for debugging
            status_code: HTTP status code
        """
        super().__init__(message)
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.context = context or {}
        self.status_code = status_code


class ValidationError(TestBoostError):
    """Validation error with field context."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        ctx = context or {}
        if field:
            ctx["field"] = field
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            context=ctx,
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class NotFoundError(TestBoostError):
    """Resource not found error."""

    def __init__(
        self,
        resource_type: str,
        resource_id: str,
        context: dict[str, Any] | None = None,
    ):
        ctx = context or {}
        ctx["resource_type"] = resource_type
        ctx["resource_id"] = resource_id
        super().__init__(
            message=f"{resource_type} not found: {resource_id}",
            error_code="NOT_FOUND",
            context=ctx,
            status_code=status.HTTP_404_NOT_FOUND,
        )


class ConflictError(TestBoostError):
    """Resource conflict error (e.g., project locked)."""

    def __init__(
        self,
        message: str,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            context=context,
            status_code=status.HTTP_409_CONFLICT,
        )


class ProjectLockedError(ConflictError):
    """Project is locked by another session."""

    def __init__(
        self,
        project_path: str,
        locked_by_session: str,
    ):
        super().__init__(
            message=f"Project is locked by session {locked_by_session}",
            context={
                "project_path": project_path,
                "locked_by_session": locked_by_session,
            },
        )
        self.error_code = "PROJECT_LOCKED"


class LLMError(TestBoostError):
    """LLM provider error."""

    def __init__(
        self,
        message: str,
        provider: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        ctx = context or {}
        if provider:
            ctx["provider"] = provider
        super().__init__(
            message=message,
            error_code="LLM_ERROR",
            context=ctx,
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class TimeoutError(TestBoostError):
    """Operation timeout error."""

    def __init__(
        self,
        operation: str,
        timeout_seconds: int,
        context: dict[str, Any] | None = None,
    ):
        ctx = context or {}
        ctx["operation"] = operation
        ctx["timeout_seconds"] = timeout_seconds
        super().__init__(
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            error_code="TIMEOUT",
            context=ctx,
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
        )


class WorkflowError(TestBoostError):
    """Workflow execution error."""

    def __init__(
        self,
        message: str,
        step_code: str | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        ctx = context or {}
        if step_code:
            ctx["step_code"] = step_code
        if session_id:
            ctx["session_id"] = session_id
        super().__init__(
            message=message,
            error_code="WORKFLOW_ERROR",
            context=ctx,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def create_error_response(
    request: Request,
    error: TestBoostError,
) -> JSONResponse:
    """
    Create a standardized error response with context (FR-032).

    Args:
        request: FastAPI request
        error: TestBoost error

    Returns:
        JSON response with error details
    """
    request_id = getattr(request.state, "request_id", "unknown")

    response_body = {
        "error": {
            "code": error.error_code,
            "message": error.message,
            "context": error.context,
        },
        "request_id": request_id,
        "path": request.url.path,
    }

    return JSONResponse(
        status_code=error.status_code,
        content=response_body,
    )


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Middleware to catch and format all exceptions with context.

    Ensures consistent error response format across the API per FR-032.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process request and handle any exceptions.

        Args:
            request: FastAPI request
            call_next: Next middleware in chain

        Returns:
            Response or error response
        """
        try:
            response = await call_next(request)
            return response
        except TestBoostError as e:
            # Log structured error
            logger.error(
                "testboost_error",
                error_code=e.error_code,
                message=e.message,
                context=e.context,
                path=request.url.path,
                request_id=getattr(request.state, "request_id", "unknown"),
            )
            return create_error_response(request, e)
        except Exception as e:
            # Wrap unexpected errors
            request_id = getattr(request.state, "request_id", "unknown")

            logger.error(
                "unhandled_error",
                error=str(e),
                error_type=type(e).__name__,
                path=request.url.path,
                request_id=request_id,
                traceback=traceback.format_exc(),
            )

            # Create generic error response
            generic_error = TestBoostError(
                message="An unexpected error occurred",
                error_code="INTERNAL_ERROR",
                context={
                    "error_type": type(e).__name__,
                },
            )
            return create_error_response(request, generic_error)


__all__ = [
    "TestBoostError",
    "ValidationError",
    "NotFoundError",
    "ConflictError",
    "ProjectLockedError",
    "LLMError",
    "TimeoutError",
    "WorkflowError",
    "ErrorHandlerMiddleware",
    "create_error_response",
]
