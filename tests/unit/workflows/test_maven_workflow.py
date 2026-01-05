"""Tests for Maven workflow operations."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock


class TestMavenWorkflowAgent:
    """Tests for Maven-related workflow agent operations."""

    def test_maven_agent_error_class_exists(self):
        """MavenAgentError should be importable."""
        from src.workflows.maven_maintenance_agent import MavenAgentError

        error = MavenAgentError("Test error")
        assert str(error) == "Test error"

    def test_tool_call_error_includes_expected_tools(self):
        """ToolCallError should include expected tools in message."""
        from src.workflows.maven_maintenance_agent import ToolCallError

        error = ToolCallError("Tools not called", expected_tools=["analyze_pom", "check_updates"])
        assert "analyze_pom" in str(error)
        assert "check_updates" in str(error)

    def test_agent_timeout_error_includes_timeout(self):
        """AgentTimeoutError should include timeout value."""
        from src.workflows.maven_maintenance_agent import AgentTimeoutError

        error = AgentTimeoutError("Timed out", timeout_seconds=30.0)
        assert "30" in str(error)
        assert error.timeout_seconds == 30.0

    @pytest.mark.asyncio
    async def test_invoke_agent_with_retry_import(self):
        """_invoke_agent_with_retry should be importable."""
        from src.workflows.maven_maintenance_agent import _invoke_agent_with_retry

        assert callable(_invoke_agent_with_retry)

    def test_workflow_state_transitions(self):
        """Workflow states should be valid SessionStatus values."""
        from src.db.models import SessionStatus

        # Valid states from the SessionStatus enum
        valid_states = [s.value for s in SessionStatus]

        # Check expected states exist
        expected = ["pending", "in_progress", "completed", "failed"]
        for state in expected:
            assert state in valid_states, f"State '{state}' not in SessionStatus"


class TestMavenWorkflowMCPTools:
    """Tests for Maven MCP tools integration."""

    def test_maven_tools_module_exists(self):
        """Maven MCP tools module should be importable."""
        from src.mcp_servers.maven_maintenance import tools

        assert tools is not None

    def test_analyze_tool_exists(self):
        """Analyze POM tool should exist."""
        from src.mcp_servers.maven_maintenance.tools import analyze

        assert analyze is not None

    def test_compile_tool_exists(self):
        """Compile tool should exist."""
        from src.mcp_servers.maven_maintenance.tools import compile

        assert compile is not None

    def test_run_tests_tool_exists(self):
        """Run tests tool should exist."""
        from src.mcp_servers.maven_maintenance.tools import run_tests

        assert run_tests is not None


class TestMavenWorkflowConfig:
    """Tests for Maven workflow configuration."""

    def test_settings_accessible(self):
        """Settings should be accessible."""
        from src.lib.config import get_settings

        settings = get_settings()
        assert settings is not None

    def test_llm_factory_exists(self):
        """LLM factory function should exist."""
        from src.lib.llm import get_llm

        assert callable(get_llm)

    def test_logger_available(self):
        """Logger should be available for workflow."""
        from src.lib.logging import get_logger

        logger = get_logger("test")
        assert logger is not None
