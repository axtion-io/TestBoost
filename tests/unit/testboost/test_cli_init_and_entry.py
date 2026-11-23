# SPDX-License-Identifier: Apache-2.0
"""init technology selection and the CLI entry point (docs/workflow.md §1)."""

import argparse
import sys
from pathlib import Path

from src.lib.cli import cmd_init, main
from src.lib.session_tracker import get_current_session, get_session_technology


def _init(project: Path, tech: str | None = None) -> int:
    return cmd_init(argparse.Namespace(project_path=str(project), name=None, description="", tech=tech))


class TestInitTechnology:
    def test_auto_detects_and_stores_the_technology(self, tmp_path, capsys):
        (tmp_path / "pom.xml").write_text("<project/>")
        assert _init(tmp_path) == 0
        session = get_current_session(str(tmp_path))
        assert get_session_technology(Path(session["session_dir"])) == "java-spring"
        assert "matched: pom.xml" in capsys.readouterr().out

    def test_polyglot_project_prints_a_notice_and_java_wins(self, tmp_path, capsys):
        (tmp_path / "pom.xml").write_text("<project/>")
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        assert _init(tmp_path) == 0
        out = capsys.readouterr().out
        assert "Multiple technology indicators" in out and "python-pytest" in out

    def test_explicit_tech_overrides_detection(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        assert _init(tmp_path, tech="python-pytest") == 0
        session = get_current_session(str(tmp_path))
        assert get_session_technology(Path(session["session_dir"])) == "python-pytest"

    def test_unknown_tech_is_rejected_without_creating_a_session(self, tmp_path, capsys):
        assert _init(tmp_path, tech="cobol") == 1
        assert "Unknown technology 'cobol'" in capsys.readouterr().err
        assert get_current_session(str(tmp_path)) is None

    def test_undetectable_project_asks_for_tech(self, tmp_path, capsys):
        assert _init(tmp_path) == 1
        assert "--tech" in capsys.readouterr().err
        assert not (tmp_path / ".testboost").exists()

    def test_missing_project_path(self, tmp_path):
        assert _init(tmp_path / "nope") == 1


class TestEntryPoint:
    def _main(self, monkeypatch, *argv):
        monkeypatch.setattr(sys, "argv", ["testboost", *argv])
        return main()

    def test_list_plugins(self, monkeypatch, capsys):
        assert self._main(monkeypatch, "--list-plugins") == 0
        out = capsys.readouterr().out
        assert "java-spring" in out and "python-pytest" in out and "pom.xml" in out

    def test_no_command_prints_help_and_fails(self, monkeypatch, capsys):
        assert self._main(monkeypatch) == 1
        assert "usage:" in capsys.readouterr().out
