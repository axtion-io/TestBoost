"""Tests for error handling functionality."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi import Request, status


class TestErrorClasses:
    """Tests for error class hierarchy."""

    def test_testboost_error_has_message_and_code(self):
        """TestBoostError should have message and error_code."""
        from src.api.middleware.error import TestBoostError

        error = TestBoostError(message="Test error", error_code="TEST_ERROR")
        assert error.message == "Test error"
        assert error.error_code == "TEST_ERROR"
        assert error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    def test_testboost_error_default_error_code(self):
        """TestBoostError should default to INTERNAL_ERROR."""
        from src.api.middleware.error import TestBoostError

        error = TestBoostError(message="Test error")
        assert error.error_code == "INTERNAL_ERROR"

    def test_testboost_error_with_context(self):
        """TestBoostError should store context."""
        from src.api.middleware.error import TestBoostError

        error = TestBoostError(
            message="Test error",
            context={"key": "value"}
        )
        assert error.context == {"key": "value"}

    def test_validation_error_includes_field(self):
        """ValidationError should include field name in context."""
        from src.api.middleware.error import ValidationError

        error = ValidationError(message="Path does not exist", field="project_path")
        assert error.context.get("field") == "project_path"
        assert error.error_code == "VALIDATION_ERROR"
        assert error.status_code == status.HTTP_400_BAD_REQUEST

    def test_not_found_error(self):
        """NotFoundError should include resource info."""
        from src.api.middleware.error import NotFoundError

        error = NotFoundError(resource_type="Session", resource_id="123")
        assert "Session" in error.message
        assert "123" in error.message
        assert error.error_code == "NOT_FOUND"
        assert error.status_code == status.HTTP_404_NOT_FOUND

    def test_workflow_error_includes_step(self):
        """WorkflowError should include step information."""
        from src.api.middleware.error import WorkflowError

        error = WorkflowError(
            message="Failed to parse POM file",
            step_code="analyze_pom",
            session_id="session-123"
        )
        assert error.context.get("step_code") == "analyze_pom"
        assert error.context.get("session_id") == "session-123"
        assert error.error_code == "WORKFLOW_ERROR"

    def test_llm_error_includes_provider(self):
        """LLMError should include provider information."""
        from src.api.middleware.error import LLMError

        error = LLMError(message="API rate limit exceeded", provider="anthropic")
        assert error.context.get("provider") == "anthropic"
        assert error.error_code == "LLM_ERROR"
        assert error.status_code == status.HTTP_502_BAD_GATEWAY

    def test_timeout_error(self):
        """TimeoutError should include operation and timeout."""
        from src.api.middleware.error import TimeoutError

        error = TimeoutError(operation="maven_build", timeout_seconds=300)
        assert error.context.get("operation") == "maven_build"
        assert error.context.get("timeout_seconds") == 300
        assert "300" in error.message
        assert error.error_code == "TIMEOUT"

    def test_conflict_error(self):
        """ConflictError should have correct status code."""
        from src.api.middleware.error import ConflictError

        error = ConflictError(message="Resource already exists")
        assert error.error_code == "CONFLICT"
        assert error.status_code == status.HTTP_409_CONFLICT

    def test_project_locked_error(self):
        """ProjectLockedError should include lock info."""
        from src.api.middleware.error import ProjectLockedError

        error = ProjectLockedError(
            project_path="/test/project",
            locked_by_session="session-456"
        )
        assert error.context.get("project_path") == "/test/project"
        assert error.context.get("locked_by_session") == "session-456"
        assert error.error_code == "PROJECT_LOCKED"


class TestErrorInheritance:
    """Tests for error class inheritance."""

    def test_all_errors_inherit_from_testboost_error(self):
        """All custom errors should inherit from TestBoostError."""
        from src.api.middleware.error import (
            TestBoostError,
            ValidationError,
            NotFoundError,
            ConflictError,
            ProjectLockedError,
            LLMError,
            TimeoutError,
            WorkflowError,
        )

        assert issubclass(ValidationError, TestBoostError)
        assert issubclass(NotFoundError, TestBoostError)
        assert issubclass(ConflictError, TestBoostError)
        assert issubclass(ProjectLockedError, ConflictError)
        assert issubclass(LLMError, TestBoostError)
        assert issubclass(TimeoutError, TestBoostError)
        assert issubclass(WorkflowError, TestBoostError)

    def test_all_errors_inherit_from_exception(self):
        """All custom errors should ultimately inherit from Exception."""
        from src.api.middleware.error import TestBoostError

        assert issubclass(TestBoostError, Exception)


class TestErrorResponse:
    """Tests for error response creation."""

    def test_create_error_response_function_exists(self):
        """create_error_response function should exist."""
        from src.api.middleware.error import create_error_response

        assert callable(create_error_response)

    def test_error_handler_middleware_exists(self):
        """ErrorHandlerMiddleware should exist."""
        from src.api.middleware.error import ErrorHandlerMiddleware

        assert ErrorHandlerMiddleware is not None

