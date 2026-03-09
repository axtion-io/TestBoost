# SPDX-License-Identifier: Apache-2.0
"""Unit tests for testboost_lite.lib.session_tracker."""

import re

from testboost_lite.lib.session_tracker import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_IN_PROGRESS,
    STEPS,
    _make_frontmatter,
    _parse_frontmatter,
    create_session,
    get_current_session,
    get_session_status,
    get_sessions_dir,
    get_testboost_dir,
    init_project,
    update_step_file,
    write_log,
)

# ============================================================================
# init_project
# ============================================================================


class TestInitProject:
    def test_creates_testboost_dir(self, tmp_path):
        result = init_project(str(tmp_path))
        assert result["success"] is True
        assert (tmp_path / ".testboost").is_dir()

    def test_creates_sessions_dir(self, tmp_path):
        init_project(str(tmp_path))
        assert (tmp_path / ".testboost" / "sessions").is_dir()

    def test_creates_config_yaml(self, tmp_path):
        init_project(str(tmp_path))
        config = tmp_path / ".testboost" / "config.yaml"
        assert config.exists()
        content = config.read_text()
        assert "coverage_target: 80" in content
        assert "mock_framework: mockito" in content

    def test_creates_gitignore(self, tmp_path):
        init_project(str(tmp_path))
        gi = tmp_path / ".testboost" / ".gitignore"
        assert gi.exists()
        assert "logs" in gi.read_text()

    def test_idempotent(self, tmp_path):
        """Calling init twice should not fail or overwrite config."""
        init_project(str(tmp_path))
        config = tmp_path / ".testboost" / "config.yaml"
        config.write_text("custom: true\n")

        init_project(str(tmp_path))
        assert config.read_text() == "custom: true\n"

    def test_returns_message(self, tmp_path):
        result = init_project(str(tmp_path))
        assert "Initialized" in result["message"]
        assert str(tmp_path) in result["message"]


# ============================================================================
# create_session
# ============================================================================


