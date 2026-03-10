# SPDX-License-Identifier: Apache-2.0
"""Unit tests for testboost_lite.lib.installer."""

from pathlib import Path

import pytest

from testboost_lite.lib.installer import install_commands

TESTBOOST_ROOT = str(Path(__file__).parent.parent.parent.parent)


@pytest.fixture
def java_project(tmp_path):
    """Create a minimal Java project structure."""
    project = tmp_path / "my-java-app"
    project.mkdir()
    (project / "pom.xml").write_text("<project/>", encoding="utf-8")
    return project


class TestInstallCommands:
    def test_installs_claude_commands(self, java_project):
        result = install_commands(str(java_project), TESTBOOST_ROOT)
        assert result["success"] is True

        commands_dir = java_project / ".claude" / "commands"
        assert commands_dir.exists()
        assert (commands_dir / "testboost.init.md").exists()
        assert (commands_dir / "testboost.generate.md").exists()

    def test_installs_opencode_commands(self, java_project):
        result = install_commands(str(java_project), TESTBOOST_ROOT)
        assert result["success"] is True

        commands_dir = java_project / ".opencode" / "commands"
        assert commands_dir.exists()
        assert (commands_dir / "testboost.init.md").exists()

    def test_installs_wrapper_scripts(self, java_project):
        result = install_commands(str(java_project), TESTBOOST_ROOT)
        assert result["success"] is True

        scripts_dir = java_project / ".testboost" / "scripts"
        assert scripts_dir.exists()
        assert (scripts_dir / "tb-init.sh").exists()
        assert (scripts_dir / "tb-generate.sh").exists()

    def test_wrapper_scripts_have_absolute_paths(self, java_project):
        install_commands(str(java_project), TESTBOOST_ROOT)

        script = (java_project / ".testboost" / "scripts" / "tb-generate.sh").read_text()
        assert TESTBOOST_ROOT in script
        assert "TESTBOOST_ROOT=" in script

    def test_wrapper_scripts_are_executable(self, java_project):
        install_commands(str(java_project), TESTBOOST_ROOT)

        import os
        script = java_project / ".testboost" / "scripts" / "tb-generate.sh"
        assert os.access(script, os.X_OK)

    def test_commands_use_installed_script_paths(self, java_project):
        install_commands(str(java_project), TESTBOOST_ROOT)

        content = (java_project / ".claude" / "commands" / "testboost.generate.md").read_text()
        # Should reference .testboost/scripts/ not testboost_lite/scripts/
        assert "bash .testboost/scripts/tb-generate.sh" in content
        assert "bash testboost_lite/scripts/tb-generate.sh" not in content

    def test_creates_integrity_secret(self, java_project):
        install_commands(str(java_project), TESTBOOST_ROOT)
        assert (java_project / ".testboost" / ".tb_secret").exists()

    def test_nonexistent_project_fails(self, tmp_path):
        result = install_commands(str(tmp_path / "nonexistent"), TESTBOOST_ROOT)
        assert result["success"] is False

    def test_commands_have_failure_protocol(self, java_project):
        install_commands(str(java_project), TESTBOOST_ROOT)

        content = (java_project / ".claude" / "commands" / "testboost.generate.md").read_text()
        assert "CRITICAL: Failure Protocol" in content
        assert "TESTBOOST_INTEGRITY" in content
        assert "STOP IMMEDIATELY" in content

    def test_idempotent_install(self, java_project):
        result1 = install_commands(str(java_project), TESTBOOST_ROOT)
        result2 = install_commands(str(java_project), TESTBOOST_ROOT)
        assert result1["success"] is True
        assert result2["success"] is True
