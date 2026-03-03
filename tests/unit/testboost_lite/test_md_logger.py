# SPDX-License-Identifier: Apache-2.0
"""Unit tests for testboost_lite.lib.md_logger."""

import pytest

from testboost_lite.lib.md_logger import MdLogger, get_log_path
from testboost_lite.lib.session_tracker import create_session, init_project


@pytest.fixture
def session_dir(tmp_path):
    """Create a session and return its directory."""
    init_project(str(tmp_path))
    result = create_session(str(tmp_path), name="test-logger")
    return result["session_dir"]


# ============================================================================
# MdLogger
# ============================================================================


class TestMdLogger:
    def test_info_writes_to_log(self, session_dir):
        logger = MdLogger(session_dir, "analysis")
        logger.info("Test info message")

        from pathlib import Path
        log_files = list((Path(session_dir) / "logs").glob("*.md"))
        assert len(log_files) == 1
        content = log_files[0].read_text()
        assert "Test info message" in content
        assert "INFO" in content

    def test_error_writes_to_log(self, session_dir):
        logger = MdLogger(session_dir, "analysis")
        logger.error("Something broke")

        from pathlib import Path
        log_files = list((Path(session_dir) / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Something broke" in content
        assert "ERROR" in content

    def test_warn_writes_to_log(self, session_dir):
        logger = MdLogger(session_dir, "analysis")
        logger.warn("Watch out")

        from pathlib import Path
        log_files = list((Path(session_dir) / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Watch out" in content
        assert "WARN" in content

    def test_debug_writes_to_log_only(self, session_dir, capsys):
        logger = MdLogger(session_dir, "analysis")
        logger.debug("Debug detail")

        # Debug should be in log file
        from pathlib import Path
        log_files = list((Path(session_dir) / "logs").glob("*.md"))
        content = log_files[0].read_text()
        assert "Debug detail" in content

    def test_info_prints_to_stdout(self, session_dir, capsys):
        logger = MdLogger(session_dir, "analysis")
        logger.info("Visible message")

        captured = capsys.readouterr()
        assert "Visible message" in captured.out

    def test_error_prints_to_stderr(self, session_dir, capsys):
        logger = MdLogger(session_dir, "analysis")
        logger.error("Error message")

        captured = capsys.readouterr()
        assert "Error message" in captured.err

    def test_result_prints_header(self, session_dir, capsys):
        logger = MdLogger(session_dir, "analysis")
        logger.result("Analysis Complete", "Found 12 files")

        captured = capsys.readouterr()
        assert "## Analysis Complete" in captured.out
        assert "Found 12 files" in captured.out

    def test_data_prints_summary(self, session_dir, capsys):
        logger = MdLogger(session_dir, "analysis")
        logger.data("Source files", ["a.java", "b.java", "c.java"])

        captured = capsys.readouterr()
        assert "3 entries" in captured.out

    def test_data_verbose_prints_json(self, session_dir, capsys):
        logger = MdLogger(session_dir, "analysis", verbose=True)
        logger.data("Config", {"key": "value"})

        captured = capsys.readouterr()
        assert '"key"' in captured.out
        assert '"value"' in captured.out

    def test_summary_counts(self, session_dir):
        logger = MdLogger(session_dir, "analysis")
        logger.info("ok 1")
        logger.info("ok 2")
        logger.warn("watch out")
        logger.error("boom")

        summary = logger.summary()
        assert "2 info" in summary
        assert "1 warnings" in summary
        assert "1 errors" in summary
        assert "boom" in summary

    def test_summary_lists_errors(self, session_dir):
        logger = MdLogger(session_dir, "analysis")
        logger.error("First error")
        logger.error("Second error")

        summary = logger.summary()
        assert "First error" in summary
        assert "Second error" in summary

    def test_multiple_steps(self, session_dir):
        """Loggers for different steps write to the same date file."""
        logger1 = MdLogger(session_dir, "analysis")
        logger2 = MdLogger(session_dir, "generation")

        logger1.info("Analysis started")
        logger2.info("Generation started")

        from pathlib import Path
        log_files = list((Path(session_dir) / "logs").glob("*.md"))
        assert len(log_files) == 1  # Same date = same file
        content = log_files[0].read_text()
        assert "analysis" in content
        assert "generation" in content


# ============================================================================
# get_log_path
# ============================================================================


class TestGetLogPath:
    def test_returns_path_with_date(self, session_dir):
        path = get_log_path(session_dir)
        assert "logs" in str(path)
        assert path.suffix == ".md"
        # Path should contain today's date
        import re
        assert re.search(r"\d{4}-\d{2}-\d{2}", str(path))