class TestCreateSession:
    def test_creates_session_dir(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        assert result["success"] is True
        assert "001-test-generation" in result["session_id"]

    def test_creates_spec_md(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        assert spec.exists()
        content = spec.read_text()
        assert "status: in_progress" in content
        assert "## Progress" in content

    def test_creates_logs_dir(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        logs = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs")
        assert logs.is_dir()

    def test_custom_name(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path), name="My Custom Session")
        assert result["session_id"] == "001-my-custom-session"

    def test_custom_description(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path), description="Test the auth module")
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        assert "Test the auth module" in spec.read_text()

    def test_sequential_numbering(self, tmp_path):
        init_project(str(tmp_path))
        r1 = create_session(str(tmp_path), name="first")
        r2 = create_session(str(tmp_path), name="second")
        assert r1["session_id"].startswith("001-")
        assert r2["session_id"].startswith("002-")

    def test_progress_table_has_all_steps(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        content = spec.read_text()
        for step in STEPS:
            assert f"| {step} | pending |" in content

    def test_sanitizes_name(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path), name="Hello World! @#$")
        assert "hello-world" in result["session_id"]
        # No special characters
        assert re.match(r"^\d{3}-[a-z0-9-]+$", result["session_id"])


# ============================================================================
# get_current_session
# ============================================================================


class TestGetCurrentSession:
    def test_returns_none_when_no_sessions(self, tmp_path):
        init_project(str(tmp_path))
        assert get_current_session(str(tmp_path)) is None

    def test_returns_none_when_no_testboost_dir(self, tmp_path):
        assert get_current_session(str(tmp_path)) is None

    def test_returns_latest_session(self, tmp_path):
        init_project(str(tmp_path))
        create_session(str(tmp_path), name="first")
        create_session(str(tmp_path), name="second")
        session = get_current_session(str(tmp_path))
        assert session is not None
        assert session["session_id"] == "002-second"

    def test_returns_session_fields(self, tmp_path):
        init_project(str(tmp_path))
        create_session(str(tmp_path))
        session = get_current_session(str(tmp_path))
        assert "session_id" in session
        assert "session_dir" in session
        assert "status" in session
        assert session["status"] == STATUS_IN_PROGRESS


# ============================================================================
# update_step_file
# ============================================================================


class TestUpdateStepFile:
    def test_writes_step_file(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(session_dir, "analysis", STATUS_COMPLETED, "# Analysis\n\nDone.")
        assert path.exists()
        content = path.read_text()
        assert "status: completed" in content
        assert "# Analysis" in content

    def test_includes_json_data(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(
            session_dir, "analysis", STATUS_COMPLETED,
            "# Analysis\n\nDone.",
            data={"source_files": ["A.java", "B.java"]},
        )
        content = path.read_text()
        assert "```json" in content
        assert '"source_files"' in content
        assert "A.java" in content

    def test_updates_spec_progress(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        update_step_file(session_dir, "analysis", STATUS_COMPLETED, "# Done")
        spec = (tmp_path / ".testboost" / "sessions" / result["session_id"] / "spec.md")
        content = spec.read_text()
        assert "| analysis | completed |" in content

    def test_in_progress_status(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(session_dir, "generation", STATUS_IN_PROGRESS, "# Generating...")
        content = path.read_text()
        assert "status: in_progress" in content

    def test_failed_status(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        path = update_step_file(session_dir, "validation", STATUS_FAILED, "# Failed\n\nError: timeout")
        content = path.read_text()
        assert "status: failed" in content


# ============================================================================
# write_log
# ============================================================================


class TestWriteLog:
    def test_creates_log_file(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Test message")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        assert len(log_files) == 1

    def test_log_contains_message(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Found 12 files")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Found 12 files" in content
        assert "INFO" in content
        assert "analysis" in content

    def test_appends_multiple_entries(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Step 1")
        write_log(session_dir, "analysis", "INFO", "Step 2")
        write_log(session_dir, "analysis", "ERROR", "Something failed")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Step 1" in content
        assert "Step 2" in content
        assert "Something failed" in content

    def test_includes_kwargs(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        session_dir = result["session_dir"]

        write_log(session_dir, "analysis", "INFO", "Files found", count=12, path="/tmp")

        log_files = list((tmp_path / ".testboost" / "sessions" / result["session_id"] / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "count=12" in content


# ============================================================================
# get_session_status
# ============================================================================


class TestGetSessionStatus:
    def test_no_session(self, tmp_path):
        status = get_session_status(str(tmp_path))
        assert "No active session" in status

    def test_with_session(self, tmp_path):
        init_project(str(tmp_path))
        create_session(str(tmp_path), name="test")
        status = get_session_status(str(tmp_path))
        assert "001-test" in status
        assert "pending" in status

    def test_with_completed_step(self, tmp_path):
        init_project(str(tmp_path))
        result = create_session(str(tmp_path))
        update_step_file(result["session_dir"], "analysis", STATUS_COMPLETED, "# Done")
        status = get_session_status(str(tmp_path))
        assert "completed" in status


# ============================================================================
# Frontmatter helpers
# ============================================================================


class TestFrontmatter:
    def test_make_frontmatter(self):
        fm = _make_frontmatter(status="completed", step="analysis")
        assert "---" in fm
        assert "status: completed" in fm
        assert "step: analysis" in fm

    def test_make_frontmatter_skips_none(self):
        fm = _make_frontmatter(status="ok", extra=None)
        assert "extra" not in fm

    def test_parse_frontmatter(self):
        content = "---\nstatus: completed\nstep: analysis\n---\n\n# Title"
        result = _parse_frontmatter(content)
        assert result["status"] == "completed"
        assert result["step"] == "analysis"

    def test_parse_frontmatter_no_frontmatter(self):
        result = _parse_frontmatter("# Just a title\nNo frontmatter here")
        assert result == {}


# ============================================================================
# Path helpers
# ============================================================================


class TestPathHelpers:
    def test_get_testboost_dir(self, tmp_path):
        result = get_testboost_dir(str(tmp_path))
        assert result == tmp_path / ".testboost"

    def test_get_sessions_dir(self, tmp_path):
        result = get_sessions_dir(str(tmp_path))
        assert result == tmp_path / ".testboost" / "sessions"
