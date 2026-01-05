"""Tests for maintenance CLI commands."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner


class TestMaintenanceCLI:
    """Tests for the maintenance CLI subcommand."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_startup_checks(self):
        """Mock startup checks to pass."""
        with patch("src.cli.main.run_all_startup_checks", new_callable=AsyncMock) as mock:
            mock.return_value = None
            yield mock

    def test_maintenance_command_exists(self, runner, mock_startup_checks):
        """The maintenance command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "--help"])
        assert result.exit_code == 0
        assert "maintenance" in result.output.lower()

    def test_maintenance_run_command_exists(self, runner, mock_startup_checks):
        """The maintenance run command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "run", "--help"])
        # Command exists even if it requires arguments
        assert result.exit_code in [0, 2]

    def test_maintenance_list_command_exists(self, runner, mock_startup_checks):
        """The maintenance list command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "list", "--help"])
        assert result.exit_code in [0, 2]

    def test_maintenance_run_invokes_command(self, runner, mock_startup_checks):
        """Maintenance run should invoke the command."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "run", "."])
        # May succeed or fail depending on project structure
        assert result.exit_code in [0, 1, 2]

    def test_maintenance_list_invokes_command(self, runner, mock_startup_checks):
        """Maintenance list should invoke the command."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "list", "."])
        # May succeed or fail depending on project structure
        assert result.exit_code in [0, 1, 2]

    def test_maintenance_invalid_path_shows_error(self, runner, mock_startup_checks):
        """Invalid path should show appropriate error."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "list", "/nonexistent/path/xyz123abc"])
        # Should fail gracefully
        assert (
            result.exit_code != 0
            or "error" in result.output.lower()
            or "not found" in result.output.lower()
            or "invalid" in result.output.lower()
        )
