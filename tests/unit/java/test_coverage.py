# SPDX-License-Identifier: Apache-2.0
"""`gaps --coverage`: what is really untested, measured by JaCoCo.

On a module tested by feature (MensuelTest, ParityTest…) the file-level rule
reported 11 % of classes tested for 93 % of lines covered.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.java.coverage import jacoco_command, read_reports
from src.lib.commands._shared import _extract_json_field
from src.lib.session_tracker import get_current_session

JACOCO_XML = """<?xml version="1.0" encoding="UTF-8"?>
<report name="demo">
  <package name="com/example/service">
    <sourcefile name="OrderService.java">
      <line nr="10" mi="0" ci="3" mb="0" cb="0"/>
      <line nr="12" mi="2" ci="0" mb="0" cb="0"/>
      <line nr="13" mi="1" ci="0" mb="0" cb="0"/>
      <line nr="14" mi="4" ci="0" mb="0" cb="0"/>
      <line nr="20" mi="0" ci="2" mb="1" cb="1"/>
      <line nr="31" mi="3" ci="0" mb="0" cb="0"/>
      <counter type="LINE" missed="4" covered="2"/>
    </sourcefile>
    <sourcefile name="UserService.java">
      <line nr="5" mi="0" ci="4" mb="0" cb="0"/>
      <counter type="LINE" missed="0" covered="9"/>
    </sourcefile>
  </package>
</report>
"""

ORDER = "src/main/java/com/example/service/OrderService.java"
USER = "src/main/java/com/example/service/UserService.java"


def _write_report(root: Path, module: str = "") -> None:
    report = root / module / "target/site/jacoco/jacoco.xml"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(JACOCO_XML)


class TestReport:
    def test_line_coverage_and_uncovered_ranges_per_source_file(self, tmp_path):
        _write_report(tmp_path)
        cov = read_reports(str(tmp_path))
        lines = cov[ORDER].pop("lines")
        assert cov[ORDER] == {"line_pct": 33.3, "missed": 4, "covered": 2,
                              "uncovered": "12-14, 31", "partial": "20"}
        assert lines == {10: "covered", 12: "missed", 13: "missed", 14: "missed", 20: "partial", 31: "missed"}
        assert cov[USER]["line_pct"] == 100.0

    def test_multi_module_paths_are_relative_to_the_project(self, tmp_path):
        _write_report(tmp_path, "billing")
        assert f"billing/{ORDER}" in read_reports(str(tmp_path))

    def test_jacoco_wraps_the_project_test_command(self):
        cmd = jacoco_command(["mvn", "test", "-q", "-P", "corp"])
        assert cmd[0] == "mvn" and cmd[-3:] == ["-q", "-P", "corp"]
        assert cmd[1].endswith(":prepare-agent") and cmd[2] == "test" and cmd[3].endswith(":report")
        assert "-Dmaven.test.failure.ignore=true" in cmd
        with pytest.raises(ValueError):
            jacoco_command(["mvn", "verify"])


class TestGapsWithCoverage:
    async def _gaps(self, project, **kw):
        from src.lib.cli import _cmd_gaps_async
        from tests.unit.testboost.helpers import setup_gaps

        await setup_gaps(project, files=[ORDER, USER], run_gaps=False)

        def fake_mvn(cmd, **_):
            _write_report(project)
            return MagicMock(returncode=0, stdout="", stderr="")

        with patch("subprocess.run", side_effect=fake_mvn) as mvn:
            rc = await _cmd_gaps_async(argparse.Namespace(project_path=str(project), verbose=False,
                                                          coverage=True, **kw))
        session = Path(get_current_session(str(project))["session_dir"])
        return rc, (session / "coverage-gaps.md").read_text(), mvn

    @pytest.mark.asyncio
    async def test_gaps_are_classes_below_the_threshold(self, initialized_project):
        rc, md, mvn = await self._gaps(initialized_project, min_coverage=80.0)
        assert rc == 0
        assert any(":prepare-agent" in part for part in mvn.call_args.args[0])
        # UserService has UserServiceTest.java but is file-level "covered" either way;
        # OrderService has no test file AND is really under-covered.
        assert _extract_json_field(md, "gaps") == [ORDER]
        assert _extract_json_field(md, "coverage")[ORDER]["uncovered"] == "12-14, 31"
        assert "| 1 | `" + ORDER + "` | 33.3% | 12-14, 31 |" in md

    @pytest.mark.asyncio
    async def test_agent_brief_points_at_the_uncovered_lines(self, initialized_project):
        from src.lib.cli import cmd_context

        await self._gaps(initialized_project, min_coverage=80.0)
        cmd_context(argparse.Namespace(project_path=str(initialized_project), verbose=False, files=None,
                                       killer=False))
        session = Path(get_current_session(str(initialized_project))["session_dir"])
        manifest = json.loads((session / "agent/manifest.json").read_text())
        brief = Path(manifest[0]["prompt_file"]).read_text()
        assert "Current line coverage**: 33.3%; uncovered lines: 12-14, 31" in brief
        assert "missed branches: 20" in brief

    @pytest.mark.asyncio
    async def test_no_report_fails_with_the_maven_output(self, initialized_project):
        from src.lib.cli import _cmd_gaps_async
        from tests.unit.testboost.helpers import setup_gaps

        await setup_gaps(initialized_project, files=[ORDER], run_gaps=False)
        with patch("subprocess.run", return_value=MagicMock(returncode=1, stdout="BUILD FAILURE", stderr="")):
            rc = await _cmd_gaps_async(argparse.Namespace(project_path=str(initialized_project),
                                                          verbose=False, coverage=True, min_coverage=80.0))
        assert rc == 1
        session = Path(get_current_session(str(initialized_project))["session_dir"])
        assert "status: failed" in (session / "coverage-gaps.md").read_text()
