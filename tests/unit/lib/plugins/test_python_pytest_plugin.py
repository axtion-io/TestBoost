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
# classify_source_file() — reads the file relative to the PROJECT, not the CWD
# ---------------------------------------------------------------------------

class TestClassifySourceFile:
    """analyze passes paths relative to the project: resolving them against
    the CWD classified every file as 'module'."""

    def _write(self, root, rel, code):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(code)

    def test_categories_from_top_level_definitions(self, plugin, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path.parent)  # CWD is NOT the project
        self._write(tmp_path, "app/models.py", "class User:\n    def name(self): ...\n")
        self._write(tmp_path, "app/utils.py", "async def fetch(): ...\ndef parse(): ...\n")
        self._write(tmp_path, "app/settings.py", "DEBUG = True\n")
        assert plugin.classify_source_file("app/models.py", tmp_path) == "class"
        assert plugin.classify_source_file("app/utils.py", tmp_path) == "function"
        assert plugin.classify_source_file("app/settings.py", tmp_path) == "module"

    def test_nested_definitions_do_not_count(self, plugin, tmp_path):
        self._write(tmp_path, "m.py", "if True:\n    class Hidden: ...\n")
        assert plugin.classify_source_file("m.py", tmp_path) == "module"

    def test_unreadable_or_invalid_file_is_module(self, plugin, tmp_path):
        self._write(tmp_path, "broken.py", "def (:\n")
        assert plugin.classify_source_file("broken.py", tmp_path) == "module"
        assert plugin.classify_source_file("missing.py", tmp_path) == "module"
