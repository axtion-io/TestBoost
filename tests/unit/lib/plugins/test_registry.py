# SPDX-License-Identifier: Apache-2.0
"""Unit tests for PluginRegistry."""

from pathlib import Path

import pytest

from src.lib.plugins.base import TechnologyPlugin
from src.lib.plugins.registry import PluginRegistry

# ---------------------------------------------------------------------------
# Minimal concrete plugin for testing
# ---------------------------------------------------------------------------

class _JavaLikePlugin(TechnologyPlugin):
    @property
    def identifier(self) -> str:
        return "test-java"

    @property
    def description(self) -> str:
        return "Test Java plugin"

    @property
    def detection_patterns(self) -> list[str]:
        return ["pom.xml"]

    @property
    def prompt_template_dir(self) -> str:
        return "config/prompts/testing"

    def find_source_files(self, project_path):
        return []

    def classify_source_file(self, relative_path):
        return "other"

    def test_file_name(self, source_relative_path):
        return source_relative_path.replace(".java", "Test.java")

    def test_file_pattern(self):
        return ["**/*Test.java"]

    def validation_command(self, project_path, session_config):
        return ["mvn", "test-compile"]

    def test_run_command(self, project_path, session_config):
        return ["mvn", "test"]

    def build_generation_context(self, project_path, source_file):
        return {"source_code": "", "class_name": "Test", "class_type": "other",
                "dependencies": [], "existing_tests": [], "conventions": {}}


class _PythonLikePlugin(TechnologyPlugin):
    @property
    def identifier(self) -> str:
        return "test-python"

    @property
    def description(self) -> str:
        return "Test Python plugin"

    @property
    def detection_patterns(self) -> list[str]:
        return ["pyproject.toml"]

    @property
    def prompt_template_dir(self) -> str:
        return "config/prompts/testing/python"

    def find_source_files(self, project_path):
        return []

    def classify_source_file(self, relative_path):
        return "module"

    def test_file_name(self, source_relative_path):
        return f"tests/test_{Path(source_relative_path).stem}.py"

    def test_file_pattern(self):
        return ["**/test_*.py"]

    def validation_command(self, project_path, session_config):
        return ["python", "-m", "py_compile", "{test_file}"]

    def test_run_command(self, project_path, session_config):
        return ["python", "-m", "pytest", "{test_file}"]

    def build_generation_context(self, project_path, source_file):
        return {"source_code": "", "class_name": "module", "class_type": "module",
                "dependencies": [], "existing_tests": [], "conventions": {}}


# ---------------------------------------------------------------------------
# PluginRegistry.detect() tests
# ---------------------------------------------------------------------------

class TestRegistryDetect:
    def test_detect_returns_first_matching_plugin(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        registry.register(_PythonLikePlugin())
        plugin = registry.detect(tmp_path)
        assert plugin is not None
        assert plugin.identifier == "test-java"

    def test_detect_returns_second_plugin_when_first_doesnt_match(self, tmp_path):
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        registry.register(_PythonLikePlugin())
        plugin = registry.detect(tmp_path)
        assert plugin is not None
        assert plugin.identifier == "test-python"

    def test_detect_returns_none_when_no_match(self, tmp_path):
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        registry.register(_PythonLikePlugin())
        plugin = registry.detect(tmp_path)
        assert plugin is None

    def test_detect_java_wins_over_python_when_both_present(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        (tmp_path / "pyproject.toml").write_text("[build-system]")
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())   # registered first
        registry.register(_PythonLikePlugin())
        plugin = registry.detect(tmp_path)
        assert plugin is not None
        assert plugin.identifier == "test-java"

    def test_detect_accepts_path_string(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        plugin = registry.detect(str(tmp_path))
        assert plugin is not None
        assert plugin.identifier == "test-java"


# ---------------------------------------------------------------------------
# PluginRegistry.get() tests
# ---------------------------------------------------------------------------

class TestRegistryGet:
    def test_get_returns_correct_plugin(self):
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        registry.register(_PythonLikePlugin())
        plugin = registry.get("test-java")
        assert plugin.identifier == "test-java"

    def test_get_raises_value_error_for_unknown_id(self):
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        with pytest.raises(ValueError) as exc_info:
            registry.get("unknown-lang")
        assert "unknown-lang" in str(exc_info.value)
        assert "test-java" in str(exc_info.value)

    def test_get_error_message_lists_available_plugins(self):
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        registry.register(_PythonLikePlugin())
        with pytest.raises(ValueError) as exc_info:
            registry.get("nonexistent")
        error_msg = str(exc_info.value)
        assert "test-java" in error_msg
        assert "test-python" in error_msg


# ---------------------------------------------------------------------------
# PluginRegistry.list_plugins() tests
# ---------------------------------------------------------------------------

class TestRegistryListPlugins:
    def test_list_plugins_returns_all_registered(self):
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        registry.register(_PythonLikePlugin())
        plugins = registry.list_plugins()
        assert len(plugins) == 2

    def test_list_plugins_returns_correct_fields(self):
        registry = PluginRegistry()
        registry.register(_JavaLikePlugin())
        plugins = registry.list_plugins()
        p = plugins[0]
        assert "identifier" in p
        assert "description" in p
        assert "detection_patterns" in p
        assert p["identifier"] == "test-java"
        assert isinstance(p["detection_patterns"], list)

    def test_list_plugins_empty_registry(self):
        registry = PluginRegistry()
        assert registry.list_plugins() == []


# ---------------------------------------------------------------------------
# ABC enforcement tests (T024 acceptance criterion)
# ---------------------------------------------------------------------------

class TestABCEnforcement:
    def test_instantiating_incomplete_plugin_raises_type_error(self):
        """A plugin that omits an abstract method must raise TypeError at instantiation."""
        with pytest.raises(TypeError):
            class _BadPlugin(TechnologyPlugin):
                @property
                def identifier(self):
                    return "bad"
                # Missing all other required abstract members

            _BadPlugin()

    def test_instantiating_partial_plugin_raises_type_error(self):
        """A plugin with only some abstract methods implemented still raises TypeError."""
        with pytest.raises(TypeError):
            class _PartialPlugin(TechnologyPlugin):
                @property
                def identifier(self):
                    return "partial"

                @property
                def description(self):
                    return "partial"

                @property
                def detection_patterns(self):
                    return ["partial.toml"]

                # Missing: prompt_template_dir, find_source_files, etc.

            _PartialPlugin()

    def test_complete_plugin_instantiates_successfully(self):
        """A fully implemented plugin must not raise."""
        plugin = _JavaLikePlugin()
        assert plugin.identifier == "test-java"
