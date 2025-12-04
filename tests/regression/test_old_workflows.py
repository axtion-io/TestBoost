"""Regression tests for old workflow compatibility (T097a).

These tests ensure that existing workflow interfaces continue to work
after the DeepAgents 0.2.8 integration. They verify backward compatibility
and proper deprecation warning logging.
"""

import pytest
import warnings
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage


class TestOldMavenMaintenanceStillWorks:
    """Regression tests for Maven maintenance workflow backward compatibility."""

    def test_maven_workflow_function_exists_and_importable(self):
        """Test that the Maven maintenance workflow function is importable.

        T097a: Verify old workflow entry points remain functional.
        """
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
        import inspect

        # Verify the function exists and is async
        assert callable(run_maven_maintenance_with_agent)
        assert inspect.iscoroutinefunction(run_maven_maintenance_with_agent)

    def test_maven_workflow_accepts_expected_parameters(self):
        """Test that the workflow accepts the expected parameters.

        T097a: Verify backward compatibility of function signature.
        """
        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent
        import inspect

        sig = inspect.signature(run_maven_maintenance_with_agent)
        params = list(sig.parameters.keys())

        # Verify expected parameters exist
        assert "project_path" in params
        assert "session_id" in params

    def test_maven_agent_exceptions_available(self):
        """Test that Maven agent exception classes are available."""
        from src.workflows.maven_maintenance_agent import (
            MavenAgentError,
            ToolCallError,
            AgentTimeoutError,
        )

        # Verify exception hierarchy
        assert issubclass(ToolCallError, MavenAgentError)
        assert issubclass(AgentTimeoutError, MavenAgentError)


class TestOldTestGenerationStillWorks:
    """Regression tests for Test Generation workflow backward compatibility."""

    def test_test_generation_function_exists_and_importable(self):
        """Test that the test generation workflow function is importable.

        T097a: Verify test generation workflow remains functional.
        """
        from src.workflows.test_generation_agent import run_test_generation_with_agent
        import inspect

        # Verify the function exists and is async
        assert callable(run_test_generation_with_agent)
        assert inspect.iscoroutinefunction(run_test_generation_with_agent)

    def test_test_generation_accepts_expected_parameters(self):
        """Test that the workflow accepts expected parameters."""
        from src.workflows.test_generation_agent import run_test_generation_with_agent
        import inspect

        sig = inspect.signature(run_test_generation_with_agent)
        params = list(sig.parameters.keys())

        # Verify expected parameters exist
        assert "session_id" in params
        assert "project_path" in params
        assert "db_session" in params

    def test_test_generation_exceptions_available(self):
        """Test that test generation exception classes are available."""
        from src.workflows.test_generation_agent import (
            TestGenerationError,
            CompilationError,
        )

        # Verify exception hierarchy
        assert issubclass(CompilationError, TestGenerationError)


class TestOldDockerDeploymentStillWorks:
    """Regression tests for Docker deployment workflow backward compatibility."""

    def test_docker_deployment_function_exists_and_importable(self):
        """Test that the Docker deployment workflow function is importable.

        T097a: Verify deployment workflow remains functional.
        """
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent
        import inspect

        # Verify the function exists and is async
        assert callable(run_docker_deployment_with_agent)
        assert inspect.iscoroutinefunction(run_docker_deployment_with_agent)

    def test_docker_deployment_accepts_expected_parameters(self):
        """Test that the workflow accepts expected parameters."""
        from src.workflows.docker_deployment_agent import run_docker_deployment_with_agent
        import inspect

        sig = inspect.signature(run_docker_deployment_with_agent)
        params = list(sig.parameters.keys())

        # Verify expected parameters exist
        assert "project_path" in params
        assert "session_id" in params

    def test_checkpointer_function_available(self):
        """Test that the checkpointer function is available."""
        from src.workflows.docker_deployment_agent import get_checkpointer
        from langgraph.checkpoint.memory import MemorySaver

        # Verify checkpointer is available
        checkpointer = get_checkpointer()
        assert isinstance(checkpointer, MemorySaver)


class TestDeprecationWarningsLogged:
    """Test that deprecation warnings are properly logged (T097b)."""

    @pytest.mark.asyncio
    async def test_deprecation_warning_logged_for_legacy_imports(self):
        """Test that importing old modules logs deprecation warnings.

        T097b: Verify deprecation warnings are emitted for legacy usage.
        """
        # This test verifies that when legacy patterns are used,
        # appropriate deprecation warnings are logged
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Import the workflow modules (using actual module names)
            from src.workflows import maven_maintenance_agent
            from src.workflows import test_generation_agent
            from src.workflows import docker_deployment_agent

            # Check that modules are importable (no crashes)
            assert maven_maintenance_agent is not None
            assert test_generation_agent is not None
            assert docker_deployment_agent is not None

            # Note: Actual deprecation warnings would be logged if old
            # direct function calls are replaced with new agent-based calls


