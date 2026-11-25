# SPDX-License-Identifier: Apache-2.0
"""templates/commands is the single source of the slash commands.

The repo keeps dev copies under .claude/ and .opencode/ (used when the LLM
CLI is launched from the TestBoost checkout). They had drifted: mutate and
killer existed for Claude Code only and were never installed in a project.
"""

from pathlib import Path

import pytest

from src.lib.installer import HELPER_SCRIPTS, _command_steps, install_commands

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ROOT / "templates" / "commands"
STEPS = _command_steps(ROOT)


def test_every_cli_command_has_a_template():
    assert set(STEPS) == {
        "init", "analyze", "gaps", "generate", "validate",
        "mutate", "killer", "status", "verify",
    }


@pytest.mark.parametrize("step", STEPS)
def test_dev_copies_match_the_template(step):
    template = (TEMPLATES / f"testboost.{step}.md").read_text()
    assert (ROOT / ".claude" / "commands" / f"testboost.{step}.md").read_text() == template
    opencode = (ROOT / ".opencode" / "commands" / f"testboost.{step}.md").read_text()
    assert "\n".join(ln for ln in opencode.splitlines() if not ln.startswith("argument-hint")) \
        == template.rstrip("\n")


@pytest.mark.parametrize("step", STEPS + list(HELPER_SCRIPTS))
def test_every_command_has_its_dev_wrapper_scripts(step):
    assert (ROOT / "scripts" / f"tb-{step}.sh").exists()
    assert (ROOT / "scripts" / f"tb-{step}.ps1").exists()


def test_install_ships_a_wrapper_for_every_command(tmp_path):
    result = install_commands(str(tmp_path), str(ROOT), "bash")
    assert result["success"]
    for step in [*STEPS, *HELPER_SCRIPTS]:
        assert (tmp_path / ".testboost" / "scripts" / f"tb-{step}.sh").exists(), step
    for step in STEPS:
        command = (tmp_path / ".claude" / "commands" / f"testboost.{step}.md").read_text()
        # commands call the installed wrapper, not the TestBoost checkout's scripts/
        assert "bash scripts/" not in command
