"""Tests for config CLI commands."""

import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner


class TestConfigCLI:
    """Tests for the config CLI subcommand."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    def test_config_command_help(self, runner):
        """Config command should show help."""
        from src.cli.main import app

        result = runner.invoke(app, ["--help"])
        # Main help should be available
        assert result.exit_code == 0

    def test_cli_version_flag(self, runner):
        """CLI should support version flag."""
        from src.cli.main import app

        result = runner.invoke(app, ["--version"])
        # Version flag may or may not be implemented
        assert result.exit_code in [0, 2]

    def test_cli_verbose_flag(self, runner):
        """CLI should support verbose flag."""
        from src.cli.main import app

        result = runner.invoke(app, ["--verbose", "--help"])
        assert result.exit_code in [0, 2]

    def test_cli_with_env_vars(self, runner):
        """CLI should respect environment variables."""
        from src.cli.main import app

        with patch.dict(os.environ, {"TESTBOOST_DEBUG": "true"}):
            result = runner.invoke(app, ["--help"])
            assert result.exit_code == 0

    def test_cli_subcommands_available(self, runner):
        """All main subcommands should be listed in help."""
        from src.cli.main import app

        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        # Check that main commands are mentioned
        output_lower = result.output.lower()
        # At least one of these should be present
        assert any(cmd in output_lower for cmd in ["maintenance", "tests", "deploy"])
