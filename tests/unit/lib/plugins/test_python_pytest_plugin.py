# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PythonPytestPlugin."""

import textwrap
import pytest
from pathlib import Path

from src.lib.plugins.python_pytest import PythonPytestPlugin


@pytest.fixture
def plugin():
    return PythonPytestPlugin()


# ---------------------------------------------------------------------------
# Plugin properties
# ---------------------------------------------------------------------------

def test_identifier(plugin):
    assert plugin.identifier == "python-pytest"


def test_detection_patterns(plugin):
    patterns = plugin.detection_patterns
    assert "pyproject.toml" in patterns
    assert "setup.py" in patterns
    assert "setup.cfg" in patterns


def test_prompt_template_dir(plugin):
    assert "python_pytest" in plugin.prompt_template_dir


def test_test_file_pattern(plugin):
    patterns = plugin.test_file_pattern()
    assert "**/test_*.py" in patterns
    assert "**/*_test.py" in patterns


# ---------------------------------------------------------------------------
# find_source_files()
# ---------------------------------------------------------------------------

class TestFindSourceFiles:
    def test_discovers_python_files(self, plugin, tmp_path):
        (tmp_path / "my_module.py").write_text("x = 1")
        result = plugin.find_source_files(tmp_path)
        assert "my_module.py" in result

    def test_excludes_test_files(self, plugin, tmp_path):
        (tmp_path / "test_foo.py").write_text("def test_x(): pass")
        (tmp_path / "bar_test.py").write_text("def test_y(): pass")
        (tmp_path / "real.py").write_text("x = 1")
        result = plugin.find_source_files(tmp_path)
        assert "test_foo.py" not in result
        assert "bar_test.py" not in result
        assert "real.py" in result

    def test_excludes_conftest_and_init(self, plugin, tmp_path):
        (tmp_path / "conftest.py").write_text("")
        (tmp_path / "__init__.py").write_text("")
        (tmp_path / "service.py").write_text("x = 1")
        result = plugin.find_source_files(tmp_path)
        assert "conftest.py" not in result
        assert "__init__.py" not in result
        assert "service.py" in result

    def test_excludes_venv_directory(self, plugin, tmp_path):
        venv_dir = tmp_path / "venv"
        venv_dir.mkdir()
        (venv_dir / "something.py").write_text("x = 1")
        (tmp_path / "real.py").write_text("x = 1")
        result = plugin.find_source_files(tmp_path)
        assert not any("venv" in p for p in result)
        assert "real.py" in result

    def test_excludes_dot_venv_directory(self, plugin, tmp_path):
        dot_venv = tmp_path / ".venv"
        dot_venv.mkdir()
        (dot_venv / "lib.py").write_text("x = 1")
        (tmp_path / "app.py").write_text("x = 1")
        result = plugin.find_source_files(tmp_path)
        assert not any(".venv" in p for p in result)
        assert "app.py" in result

    def test_result_is_sorted(self, plugin, tmp_path):
        (tmp_path / "z_module.py").write_text("")
        (tmp_path / "a_module.py").write_text("")
        result = plugin.find_source_files(tmp_path)
        assert result == sorted(result)


# ---------------------------------------------------------------------------
# test_file_name()
# ---------------------------------------------------------------------------

class TestTestFileName:
    def test_src_prefix_stripped(self, plugin):
        result = plugin.test_file_name("src/services/user_service.py")
        assert result == "tests/services/test_user_service.py"

    def test_top_level_file(self, plugin):
        result = plugin.test_file_name("my_module.py")
        assert result == "tests/test_my_module.py"

    def test_nested_non_src(self, plugin):
        result = plugin.test_file_name("app/models/user.py")
        assert result == "tests/app/models/test_user.py"

    def test_backslash_separator(self, plugin):
        result = plugin.test_file_name("src\\services\\order.py")
        assert result == "tests/services/test_order.py"


# ---------------------------------------------------------------------------
# build_generation_context() — uses ast parsing
# ---------------------------------------------------------------------------

class TestBuildGenerationContext:
    def _write_source(self, tmp_path, filename, code):
        path = tmp_path / filename
        path.write_text(textwrap.dedent(code))
        return path

    def test_extracts_class_name(self, plugin, tmp_path):
        self._write_source(tmp_path, "user_service.py", """
            class UserService:
                def get_user(self, user_id: int) -> dict:
                    return {}
        """)
        ctx = plugin.build_generation_context(tmp_path, "user_service.py")
        assert ctx["class_name"] == "UserService"
        assert ctx["class_type"] == "class"

    def test_extracts_function_names(self, plugin, tmp_path):
        self._write_source(tmp_path, "utils.py", """
            def format_date(date_str: str) -> str:
                return date_str

            def parse_number(s: str) -> int:
                return int(s)
        """)
        ctx = plugin.build_generation_context(tmp_path, "utils.py")
        assert ctx["class_type"] == "function"
        fn_names = [f["name"] for f in ctx["functions"]]
        assert "format_date" in fn_names
        assert "parse_number" in fn_names

    def test_extracts_imports(self, plugin, tmp_path):
        self._write_source(tmp_path, "service.py", """
            import os
            from pathlib import Path
            from typing import Optional

            def do_something():
                pass
        """)
        ctx = plugin.build_generation_context(tmp_path, "service.py")
        assert "os" in ctx["dependencies"]

    def test_includes_source_code(self, plugin, tmp_path):
        self._write_source(tmp_path, "simple.py", "x = 42\n")
        ctx = plugin.build_generation_context(tmp_path, "simple.py")
        assert "x = 42" in ctx["source_code"]

    def test_has_required_keys(self, plugin, tmp_path):
        self._write_source(tmp_path, "empty.py", "")
        ctx = plugin.build_generation_context(tmp_path, "empty.py")
        for key in ["source_code", "class_name", "class_type", "dependencies", "existing_tests", "conventions"]:
            assert key in ctx, f"Missing required key: {key}"
