# SPDX-License-Identifier: Apache-2.0
"""init → analyze → gaps → generate on the real sample project.

Unlike the CLI unit suite, NOTHING in TestBoost is mocked here: only the two
external processes are faked — the LLM (`get_llm`) and Maven
(`subprocess.run`). docs/mvp-plan.md: "tests green ≠ feature works" when
every test mocks the seam (here: the bridge) where integration breaks.
"""

import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async, _cmd_generate_async, cmd_init
from src.lib.commands._shared import _extract_json_field
from src.lib.session_tracker import get_current_session, read_project_analysis_data

SERVICE = "src/main/java/com/example/service/OrderService.java"


def _args(project, **kw):
    return argparse.Namespace(project_path=str(project), verbose=False, **kw)


class _FakeLLM:
    """Edge-case analysis gets JSON scenarios, generation gets a JUnit class."""

    def __init__(self):
        self.prompts: list[str] = []

    async def ainvoke(self, prompt):
        self.prompts.append(str(prompt))
        if "edge case" in str(prompt).lower() and "JSON" in str(prompt):
            return SimpleNamespace(content=json.dumps([
                {"method": "createOrder", "scenario": "null user", "expected_behavior": "throws"},
            ]))
        return SimpleNamespace(content=(
            "```java\npackage com.example.service;\nimport org.junit.jupiter.api.Test;\n"
            "class OrderServiceTest {\n  @Test\n  void createsOrder() {}\n}\n```"
        ))


@pytest.fixture
def analyzed(java_project):
    cmd_init(argparse.Namespace(project_path=str(java_project), name=None, description="", tech=None))
    import asyncio
    assert asyncio.run(_cmd_analyze_async(_args(java_project))) == 0
    assert asyncio.run(_cmd_gaps_async(_args(java_project))) == 0
    return java_project


def test_analyze_builds_the_project_level_context(analyzed):
    data = read_project_analysis_data(str(analyzed))
    assert data["project_context"]["java_version"] == "17"
    assert SERVICE in data["source_files"]
    # class index: exact dependency field types for the prompt
    order_service = data["class_index"]["OrderService"]
    assert order_service["package"] == "com.example.service"
    assert any(f["type"] == "OrderRepository" for f in order_service["fields"])
    # style examples come from the project's own tests
    assert any("UserServiceTest" in ex["path"] for ex in data["test_examples"])
    assert data["maven_compile_cmd"].startswith("mvn test-compile")


def test_gaps_agrees_with_analyze(analyzed):
    session_dir = Path(get_current_session(str(analyzed))["session_dir"])
    gaps_md = (session_dir / "coverage-gaps.md").read_text()
    gaps = _extract_json_field(gaps_md, "gaps")
    covered = _extract_json_field(gaps_md, "covered")
    assert covered == ["src/main/java/com/example/service/UserService.java"]
    assert SERVICE in gaps
    details = {d["path"]: d["has_test"] for d in read_project_analysis_data(str(analyzed))["source_file_details"]}
    assert {p for p, has in details.items() if has} == set(covered)


@pytest.mark.asyncio
async def test_generate_writes_a_compiled_test_with_project_context(analyzed):
    llm = _FakeLLM()
    compiled = MagicMock(returncode=0, stdout="", stderr="")
    with patch("src.test_generation.generate_unit.get_llm", return_value=llm), \
         patch("src.lib.startup_checks.check_llm_connection", new=AsyncMock()), \
         patch("subprocess.run", return_value=compiled) as mvn:
        rc = await _cmd_generate_async(_args(analyzed, files=[SERVICE], no_runtime_fix=False))

    assert rc == 0
    test_file = analyzed / "src/test/java/com/example/service/OrderServiceTest.java"
    assert "createsOrder" in test_file.read_text()
    generation_prompt = llm.prompts[-1]
    assert "null user" in generation_prompt              # edge case → requirements
    assert "OrderRepository" in generation_prompt        # class-index signatures
    assert "UserServiceTest" in generation_prompt        # project style example
    commands = [c.args[0] for c in mvn.call_args_list]
    assert any("test-compile" in cmd for cmd in commands)
    assert any("-Dtest=OrderService" in cmd for cmd in commands)  # runtime check
