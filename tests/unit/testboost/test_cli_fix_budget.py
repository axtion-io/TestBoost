# SPDX-License-Identifier: Apache-2.0
"""config.yaml-driven budgets of the generate/validate loops.

docs/configuration.md: `max_correction_retries` bounds the compile-fix loop
and `test_timeout_seconds` bounds a test run. Both used to be written to
config.yaml and never read.
"""

import argparse
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib.cli import _attempt_compile_fix, _cmd_validate_async
from src.lib.plugins import get_registry
from src.lib.session_tracker import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    get_current_session,
    update_step_file,
)
from tests.unit.testboost.helpers import failing_compile


class _Logger:
    def __getattr__(self, _name):
        return lambda *a, **k: None


def _set_config(project: Path, **values) -> None:
    (project / ".testboost" / "config.yaml").write_text(
        "".join(f"{k}: {v}\n" for k, v in values.items())
    )


class TestCompileFixBudget:
    @pytest.mark.asyncio
    async def test_budget_is_compile_checks_so_fixes_are_budget_minus_one(self, tmp_path):
        test_file = tmp_path / "OrderServiceTest.java"
        test_file.write_text("broken")
        fixes = iter(f"fix {i}" for i in range(10))
        fix = AsyncMock(side_effect=lambda *a, **k: next(fixes))

        with patch("src.lib.bridge.fix_compilation_errors", new=fix), \
             patch("subprocess.run", return_value=failing_compile()):
            code, exhausted = await _attempt_compile_fix(
                str(tmp_path), test_file, "broken", "OrderService", _Logger(),
                max_attempts=5,
            )

        assert fix.await_count == 4
        assert exhausted == {"errors": exhausted["errors"], "attempts": 4}
        assert code == "fix 3" == test_file.read_text()

    @pytest.mark.asyncio
    async def test_hints_cap_the_budget_to_a_single_fix(self, tmp_path):
        test_file = tmp_path / "OrderServiceTest.java"
        fix = AsyncMock(return_value="hinted")
        with patch("src.lib.bridge.fix_compilation_errors", new=fix), \
             patch("subprocess.run", return_value=failing_compile()):
            await _attempt_compile_fix(
                str(tmp_path), test_file, "broken", "OrderService", _Logger(),
                hints=["use BigDecimal"], max_attempts=5,
            )
        assert fix.await_count == 1
        assert "use BigDecimal" in fix.await_args.args[1]

    @pytest.mark.asyncio
    async def test_fix_prompt_comes_from_the_session_plugin(self, tmp_path):
        """A Python test must be fixed with the pytest prompt: the bridge used
        to drop the plugin's prompt dir, so python_pytest/compilation_fix.md
        was never loaded."""
        plugin = get_registry().get("python-pytest")
        test_file = tmp_path / "tests" / "test_billing.py"
        fix = AsyncMock(return_value="def test_x(): pass")
        failing = MagicMock(returncode=1, stdout="", stderr=f"File {test_file.name}, SyntaxError")
        with patch("src.lib.bridge.fix_compilation_errors", new=fix), \
             patch("subprocess.run", return_value=failing):
            await _attempt_compile_fix(
                str(tmp_path), test_file, "def test_x(:", "billing", _Logger(),
                plugin=plugin, max_attempts=2,
            )
        assert fix.await_args.kwargs["prompt_template_dir"] == "testing/python_pytest"

    @pytest.mark.asyncio
    async def test_bridge_loads_the_plugin_prompt_template(self):
        from src.lib.bridge import fix_compilation_errors

        llm = MagicMock()
        llm.ainvoke = AsyncMock(return_value=MagicMock(content="```python\nfixed\n```"))
        with patch("src.test_generation.generate_unit.get_llm", return_value=llm), \
             patch("src.test_generation.generate_unit.load_prompt_template",
                   return_value="{compile_errors}{test_code}") as load:
            fixed = await fix_compilation_errors(
                "code", "err", "billing", prompt_template_dir="testing/python_pytest",
            )
        load.assert_called_once_with("testing/python_pytest/compilation_fix.md")
        assert fixed == "fixed"


