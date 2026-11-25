# SPDX-License-Identifier: Apache-2.0
"""Agent mode: the host agent writes the tests, TestBoost never calls an LLM.

docs/workflow.md (Agent mode): `context` writes one prompt per gap with the
test path the plugin expects; the agent writes the test there; `generate
--agent` registers and compiles it; validate/mutate are unchanged. Same
cycle for surviving mutants with `context --killer` / `killer --agent`.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.lib.cli import _cmd_validate_async, cmd_context, cmd_generate, cmd_init, cmd_killer, main
from src.lib.session_tracker import get_current_session
from tests.unit.testboost.helpers import (
    ORDER_SERVICE,
    USER_CONTROLLER,
    prepare_mutation,
    setup_gaps,
)

ORDER_TEST = "src/test/java/com/example/service/OrderServiceTest.java"
CONTROLLER_TEST = "src/test/java/com/example/web/UserControllerTest.java"
COMPILES = "package com.example.service;\nclass OrderServiceTest {\n  @Test void a() {}\n  @Test void b() {}\n}\n"


@pytest.fixture(autouse=True)
def no_llm():
    """Any LLM use in agent mode is a bug: every entry point raises."""
    boom = AssertionError("agent mode must not call an LLM")
    with patch("src.lib.llm.get_llm", side_effect=boom), \
         patch("src.test_generation.generate_unit.get_llm", side_effect=boom), \
         patch("src.test_generation.killer_tests.get_llm", side_effect=boom), \
         patch("src.lib.startup_checks.check_llm_connection", side_effect=boom):
        yield


def _args(project, **kw):
    return argparse.Namespace(project_path=str(project), verbose=False, **kw)


def _session_dir(project) -> Path:
    return Path(get_current_session(str(project))["session_dir"])


def _write(project, rel, code=COMPILES):
    path = Path(project) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(code)


def _generation(project):
    from src.lib.commands._shared import _extract_json_field, _read_step_status
    md = _session_dir(project) / "generation.md"
    return _read_step_status(md), json.loads(json.dumps(_extract_json_field(md.read_text(), "generated")))


class TestContext:
    @pytest.mark.asyncio
    async def test_one_prompt_per_gap_with_the_plugin_test_path(self, initialized_project, capsys):
        await setup_gaps(initialized_project, files=[ORDER_SERVICE, USER_CONTROLLER])
        assert cmd_context(_args(initialized_project, files=None, killer=False)) == 0

        manifest = json.loads((_session_dir(initialized_project) / "agent/manifest.json").read_text())
        assert [(m["source_file"], m["test_path"]) for m in manifest] == [
            (ORDER_SERVICE, ORDER_TEST), (USER_CONTROLLER, CONTROLLER_TEST),
        ]
        brief = Path(manifest[0]["prompt_file"]).read_text()
        assert brief.startswith(f"# Test to write: `{ORDER_TEST}`")
        assert f"`{ORDER_SERVICE}` — read it" in brief                # the agent reads the source…
        assert "public class OrderService" not in brief             # …so the brief does not copy it
        assert "Test stack available" in brief and "generate <project> --agent" in brief
        out = capsys.readouterr().out
        assert "2 test(s) to write" in out and ORDER_TEST in out

    @pytest.mark.asyncio
    async def test_files_filter(self, initialized_project):
        await setup_gaps(initialized_project, files=[ORDER_SERVICE, USER_CONTROLLER])
        cmd_context(_args(initialized_project, files=["web/"], killer=False))
        manifest = json.loads((_session_dir(initialized_project) / "agent/manifest.json").read_text())
        assert [m["test_path"] for m in manifest] == [CONTROLLER_TEST]

    @pytest.mark.asyncio
    async def test_files_outside_the_gaps_is_targeted_as_asked(self, initialized_project):
        """An already-tested class (absent from gaps) can still be strengthened."""
        await setup_gaps(initialized_project, files=[ORDER_SERVICE, USER_CONTROLLER])
        gaps = _session_dir(initialized_project) / "coverage-gaps.md"
        gaps.write_text(gaps.read_text().replace(USER_CONTROLLER, "src/main/java/com/example/Other.java"))
        assert cmd_context(_args(initialized_project, files=["UserController"], killer=False)) == 0
        manifest = json.loads((_session_dir(initialized_project) / "agent/manifest.json").read_text())
        assert [m["test_path"] for m in manifest] == [CONTROLLER_TEST]

    @pytest.mark.asyncio
    async def test_files_matching_nothing_is_an_error_not_every_gap(self, initialized_project, capsys):
        await setup_gaps(initialized_project, files=[ORDER_SERVICE, USER_CONTROLLER])
        assert cmd_context(_args(initialized_project, files=["Typo"], killer=False)) == 1
        assert not (_session_dir(initialized_project) / "agent/manifest.json").exists()
        assert "No source file matches --files Typo" in capsys.readouterr().err

    def test_requires_gaps(self, initialized_project):
        assert cmd_context(_args(initialized_project, files=None, killer=False)) == 1


class TestGenerateAgent:
    async def _context(self, project, files=(ORDER_SERVICE,)):
        await setup_gaps(project, files=list(files))
        assert cmd_context(_args(project, files=None, killer=False)) == 0

    @pytest.mark.asyncio
    async def test_missing_test_is_reported_not_generated(self, initialized_project, capsys):
        await self._context(initialized_project)
        with patch("subprocess.run") as mvn:
            rc = cmd_generate(_args(initialized_project, files=None, agent=True))
        assert rc == 1
        mvn.assert_not_called()                                 # nothing to compile
        status, generated = _generation(initialized_project)
        assert (status, generated) == ("failed", [])
        assert "missing — write it" in capsys.readouterr().out

    @pytest.mark.asyncio
    async def test_written_test_is_compiled_registered_and_validates(self, initialized_project, capsys):
        await self._context(initialized_project)
        _write(initialized_project, ORDER_TEST)
        ok = MagicMock(returncode=0, stdout="Tests run: 2", stderr="")
        with patch("subprocess.run", return_value=ok) as mvn:
            assert cmd_generate(_args(initialized_project, files=None, agent=True)) == 0
        assert "test-compile" in mvn.call_args.args[0]
        status, generated = _generation(initialized_project)
        assert status == "completed"
        assert generated == [{"path": ORDER_TEST, "class_name": "OrderService",
                              "source_file": ORDER_SERVICE, "test_count": 2}]
        assert "[TESTBOOST_INTEGRITY:" in capsys.readouterr().out

        with patch("subprocess.run", return_value=ok):           # the next step is unchanged
            assert await _cmd_validate_async(_args(initialized_project)) == 0

    @pytest.mark.asyncio
    async def test_compile_errors_are_attributed_to_their_file(self, initialized_project):
        await self._context(initialized_project, files=(ORDER_SERVICE, USER_CONTROLLER))
        _write(initialized_project, ORDER_TEST)
        _write(initialized_project, CONTROLLER_TEST, "class UserControllerTest { @Test void x() {} }")
        broken = MagicMock(returncode=1, stdout="", stderr=(
            "[ERROR] /p/src/test/java/com/example/web/UserControllerTest.java:[1,40] cannot find symbol\n"))
        with patch("subprocess.run", return_value=broken):
            assert cmd_generate(_args(initialized_project, files=None, agent=True)) == 1
        report = (_session_dir(initialized_project) / "generation.md").read_text()
        assert f"Compilation errors: `{CONTROLLER_TEST}`" in report
        assert f"Compilation errors: `{ORDER_TEST}`" not in report
        status, generated = _generation(initialized_project)
        assert status == "failed" and [g["path"] for g in generated] == [ORDER_TEST]

    def test_requires_context(self, initialized_project):
        assert cmd_generate(_args(initialized_project, files=None, agent=True)) == 1

    @pytest.mark.asyncio
    async def test_cli_flag(self, initialized_project, monkeypatch):
        await self._context(initialized_project)
        _write(initialized_project, ORDER_TEST)
        monkeypatch.setattr("sys.argv", ["testboost", "generate", str(initialized_project), "--agent"])
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
            assert main() == 0


class TestPythonProject:
    """Per-file compile check (`py_compile {test_file}`), for real."""

    @pytest.fixture(autouse=True)
    def _no_child_coverage(self, monkeypatch):
        for var in ("COV_CORE_SOURCE", "COV_CORE_CONFIG", "COV_CORE_DATAFILE", "COVERAGE_PROCESS_START"):
            monkeypatch.delenv(var, raising=False)

    @pytest.mark.asyncio
    async def test_syntax_error_blocks_registration(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
        (tmp_path / "billing.py").write_text("def total():\n    return 1\n")
        cmd_init(argparse.Namespace(project_path=str(tmp_path), name=None, description="", tech="python-pytest"))
        await setup_gaps(tmp_path, files=["billing.py"])
        assert cmd_context(_args(tmp_path, files=None, killer=False)) == 0

        _write(tmp_path, "tests/test_billing.py", "def test_total(:\n")
        assert cmd_generate(_args(tmp_path, files=None, agent=True)) == 1
        _write(tmp_path, "tests/test_billing.py", "import billing\n\ndef test_total():\n    assert billing.total() == 1\n")
        assert cmd_generate(_args(tmp_path, files=None, agent=True)) == 0


class TestKillerAgent:
    def _source(self, project):
        _write(project, "src/main/java/com/example/OrderService.java",
               "package com.example;\npublic class OrderService { int total(int a) { return a + 1; } }")

    def test_context_killer_requires_mutation(self, initialized_project):
        assert cmd_context(_args(initialized_project, files=None, killer=True, max_tests=10)) == 1

    def test_prompt_per_class_then_registration(self, initialized_project, capsys):
        prepare_mutation(initialized_project)
        self._source(initialized_project)
        assert cmd_context(_args(initialized_project, files=None, killer=True, max_tests=10)) == 0
        manifest = json.loads((_session_dir(initialized_project) / "agent/killer/manifest.json").read_text())
        killer_path = "src/test/java/com/example/OrderServiceKillerTest.java"
        assert [(m["class"], m["test_path"], m["mutants_targeted"]) for m in manifest] == [
            ("com.example.OrderService", killer_path, 1)]
        brief = Path(manifest[0]["prompt_file"]).read_text()
        assert "Replaced + with -" in brief and "testboost equivalent" in brief
        assert "src/main/java/com/example/OrderService.java" in brief

        assert cmd_killer(_args(initialized_project, agent=True)) == 1     # not written yet
        _write(initialized_project, killer_path, "class OrderServiceKillerTest { @Test void k() {} }")
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")):
            assert cmd_killer(_args(initialized_project, agent=True)) == 0
        report = (_session_dir(initialized_project) / "killer-tests.md").read_text()
        assert "status: completed" in report and killer_path in report


class TestAgentEdgeCases:
    def test_no_session(self, tmp_path):
        assert cmd_context(_args(tmp_path, files=None, killer=False)) == 1
        assert cmd_generate(_args(tmp_path, files=None, agent=True)) == 1

    @pytest.mark.asyncio
    async def test_build_failure_not_naming_a_test_is_a_project_config_error(self, initialized_project, capsys):
        """Maven fails without citing the agent's test (missing profile, repository…): the
        registration fails and points at the build command in analysis.md."""
        await setup_gaps(initialized_project, files=[ORDER_SERVICE])
        cmd_context(_args(initialized_project, files=None, killer=False))
        _write(initialized_project, ORDER_TEST)
        broken = MagicMock(returncode=1, stdout="", stderr="[ERROR] Non-resolvable parent POM\n")
        with patch("subprocess.run", return_value=broken):
            assert cmd_generate(_args(initialized_project, files=None, agent=True)) == 1
        report = (_session_dir(initialized_project) / "generation.md").read_text()
        assert "Non-resolvable parent POM" in report
        assert "maven_compile_cmd" in capsys.readouterr().out

    @pytest.mark.asyncio
    async def test_without_maven_registration_defers_to_validate(self, initialized_project):
        await setup_gaps(initialized_project, files=[ORDER_SERVICE])
        cmd_context(_args(initialized_project, files=None, killer=False))
        _write(initialized_project, ORDER_TEST)
        with patch("subprocess.run", side_effect=FileNotFoundError("mvn")):
            assert cmd_generate(_args(initialized_project, files=None, agent=True)) == 0
        assert _generation(initialized_project)[0] == "completed"

    def test_killer_context_skips_classes_without_source(self, initialized_project, capsys):
        prepare_mutation(initialized_project, surviving=[
            {"class": "com.example.Ghost", "method": "m", "mutator": "MATH", "line": 1, "description": "d"},
            {"class": "../../etc", "method": "m", "mutator": "MATH", "line": 1, "description": "d"},
        ])
        assert cmd_context(_args(initialized_project, files=None, killer=True, max_tests=10)) == 0
        manifest = json.loads((_session_dir(initialized_project) / "agent/killer/manifest.json").read_text())
        assert manifest == []
        assert "0 killer test class(es)" in capsys.readouterr().out
