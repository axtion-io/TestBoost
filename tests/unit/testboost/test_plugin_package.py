# SPDX-License-Identifier: Apache-2.0
"""What ships to other tools stays consistent with the code: the Claude Code plugin
(skills → MCP tools that exist, .mcp.json → an installed script) and the slash-command
copies installed for Claude Code and OpenCode (identical to templates/commands)."""

import json
import re
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
PLUGIN = ROOT / "plugin"


def test_marketplace_points_at_the_plugin():
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    entry = market["plugins"][0]
    assert entry["name"] == manifest["name"] == "testboost"
    assert (ROOT / entry["source"]).resolve() == PLUGIN


def test_plugin_version_follows_the_package():
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["poetry"]
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    assert manifest["version"] == package["version"]


def test_mcp_server_command_is_an_installed_script():
    scripts = tomllib.loads((ROOT / "pyproject.toml").read_text())["tool"]["poetry"]["scripts"]
    server = json.loads((PLUGIN / ".mcp.json").read_text())["mcpServers"]["testboost"]
    assert server["args"][-1] in scripts
    assert "testboost[mcp]" in server["args"][1]


def test_skills_only_name_tools_the_server_has():
    mcp_server = pytest.importorskip("src.mcp_server")
    import asyncio
    tools = {t.name for t in asyncio.run(mcp_server.server.list_tools())}
    for skill in PLUGIN.glob("skills/*/SKILL.md"):
        text = skill.read_text()
        assert text.startswith("---\ndescription: "), skill
        named = set(re.findall(r"`([a-z_]+)`", text)) & (tools | {"register", "equivalent", "generate"})
        assert named <= tools, (skill.name, named - tools)


@pytest.mark.parametrize("copy_dir", [".claude/commands", ".opencode/commands"])
def test_installed_command_copies_match_the_templates(copy_dir):
    for template in sorted((ROOT / "templates/commands").glob("*.md")):
        copy = (ROOT / copy_dir / template.name).read_text().splitlines()
        if copy_dir == ".opencode/commands":                # OpenCode adds an argument-hint line
            copy = [ln for ln in copy if not ln.startswith("argument-hint:")]
        assert copy == template.read_text().splitlines(), f"{copy_dir}/{template.name} drifted"
