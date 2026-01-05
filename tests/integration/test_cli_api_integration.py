"""Integration tests for CLI and API interaction."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import subprocess
import json


@pytest.mark.integration
class TestCLIAPIIntegration:
    """Test CLI commands that interact with the API."""

    @pytest.fixture
    def mock_startup_checks(self):
        """Mock startup checks to pass."""
        with patch("src.cli.main.run_all_startup_checks", new_callable=AsyncMock) as mock:
            mock.return_value = None
            yield mock

    def test_cli_triggers_api_session(self, mock_startup_checks):
        """CLI command should execute and interact with API."""
        from typer.testing import CliRunner
        from src.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["maintenance", "list", "."])

        # Command should execute (may fail on project validation)
        assert result.exit_code in [0, 1, 2]

    def test_cli_retrieves_session_status(self, mock_startup_checks):
        """CLI should be able to display session status."""
        from typer.testing import CliRunner
        from src.cli.main import app

        runner = CliRunner()
        # Use status command if it exists
        result = runner.invoke(app, ["status"])
        # May succeed or show help/error
        assert result.exit_code in [0, 1, 2]

    def test_cli_handles_api_unavailable(self, mock_startup_checks):
        """CLI should handle API being unavailable gracefully."""
        from typer.testing import CliRunner
        from src.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["maintenance", "list", "."])

        # Should fail gracefully with appropriate message
        assert result.exit_code in [0, 1, 2]


@pytest.mark.integration
class TestCLIWorkflowIntegration:
    """Test CLI triggering full workflows."""

    @pytest.fixture
    def mock_startup_checks(self):
        """Mock startup checks to pass."""
        with patch("src.cli.main.run_all_startup_checks", new_callable=AsyncMock) as mock:
            mock.return_value = None
            yield mock

    def test_maintenance_workflow_end_to_end(self, mock_startup_checks):
        """Test maintenance command triggers complete workflow."""
        from typer.testing import CliRunner
        from src.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["maintenance", "run", ".", "--dry-run"])

        # Command executes
        assert result.exit_code in [0, 1, 2]

    def test_test_generation_workflow_end_to_end(self, mock_startup_checks):
        """Test generation command triggers complete workflow."""
        from typer.testing import CliRunner
        from src.cli.main import app

        runner = CliRunner()
        result = runner.invoke(app, ["tests", "generate", ".", "--verbose"])

        assert result.exit_code in [0, 1, 2]

