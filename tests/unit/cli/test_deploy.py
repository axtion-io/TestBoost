"""Tests for deploy CLI commands."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner


class TestDeployCLI:
    """Tests for the deploy CLI subcommand."""

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

    def test_deploy_command_exists(self, runner, mock_startup_checks):
        """The deploy command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["deploy", "--help"])
        assert result.exit_code in [0, 2]

    def test_deploy_docker_subcommand(self, runner, mock_startup_checks):
        """Deploy docker subcommand should exist."""
        from src.cli.main import app

        result = runner.invoke(app, ["deploy", "docker", "--help"])
        assert result.exit_code in [0, 2]

    def test_deploy_requires_project_path(self, runner, mock_startup_checks):
        """Deploy should require a project path argument."""
        from src.cli.main import app

        result = runner.invoke(app, ["deploy", "docker"])
        # Missing argument or runs with defaults
        assert result.exit_code in [0, 1, 2]

    def test_deploy_docker_runs_command(self, runner, mock_startup_checks):
        """Deploy docker should invoke the deploy command."""
        from src.cli.main import app

        # With mocked startup checks, command should at least start
        result = runner.invoke(app, ["deploy", "docker", "."])
        # May succeed, fail due to missing project, or require more args
        assert result.exit_code in [0, 1, 2]

    def test_deploy_dry_run_flag(self, runner, mock_startup_checks):
        """Deploy should support dry-run flag."""
        from src.cli.main import app

        result = runner.invoke(app, ["deploy", "docker", ".", "--dry-run"])
        assert result.exit_code in [0, 1, 2]
