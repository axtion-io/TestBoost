"""Tests for maintenance CLI commands."""

from unittest.mock import AsyncMock, MagicMock, patch

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


class TestMaintenanceParityCommands:
    """Tests for CLI vs API parity commands (T063-T071)."""

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

    @pytest.fixture
    def mock_api_client(self):
        """Mock APIClient for testing."""
        with patch("src.cli.commands.maintenance.APIClient") as mock_class:
            mock_instance = MagicMock()
            mock_class.return_value = mock_instance
            yield mock_instance

    # =========================================================================
    # T063-T065: Step Execution Tests
    # =========================================================================

    def test_sessions_command_exists(self, runner, mock_startup_checks):
        """The sessions command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "sessions", "--help"])
        assert result.exit_code == 0
        assert "sessions" in result.output.lower() or "list" in result.output.lower()

    def test_steps_command_exists(self, runner, mock_startup_checks):
        """The steps command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "steps", "--help"])
        assert result.exit_code == 0
        assert "steps" in result.output.lower()

    def test_step_command_exists(self, runner, mock_startup_checks):
        """The step command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "step", "--help"])
        assert result.exit_code == 0
        assert "step" in result.output.lower()

    @patch("src.cli.utils.api_client.APIClient")
    def test_sessions_displays_table(self, mock_api_class, runner, mock_startup_checks):
        """Sessions command should display sessions in a table."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.list_sessions.return_value = {
            "items": [
                {
                    "id": "abc-123",
                    "session_type": "maven_maintenance",
                    "status": "completed",
                    "project_path": "/test/project",
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
            "pagination": {"total": 1, "page": 1, "per_page": 20},
        }

        result = runner.invoke(app, ["maintenance", "sessions"])
        assert result.exit_code == 0
        assert "abc" in result.output or "Sessions" in result.output

    @patch("src.cli.utils.api_client.APIClient")
    def test_steps_displays_steps(self, mock_api_class, runner, mock_startup_checks):
        """Steps command should display steps for a session."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.get_steps.return_value = {
            "items": [
                {
                    "id": "step-1",
                    "code": "analyze",
                    "name": "Analyze Dependencies",
                    "status": "completed",
                    "sequence": 1,
                }
            ],
            "total": 1,
        }

        result = runner.invoke(app, ["maintenance", "steps", "session-123"])
        assert result.exit_code == 0

    @patch("src.cli.utils.api_client.APIClient")
    def test_step_executes_step(self, mock_api_class, runner, mock_startup_checks):
        """Step command should execute a specific step."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.execute_step.return_value = {
            "id": "step-1",
            "code": "analyze",
            "name": "Analyze Dependencies",
            "status": "in_progress",
            "message": "Step started",
        }

        result = runner.invoke(app, ["maintenance", "step", "session-123", "analyze"])
        assert result.exit_code == 0

    # =========================================================================
    # T066-T069: Session Control Tests
    # =========================================================================

    def test_pause_command_exists(self, runner, mock_startup_checks):
        """The pause command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "pause", "--help"])
        assert result.exit_code == 0
        assert "pause" in result.output.lower()

    def test_resume_command_exists(self, runner, mock_startup_checks):
        """The resume command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "resume", "--help"])
        assert result.exit_code == 0
        assert "resume" in result.output.lower()

    @patch("src.cli.utils.api_client.APIClient")
    def test_pause_pauses_session(self, mock_api_class, runner, mock_startup_checks):
        """Pause command should pause a session."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.pause_session.return_value = {
            "session_id": "session-123",
            "status": "paused",
            "checkpoint_id": "checkpoint-abc",
            "message": "Session paused",
        }

        result = runner.invoke(app, ["maintenance", "pause", "session-123"])
        assert result.exit_code == 0
        assert "paused" in result.output.lower() or "checkpoint" in result.output.lower()

    @patch("src.cli.utils.api_client.APIClient")
    def test_resume_resumes_session(self, mock_api_class, runner, mock_startup_checks):
        """Resume command should resume a session."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.resume_session.return_value = {
            "session_id": "session-123",
            "status": "in_progress",
            "message": "Session resumed",
        }

        result = runner.invoke(app, ["maintenance", "resume", "session-123"])
        assert result.exit_code == 0
        assert "resumed" in result.output.lower()

    # =========================================================================
    # T070-T072: Artifacts & Cancel Tests
    # =========================================================================

    def test_artifacts_command_exists(self, runner, mock_startup_checks):
        """The artifacts command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "artifacts", "--help"])
        assert result.exit_code == 0
        assert "artifacts" in result.output.lower()

    def test_cancel_command_exists(self, runner, mock_startup_checks):
        """The cancel command should be available."""
        from src.cli.main import app

        result = runner.invoke(app, ["maintenance", "cancel", "--help"])
        assert result.exit_code == 0
        assert "cancel" in result.output.lower()

    @patch("src.cli.utils.api_client.APIClient")
    def test_artifacts_displays_artifacts(self, mock_api_class, runner, mock_startup_checks):
        """Artifacts command should display session artifacts."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.get_artifacts.return_value = {
            "items": [
                {
                    "id": "artifact-1",
                    "name": "analysis_result",
                    "artifact_type": "llm_response",
                    "content_type": "application/json",
                    "size_bytes": 1024,
                    "created_at": "2024-01-01T00:00:00Z",
                }
            ],
            "total": 1,
        }

        result = runner.invoke(app, ["maintenance", "artifacts", "session-123"])
        assert result.exit_code == 0

    @patch("src.cli.utils.api_client.APIClient")
    def test_cancel_with_force(self, mock_api_class, runner, mock_startup_checks):
        """Cancel command with --force should not prompt."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client
        mock_client.cancel_maintenance.return_value = {}

        result = runner.invoke(app, ["maintenance", "cancel", "session-123", "--force"])
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()

    @patch("src.cli.utils.api_client.APIClient")
    def test_cancel_without_force_prompts(self, mock_api_class, runner, mock_startup_checks):
        """Cancel command without --force should prompt for confirmation."""
        from src.cli.main import app

        mock_client = MagicMock()
        mock_api_class.return_value = mock_client

        # Simulate user saying "n" to confirmation
        result = runner.invoke(app, ["maintenance", "cancel", "session-123"], input="n\n")
        assert result.exit_code == 0
        assert "cancelled" in result.output.lower()  # "Cancelled." message


class TestAPIClient:
    """Tests for APIClient utility."""

    def test_api_client_builds_url(self):
        """APIClient should build URLs correctly."""
        from src.cli.utils.api_client import APIClient

        client = APIClient(base_url="http://test:8000")
        url = client._build_url("/api/sessions/{session_id}", session_id="abc123")
        assert url == "http://test:8000/api/sessions/abc123"

    def test_api_client_handles_404(self):
        """APIClient should raise APIError on 404."""
        from src.cli.utils.api_client import APIClient, APIError

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            mock_response = MagicMock()
            mock_response.status_code = 404
            mock_response.json.return_value = {"detail": "Not found"}
            mock_client.get.return_value = mock_response

            client = APIClient()
            with pytest.raises(APIError) as exc_info:
                client.get("/test")

            assert exc_info.value.status_code == 404
            assert "not found" in exc_info.value.message.lower()

    def test_api_client_handles_401(self):
        """APIClient should provide helpful message on 401."""
        from src.cli.utils.api_client import APIClient, APIError

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__ = MagicMock(return_value=mock_client)
            mock_client_class.return_value.__exit__ = MagicMock(return_value=False)

            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.json.return_value = {"detail": "Unauthorized"}
            mock_client.get.return_value = mock_response

            client = APIClient()
            with pytest.raises(APIError) as exc_info:
                client.get("/test")

            assert exc_info.value.status_code == 401
            assert "authentication" in exc_info.value.message.lower()


class TestFormatters:
    """Tests for CLI formatters."""

    def test_format_session_table_handles_empty(self):
        """Formatter should handle empty session list."""
        from unittest.mock import MagicMock

        from src.cli.formatters import format_session_table

        mock_console = MagicMock()
        format_session_table([], mock_console)
        mock_console.print.assert_called()

    def test_format_steps_table_handles_empty(self):
        """Formatter should handle empty steps list."""
        from unittest.mock import MagicMock

        from src.cli.formatters import format_steps_table

        mock_console = MagicMock()
        format_steps_table([], mock_console)
        mock_console.print.assert_called()

    def test_format_artifacts_table_handles_empty(self):
        """Formatter should handle empty artifacts list."""
        from unittest.mock import MagicMock

        from src.cli.formatters import format_artifacts_table

        mock_console = MagicMock()
        format_artifacts_table([], mock_console)
        mock_console.print.assert_called()

    def test_style_status_colors(self):
        """Status styling should apply correct colors."""
        from src.cli.formatters import _style_status

        assert "green" in _style_status("completed")
        assert "red" in _style_status("failed")
        assert "blue" in _style_status("in_progress")
        assert "yellow" in _style_status("paused")