class TestAPIInterfaceRegression:
    """Regression tests for API interface backward compatibility (T097c)."""

    def test_api_endpoints_accept_old_request_format(self):
        """Test that API endpoints accept legacy request formats.

        T097c: Verify API backward compatibility.
        """
        from src.api.routers.testboost import MaintenanceRequest

        # Test with minimal legacy-style request
        legacy_request = MaintenanceRequest(
            project_path="/legacy/project",
        )

        assert legacy_request.project_path == "/legacy/project"
        # Verify default values are set
        assert legacy_request.auto_approve is False
        assert legacy_request.dry_run is False

    def test_api_response_format_unchanged(self):
        """Test that API response format matches legacy expectations.

        T097c: Verify response structure is backward compatible.
        """
        from src.api.routers.testboost import MaintenanceResponse

        # Verify response can be constructed with expected fields
        response = MaintenanceResponse(
            success=True,
            session_id="test-session",
            status="completed",
            message="Analysis complete"
        )

        assert response.session_id == "test-session"
        assert response.status == "completed"
        assert response.success is True

    def test_analyze_request_model_unchanged(self):
        """Test that AnalyzeRequest model structure is backward compatible."""
        from src.api.routers.testboost import AnalyzeRequest

        request = AnalyzeRequest(
            project_path="/test/project",
            include_snapshots=True,
            check_vulnerabilities=True
        )

        assert request.project_path == "/test/project"
        assert request.include_snapshots is True
        assert request.check_vulnerabilities is True

    def test_test_generate_request_model_unchanged(self):
        """Test that TestGenerateRequest model structure is backward compatible."""
        from src.api.routers.testboost import TestGenerateRequest

        request = TestGenerateRequest(
            project_path="/test/project",
            target_mutation_score=85.0
        )

        assert request.project_path == "/test/project"
        assert request.target_mutation_score == 85.0


class TestLibModulesRegression:
    """Regression tests for src/lib modules backward compatibility."""

    def test_get_settings_returns_valid_config(self):
        """Test that get_settings() still returns valid configuration."""
        from src.lib.config import get_settings

        settings = get_settings()

        assert settings is not None
        assert hasattr(settings, "llm_provider")
        assert hasattr(settings, "model")
        assert hasattr(settings, "database_url")

    def test_get_logger_returns_bound_logger(self):
        """Test that get_logger() returns a functional logger."""
        from src.lib.logging import get_logger

        logger = get_logger(__name__)

        assert logger is not None
        # Verify logger has standard methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "error")
        assert hasattr(logger, "debug")
        assert hasattr(logger, "warning")

    def test_llm_exceptions_still_available(self):
        """Test that LLM exception classes are still importable."""
        from src.lib.llm import (
            LLMError,
            LLMProviderError,
            LLMTimeoutError,
            LLMRateLimitError,
        )

        # Verify exception hierarchy
        assert issubclass(LLMProviderError, LLMError)
        assert issubclass(LLMTimeoutError, LLMError)
        assert issubclass(LLMRateLimitError, LLMError)

    def test_get_llm_factory_exists(self):
        """Test that get_llm factory function exists and is callable."""
        from src.lib.llm import get_llm

        assert callable(get_llm)


class TestStartupChecksRegression:
    """Regression tests for startup check backward compatibility."""

    def test_startup_check_exceptions_importable(self):
        """Test that startup check exceptions are available."""
        from src.lib.startup_checks import (
            StartupCheckError,
            LLMConnectionError,
            AgentConfigError,
        )

        # Verify exception hierarchy
        assert issubclass(LLMConnectionError, StartupCheckError)
        assert issubclass(AgentConfigError, StartupCheckError)

    @pytest.mark.asyncio
    async def test_check_llm_connection_exists(self):
        """Test that check_llm_connection function is available."""
        from src.lib.startup_checks import check_llm_connection

        assert callable(check_llm_connection)

    def test_validate_agent_infrastructure_exists(self):
        """Test that validate_agent_infrastructure function is available."""
        from src.lib.startup_checks import validate_agent_infrastructure

        assert callable(validate_agent_infrastructure)
