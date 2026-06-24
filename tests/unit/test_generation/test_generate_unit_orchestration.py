# SPDX-License-Identifier: Apache-2.0
"""Tests for generate_unit's orchestration entry points (LLM mocked)."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.test_generation.generate_unit import (
    analyze_edge_cases,
    fix_compilation_errors,
    generate_adaptive_tests,
)

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "java-sample-project"

JAVA_TEST = (
    "package com.example.service;\n"
    "import org.junit.jupiter.api.Test;\n"
    "class OrderServiceTest {\n  @Test\n  void shouldWork() {}\n  @Test\n  void shouldAlsoWork() {}\n}"
)


@pytest.fixture
def java_project(tmp_path):
    dest = tmp_path / "java-project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


def _llm_returning(text):
    llm = SimpleNamespace()
    llm.ainvoke = AsyncMock(return_value=SimpleNamespace(content=text))
    return llm


class TestGenerateAdaptiveTests:
    @pytest.mark.asyncio
    async def test_source_not_found(self, java_project):
        result = json.loads(await generate_adaptive_tests(
            str(java_project), "src/main/java/com/example/Nope.java",
        ))
        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_full_generation_flow(self, java_project):
        """Relative source path resolved, class analyzed, context assembled,
        LLM output wrapped in the result JSON."""
        with patch("src.test_generation.generate_unit._generate_test_code_with_llm",
                   new=AsyncMock(return_value=JAVA_TEST)) as mock_gen:
            result = json.loads(await generate_adaptive_tests(
                str(java_project),
                "src/main/java/com/example/service/OrderService.java",
                conventions={"naming": {"dominant_pattern": "camelCase"}},
            ))

        assert result["success"] is True
        assert result["test_code"] == JAVA_TEST
        assert result["test_count"] == 2
        assert result["class_type"] == "service"
        assert result["test_file"].endswith("src/test/java/com/example/service/OrderServiceTest.java")
        # The context handed to the LLM holds the analyzed class
        context = mock_gen.call_args.args[0]
        assert context["class_name"] == "OrderService"
        assert context["package"] == "com.example.service"
        assert context["methods"], "public methods should be in the context"


class TestFixCompilationErrors:
    @pytest.mark.asyncio
    async def test_strips_java_fences(self):
        with patch("src.test_generation.generate_unit.get_llm",
                   return_value=_llm_returning("```java\nclass Fixed {}\n```")):
            fixed = await fix_compilation_errors("class Broken {}", "[ERROR] x", "Broken")
        assert fixed == "class Fixed {}"

    @pytest.mark.asyncio
    async def test_plain_response_kept(self):
        with patch("src.test_generation.generate_unit.get_llm",
                   return_value=_llm_returning("class Fixed {}")):
            fixed = await fix_compilation_errors("class Broken2 {}", "[ERROR] y", "Broken2")
        assert fixed == "class Fixed {}"


class TestAnalyzeEdgeCases:
    @pytest.mark.asyncio
    async def test_parses_fenced_json_list(self):
        scenarios = [{"method": "transfer", "scenario": "negative amount",
                      "expected_behavior": "throws"}]
        with patch("src.test_generation.generate_unit.get_llm",
                   return_value=_llm_returning(f"```json\n{json.dumps(scenarios)}\n```")):
            result = await analyze_edge_cases("class A {}", "A", "service")
        assert result == scenarios

    @pytest.mark.asyncio
    async def test_invalid_json_returns_empty(self):
        with patch("src.test_generation.generate_unit.get_llm",
                   return_value=_llm_returning("not json at all")):
            result = await analyze_edge_cases("class A {}", "A", "service")
        assert result == []

    @pytest.mark.asyncio
    async def test_non_list_json_returns_empty(self):
        with patch("src.test_generation.generate_unit.get_llm",
                   return_value=_llm_returning('{"oops": true}')):
            result = await analyze_edge_cases("class A {}", "A", "service")
        assert result == []
