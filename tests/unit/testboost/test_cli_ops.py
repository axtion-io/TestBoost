# SPDX-License-Identifier: Apache-2.0
"""Operations commands: cleanup, doctor, metrics emission.

LLM calls are mocked via the bridge so the workflow is tested without an
API key. CRITICAL: if the LLM is unreachable, the error MUST propagate.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

from src.lib.cli import (
    cmd_init,
)
from src.lib.session_tracker import (
    get_current_session,
)


class TestCmdCleanup:
    def test_no_candidates_prints_message(self, tmp_path, capsys):
        from src.lib.cli import cmd_cleanup
        cmd_init(argparse.Namespace(
            project_path=str(tmp_path), name=None, description="", tech="java-spring",
        ))
        capsys.readouterr()
        rc = cmd_cleanup(argparse.Namespace(
            project_path=str(tmp_path), ttl_hours=24, dry_run=False,
        ))
        assert rc == 0
        assert "No abandoned sessions" in capsys.readouterr().out

    def test_dry_run_does_not_modify(self, tmp_path, capsys):
        import re

        from src.lib.cli import cmd_cleanup
        from src.lib.session_tracker import _parse_frontmatter
        cmd_init(argparse.Namespace(
            project_path=str(tmp_path), name=None, description="", tech="java-spring",
        ))
        # Flip to awaiting_input + backdate
        session = get_current_session(str(tmp_path))
        spec = Path(session["session_dir"]) / "spec.md"
        c = spec.read_text()
        c = c.replace("status: in_progress", "status: awaiting_input")
        c = re.sub(r"started_at:.*", "started_at: 2020-01-01T00:00:00Z", c, count=1)
        spec.write_text(c)

        capsys.readouterr()
        rc = cmd_cleanup(argparse.Namespace(
            project_path=str(tmp_path), ttl_hours=24, dry_run=True,
        ))
        assert rc == 0
        assert "Would mark" in capsys.readouterr().out
        # Status unchanged
        fm = _parse_frontmatter(spec.read_text())
        assert fm["status"] == "awaiting_input"

    def test_real_run_marks_abandoned(self, tmp_path):
        import re

        from src.lib.cli import cmd_cleanup
        from src.lib.session_tracker import _parse_frontmatter
        cmd_init(argparse.Namespace(
            project_path=str(tmp_path), name=None, description="", tech="java-spring",
        ))
        session = get_current_session(str(tmp_path))
        spec = Path(session["session_dir"]) / "spec.md"
        c = spec.read_text()
        c = c.replace("status: in_progress", "status: awaiting_input")
        c = re.sub(r"started_at:.*", "started_at: 2020-01-01T00:00:00Z", c, count=1)
        spec.write_text(c)

        rc = cmd_cleanup(argparse.Namespace(
            project_path=str(tmp_path), ttl_hours=24, dry_run=False,
        ))
        assert rc == 0
        fm = _parse_frontmatter(spec.read_text())
        assert fm["status"] == "abandoned"
class TestCmdDoctor:
    def test_reports_missing_tb_secret(self, tmp_path, capsys):
        from src.lib.cli import cmd_doctor
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock):
            rc = cmd_doctor(argparse.Namespace(project_path=str(tmp_path)))
        out = capsys.readouterr().out
        # tb_secret check should report KO
        assert "[KO]" in out and "tb_secret" in out
        assert rc == 1

    def test_reports_llm_failure(self, tmp_path, capsys):
        from src.lib.cli import cmd_doctor
        cmd_init(argparse.Namespace(
            project_path=str(tmp_path), name=None, description="", tech="java-spring",
        ))
        capsys.readouterr()
        async def boom(*a, **k):
            raise RuntimeError("LLM unreachable")
        with patch("src.lib.startup_checks.check_llm_connection", new=boom):
            rc = cmd_doctor(argparse.Namespace(project_path=str(tmp_path)))
        out = capsys.readouterr().out
        assert "LLM ping failed" in out
        assert rc == 1
class TestMetricsEmission:
    def test_main_emits_metrics_line(self, tmp_path, capsys, monkeypatch):
        """A successful command produces exactly one [TESTBOOST_METRICS:{...}] line."""
        from src.lib.cli import main

        # Ensure we don't accidentally hit the network or filesystem in a way
        # we can't control — `doctor` is a small isolated command, but pin
        # the LLM check to succeed.
        async def ok(*a, **k):
            return None

        monkeypatch.setattr("sys.argv", ["testboost", "cleanup", str(tmp_path), "--dry-run"])
        # Avoid the directory-not-initialised path: pre-init
        cmd_init(argparse.Namespace(
            project_path=str(tmp_path), name=None, description="", tech="java-spring",
        ))
        capsys.readouterr()
        rc = main()
        assert rc == 0
        captured = capsys.readouterr()
        # Metrics go to stderr so stdout consumers (sign-answer JSON,
        # resume markdown) stay parseable
        assert "[TESTBOOST_METRICS:" not in captured.out
        metric_lines = [ln for ln in captured.err.splitlines() if ln.startswith("[TESTBOOST_METRICS:")]
        assert len(metric_lines) == 1
        payload_str = metric_lines[0][len("[TESTBOOST_METRICS:"):-1]
        payload = json.loads(payload_str)
        assert payload["command"] == "cleanup"
        assert payload["exit_code"] == 0
        assert "duration_ms" in payload
        assert payload["project_path"] == str(tmp_path)


# ============================================================================
# Phase 6 — batched questions, scoped answers, no-regeneration resume
# ============================================================================
