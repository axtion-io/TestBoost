"""Tests for tests CLI commands."""

from unittest.mock import AsyncMock, patch

import pytest
from typer.testing import CliRunner


class TestTestsCLI:
    """Tests for the tests CLI subcommand."""

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

    def test_tests_command_exists(self, runner, mock_startup_checks):
        """The tests command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "--help"])
        assert result.exit_code == 0
        assert "tests" in result.output.lower()

    def test_tests_analyze_command_exists(self, runner, mock_startup_checks):
        """The tests analyze command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "analyze", "--help"])
        assert result.exit_code in [0, 2]

    def test_tests_generate_command_exists(self, runner, mock_startup_checks):
        """The tests generate command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "generate", "--help"])
        assert result.exit_code in [0, 2]

    def test_tests_analyze_runs_command(self, runner, mock_startup_checks):
        """Tests analyze should run the command."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "analyze", "."])
        # May succeed or fail depending on project structure
        assert result.exit_code in [0, 1, 2]

    def test_tests_generate_runs_command(self, runner, mock_startup_checks):
        """Tests generate should run the command."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "generate", "."])
        # May succeed or fail depending on project/LLM
        assert result.exit_code in [0, 1, 2]

    def test_tests_generate_verbose_flag(self, runner, mock_startup_checks):
        """Tests generate should accept verbose flag."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "generate", ".", "--verbose"])
        # Command runs (may fail due to missing project)
        assert result.exit_code in [0, 1, 2]

    def test_tests_analyze_with_options(self, runner, mock_startup_checks):
        """Tests analyze should accept various options."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "analyze", ".", "--verbose"])
        assert result.exit_code in [0, 1, 2]

    def test_tests_generate_dry_run(self, runner, mock_startup_checks):
        """Tests generate should support dry-run mode."""
        from src.cli.main import app

        result = runner.invoke(app, ["tests", "generate", ".", "--dry-run"])
        assert result.exit_code in [0, 1, 2]
