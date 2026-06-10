# SPDX-License-Identifier: Apache-2.0
"""Unit tests for JavaSpringPlugin."""

from unittest.mock import patch

import pytest

from src.lib.plugins.java_spring import JavaSpringPlugin


@pytest.fixture
def plugin():
    return JavaSpringPlugin()


# ---------------------------------------------------------------------------
# Plugin properties
# ---------------------------------------------------------------------------

def test_identifier(plugin):
    assert plugin.identifier == "java-spring"


def test_detection_patterns(plugin):
    patterns = plugin.detection_patterns
    assert "pom.xml" in patterns
    assert "build.gradle" in patterns
    assert "build.gradle.kts" in patterns


def test_prompt_template_dir(plugin):
    assert plugin.prompt_template_dir == "testing"


def test_test_file_pattern(plugin):
    patterns = plugin.test_file_pattern()
    assert "**/*Test.java" in patterns
    assert "**/*Tests.java" in patterns


# ---------------------------------------------------------------------------
# find_source_files() — delegates to src.java.discovery
# ---------------------------------------------------------------------------

def test_find_source_files_delegates_to_discovery(plugin, tmp_path):
    with patch("src.java.discovery.find_source_files") as mock_find:
        mock_find.return_value = ["src/main/java/com/example/Foo.java"]
        result = plugin.find_source_files(tmp_path)
    mock_find.assert_called_once_with(str(tmp_path))
    assert result == ["src/main/java/com/example/Foo.java"]


# ---------------------------------------------------------------------------
# classify_source_file() — delegates to src.java.discovery
# ---------------------------------------------------------------------------

def test_classify_source_file_delegates_to_discovery(plugin):
    with patch("src.java.discovery.classify_source_file") as mock_classify:
        mock_classify.return_value = "service"
        result = plugin.classify_source_file("src/main/java/com/example/UserService.java")
    assert result == "service"


# ---------------------------------------------------------------------------
# validation_command()
# ---------------------------------------------------------------------------

class TestValidationCommand:
    def test_returns_mvn_command_list(self, plugin, tmp_path):
        cmd = plugin.validation_command(tmp_path, {})
        assert isinstance(cmd, list)
        assert len(cmd) > 0
        # First element is the resolved mvn binary (case-insensitive for Windows compatibility)
        first = cmd[0].lower()
        assert first.endswith("mvn") or first.endswith("mvn.cmd")

    def test_contains_test_compile_goal(self, plugin, tmp_path):
        cmd = plugin.validation_command(tmp_path, {})
        assert "test-compile" in cmd

    def test_session_config_override_respected(self, plugin, tmp_path):
        session_config = {"maven_compile_cmd": "mvn test-compile -q -P corp"}
        cmd = plugin.validation_command(tmp_path, session_config)
        assert "-P" in cmd
        assert "corp" in cmd


# ---------------------------------------------------------------------------
# test_run_command()
# ---------------------------------------------------------------------------

class TestTestRunCommand:
    def test_returns_mvn_command_list(self, plugin, tmp_path):
        cmd = plugin.test_run_command(tmp_path, {})
        assert isinstance(cmd, list)
        assert "test" in cmd

    def test_session_config_override_respected(self, plugin, tmp_path):
        session_config = {"maven_test_cmd": "mvn test -q -P corp"}
        cmd = plugin.test_run_command(tmp_path, session_config)
        assert "-P" in cmd
        assert "corp" in cmd


# ---------------------------------------------------------------------------
# _detect_maven_build_config() — pom profiles + .mvn/maven.config
# ---------------------------------------------------------------------------

class TestDetectMavenBuildConfig:
    def test_defaults_without_config(self, tmp_path):
        from src.lib.plugins.java_spring import _detect_maven_build_config
        (tmp_path / "pom.xml").write_text("<project></project>")
        config = _detect_maven_build_config(tmp_path)
        assert "test-compile" in config["compile_cmd"]
        assert "mvn" in config["compile_cmd"]
        assert config["notes"] == [
            "No special profiles or Maven config detected — using default flags"
        ]

    def test_maven_config_flags_appended(self, tmp_path):
        from src.lib.plugins.java_spring import _detect_maven_build_config
        (tmp_path / "pom.xml").write_text("<project></project>")
        mvn_dir = tmp_path / ".mvn"
        mvn_dir.mkdir()
        (mvn_dir / "maven.config").write_text("-P corp-profile\n-DskipITs")
        config = _detect_maven_build_config(tmp_path)
        assert "-P corp-profile" in config["compile_cmd"]
        assert "-DskipITs" in config["compile_cmd"]
        assert config["notes"], "a note should document the extra flags"


class TestParseMavenCmd:
    def test_valid_command(self):
        from src.lib.plugins.java_spring import _parse_maven_cmd
        cmd = _parse_maven_cmd("mvn test-compile -q -P prof")
        assert cmd[0].endswith("mvn") or "mvn" in cmd[0]
        assert "-P" in cmd and "prof" in cmd

    def test_rejects_non_maven_binary(self):
        import pytest as _pytest

        from src.lib.plugins.java_spring import _parse_maven_cmd
        with _pytest.raises(ValueError):
            _parse_maven_cmd("rm -rf /")
