# SPDX-License-Identifier: Apache-2.0
"""TestBoost over MCP: the host agent (Claude Code, Cursor…) calls the same commands
as the CLI, through the real protocol, and no tool needs an LLM key."""

import sys

import pytest

mcp = pytest.importorskip("mcp")

from mcp import ClientSession  # noqa: E402
from mcp.client.stdio import StdioServerParameters, stdio_client  # noqa: E402

from src import mcp_server  # noqa: E402

AGENT_LOOP = {"init", "analyze", "gaps", "context", "register_tests", "validate", "mutate",
              "register_killer_tests", "declare_equivalent", "check", "pit_setup", "status"}


async def _session_call(*calls):
    params = StdioServerParameters(command=sys.executable, args=["-m", "src.mcp_server"],
                                   env={"TESTBOOST_LLM_PROVIDER": "none"})
    async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
        await session.initialize()
        return [await call(session) for call in calls]


@pytest.mark.asyncio
async def test_real_protocol_lists_the_agent_loop_and_runs_a_command(java_project):
    tools, result = await _session_call(
        lambda s: s.list_tools(),
        lambda s: s.call_tool("init", {"project_path": str(java_project)}),
    )
    assert {t.name for t in tools.tools} == AGENT_LOOP
    text = result.content[0].text
    assert text.startswith("exit 0 (ok)") and "[TESTBOOST_METRICS" not in text
    assert (java_project / ".testboost" / "sessions").is_dir()       # the CLI really ran


@pytest.mark.asyncio
async def test_arguments_become_cli_flags(monkeypatch, tmp_path):
    seen = []

    async def fake(*args):
        seen.append(args)
        return 1, "below threshold"
    monkeypatch.setattr(mcp_server, "run_cli", fake)
    out = await mcp_server.check(str(tmp_path), base="origin/main", min_mutation=70, mutation=False)
    assert seen == [("check", str(tmp_path), "--min-coverage", "80.0", "--min-mutation", "70",
                     "--base", "origin/main", "--no-mutation")]
    await mcp_server.check(str(tmp_path), classes=["a.B"], target_tests=["a.BTest"])
    assert seen[-1][-4:] == ("--classes", "a.B", "--target-tests", "a.BTest")
    assert out.startswith("exit 1 (failed / below threshold)")

    await mcp_server.declare_equivalent(str(tmp_path), ["abc", "def"], "the list is always sorted")
    assert seen[-1] == ("equivalent", str(tmp_path), "abc", "def", "--reason", "the list is always sorted")


@pytest.mark.asyncio
async def test_a_missing_project_is_refused_before_running(monkeypatch, tmp_path):
    monkeypatch.setattr(mcp_server, "run_cli", lambda *a: pytest.fail("must not run"))
    with pytest.raises(ValueError, match="not a directory"):
        await mcp_server.status(str(tmp_path / "nope"))


@pytest.mark.asyncio
async def test_timeout_kills_the_command(monkeypatch):
    monkeypatch.setenv("TESTBOOST_MCP_TIMEOUT", "0.01")
    code, text = await mcp_server.run_cli("doctor", "--help")
    assert code == 124 and "TESTBOOST_MCP_TIMEOUT" in text
