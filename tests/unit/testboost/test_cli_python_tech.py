# SPDX-License-Identifier: Apache-2.0
"""Regression tests for generate on python-pytest projects.

History (MR review finding): the generator derived test paths with
Java-only rules and returned non-.java paths UNCHANGED, so generated
pytest code was written over the production module itself — corrupting
the user's source tree. The test path must come from the technology
plugin, and the write site must refuse source/target collisions.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.lib.cli import (
    _cmd_analyze_async,
    _cmd_gaps_async,
    _cmd_generate_async,
    cmd_init,
)

PY_TEST_CODE = "import app\n\n\ndef test_app():\n    assert app.PRODUCTION_CODE == 42\n"


@pytest.fixture
def python_project(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
    (tmp_path / "app.py").write_text("PRODUCTION_CODE = 42\n")
    services = tmp_path / "src" / "services"
    services.mkdir(parents=True)
    (services / "user_service.py").write_text("class UserService:\n    pass\n")
    cmd_init(argparse.Namespace(
        project_path=str(tmp_path), name=None, description="", tech="python-pytest",
    ))
    return tmp_path


async def _run_pipeline(project):
    ctx = json.dumps({
        "success": True, "project_type": "python-pytest", "build_system": "unknown",
        "java_version": None, "frameworks": [], "test_frameworks": [],
        "source_structure": {"class_count": 2, "packages": []},
        "test_structure": {"test_count": 0}, "dependencies": [],
    })
    args = argparse.Namespace(project_path=str(project), verbose=False)
    with patch("src.lib.bridge.analyze_project_context", new=AsyncMock(return_value=ctx)), \
         patch("src.lib.bridge.detect_test_conventions",
               new=AsyncMock(return_value='{"success": false}')), \
         patch("src.lib.bridge.build_class_index", return_value={}), \
         patch("src.lib.bridge.extract_test_examples", return_value=[]):
        await _cmd_analyze_async(args)
    await _cmd_gaps_async(args)

    with patch("src.lib.startup_checks.check_llm_connection", new=AsyncMock()), \
         patch("src.lib.bridge.analyze_edge_cases",
               new=AsyncMock(return_value=[{"scenario": "x", "expected": "y"}])), \
         patch("src.test_generation.generate_unit._generate_test_code_with_llm",
               new=AsyncMock(return_value=PY_TEST_CODE)):
        return await _cmd_generate_async(argparse.Namespace(
            project_path=str(project), verbose=False, files=None,
            fail_on_uncertainty=False, answer_file=None,
        ))


class TestPythonGenerationDoesNotClobberSources:
    @pytest.mark.asyncio
    async def test_sources_intact_and_tests_under_tests_dir(self, python_project):
        rc = await _run_pipeline(python_project)
        assert rc == 0

        # Production sources are untouched, byte for byte
        assert (python_project / "app.py").read_text() == "PRODUCTION_CODE = 42\n"
        assert (python_project / "src/services/user_service.py").read_text() == \
            "class UserService:\n    pass\n"

        # Generated tests landed under tests/, per the plugin's mapping
        assert (python_project / "tests/test_app.py").read_text() == PY_TEST_CODE
        assert (python_project / "tests/services/test_user_service.py").exists()

    @pytest.mark.asyncio
    async def test_report_records_plugin_test_paths(self, python_project):
        from src.lib.session_tracker import get_current_session

        await _run_pipeline(python_project)
        session = get_current_session(str(python_project))
        gen_md = (Path(session["session_dir"]) / "generation.md").read_text()
        assert "tests/test_app.py" in gen_md
        # The old, source-clobbering pairs must never appear
        assert "| `app.py` | `app.py` |" not in gen_md


class TestSafeTestTarget:
    def test_refuses_source_target_collision(self, tmp_path):
        from src.lib.commands.generate_cmd import _safe_test_target

        (tmp_path / "app.py").write_text("x = 1\n")
        with pytest.raises(RuntimeError, match="refusing to write"):
            _safe_test_target(str(tmp_path), "app.py", "app.py")

    def test_accepts_distinct_target(self, tmp_path):
        from src.lib.commands.generate_cmd import _safe_test_target

        target = _safe_test_target(str(tmp_path), "tests/test_app.py", "app.py")
        assert target == tmp_path / "tests/test_app.py"