class TestValidateTimeouts:
    def _seed_generation(self, project):
        session = get_current_session(str(project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Generation\n")
        return Path(session["session_dir"])

    @pytest.mark.asyncio
    async def test_test_run_uses_configured_timeout(self, initialized_project):
        self._seed_generation(initialized_project)
        _set_config(initialized_project, test_timeout_seconds=900)
        ok = MagicMock(returncode=0, stdout="Tests run: 1", stderr="")
        with patch("subprocess.run", return_value=ok) as run:
            rc = await _cmd_validate_async(argparse.Namespace(
                project_path=str(initialized_project), verbose=False,
            ))
        assert rc == 0
        assert run.call_args_list[-1].kwargs["timeout"] == 900

    @pytest.mark.asyncio
    async def test_compile_timeout_fails_cleanly(self, initialized_project):
        """Regression: a hanging `mvn test-compile` raised UnboundLocalError
        (the handler read `test_timeout`, assigned only after compiling)."""
        session_dir = self._seed_generation(initialized_project)
        hang = subprocess.TimeoutExpired(cmd=["mvn", "test-compile"], timeout=120)
        with patch("subprocess.run", side_effect=hang):
            rc = await _cmd_validate_async(argparse.Namespace(
                project_path=str(initialized_project), verbose=False,
            ))
        assert rc == 1
        content = (session_dir / "validation.md").read_text()
        assert f"status: {STATUS_FAILED}" in content
        assert "mvn test-compile" in content


class _RecordingLogger:
    def __init__(self):
        self.warnings: list[str] = []

    def warn(self, msg):
        self.warnings.append(msg)

    def __getattr__(self, _name):
        return lambda *a, **k: None


class TestCompileFailuresNotCausedByTheTest:
    @pytest.mark.asyncio
    async def test_project_config_error_is_not_sent_to_the_llm(self, tmp_path):
        """Maven fails without naming the generated test (missing profile,
        corporate repo…): no LLM fix, and the user is told where to set the
        Maven flags (analysis.md maven_compile_cmd)."""
        logger = _RecordingLogger()
        fix = AsyncMock()
        broken_build = MagicMock(returncode=1, stdout="", stderr="[ERROR] Non-resolvable parent POM")
        with patch("src.lib.bridge.fix_compilation_errors", new=fix), \
             patch("subprocess.run", return_value=broken_build):
            code, exhausted = await _attempt_compile_fix(
                str(tmp_path), tmp_path / "OrderServiceTest.java", "code", "OrderService",
                logger, session_dir=str(tmp_path / "s1"),
            )
        fix.assert_not_called()
        assert (code, exhausted) == ("code", None)
        text = "\n".join(logger.warnings)
        assert "maven_compile_cmd" in text and str(tmp_path / "s1" / "analysis.md") in text
        assert "Non-resolvable parent POM" in text

    @pytest.mark.asyncio
    async def test_missing_maven_skips_the_check(self, tmp_path):
        logger = _RecordingLogger()
        with patch("subprocess.run", side_effect=FileNotFoundError("mvn")):
            code, exhausted = await _attempt_compile_fix(
                str(tmp_path), tmp_path / "XTest.java", "code", "X", logger,
            )
        assert (code, exhausted) == ("code", None)
        assert any("Compile check skipped" in w for w in logger.warnings)

    @pytest.mark.asyncio
    async def test_invalid_maven_command_override_falls_back_to_mvn(self, tmp_path):
        """analysis.md is user-editable: a non-Maven binary is refused."""
        logger = _RecordingLogger()
        ok = MagicMock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=ok) as run:
            await _attempt_compile_fix(
                str(tmp_path), tmp_path / "XTest.java", "code", "X", logger,
                maven_compile_cmd="rm -rf /",
            )
        assert run.call_args.args[0][1] == "test-compile"
        assert any("Invalid maven_compile_cmd" in w for w in logger.warnings)
