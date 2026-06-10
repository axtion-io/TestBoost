# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PythonPytestPlugin."""


import pytest

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
