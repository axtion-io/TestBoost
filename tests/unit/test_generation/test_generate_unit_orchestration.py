# SPDX-License-Identifier: Apache-2.0
"""Tests for generate_unit's orchestration entry points (LLM mocked)."""

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.test_generation.generate_unit import (
    _detect_test_dependencies,
    _generate_test_code_with_llm,
    analyze_edge_cases,
    fix_compilation_errors,
    fix_test_runtime_errors,
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
        assert result["class_type"] == "service"
        # Only what generate consumes is returned (where to write is the plugin's call)
        assert result["context"] == {"class_name": "OrderService", "package": "com.example.service"}
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


def _context(project_path="", **overrides):
    context = {
        "class_name": "OrderService", "package": "com.example.service",
        "class_type": "service", "methods": [{"name": "total", "return_type": "BigDecimal"}],
        "dependencies": [{"type": "OrderRepository", "name": "repo"}],
        "conventions": {}, "test_requirements": [], "project_path": project_path,
        "class_index": None, "test_examples": None,
    }
    context.update(overrides)
    return context


class TestPromptAssembly:
    """docs/workflow.md (Generate): the prompt carries the dependency
    signatures from the class index, the parent class, the project test
    examples, the detected conventions and the technology's template."""

    @pytest.fixture(autouse=True)
    def _clear(self):
        _detect_test_dependencies.cache_clear()

    async def _prompt(self, context, response=JAVA_TEST, **kwargs):
        llm = _llm_returning(response)
        with patch("src.test_generation.generate_unit.get_llm", return_value=llm):
            code = await _generate_test_code_with_llm(context, "class OrderService {}", **kwargs)
        return code, llm.ainvoke.await_args.args[0]

    @pytest.mark.asyncio
    async def test_class_index_context_reaches_the_prompt(self, java_project):
        index = {
            "OrderService": {"extends": "BaseService"},
            "BaseService": {"public_signatures": "  - void audit(String who)", "fields": []},
            "OrderRepository": {
                "fields": [{"type": "BigDecimal", "name": "amount"}],
                "public_signatures": "  - Order save(Order order)",
            },
        }
        examples = [{"path": "src/test/java/FooTest.java", "content": "class FooTest {}"}]
        conventions = {"naming": {"dominant_pattern": "should_when"},
                       "assertions": {"dominant_style": "hamcrest"}}
        _code, prompt = await self._prompt(_context(
            str(java_project), class_index=index, test_examples=examples,
            conventions=conventions, test_requirements=[{"scenario": "negative total"}],
        ))
        assert "Order save(Order order)" in prompt            # dependency signatures
        assert "`BigDecimal amount`" in prompt               # exact field types
        assert "Parent Class `BaseService`" in prompt         # inheritance
        assert "void audit(String who)" in prompt
        assert "class FooTest {}" in prompt                   # project test example
        assert "should_when" in prompt and "hamcrest" in prompt  # conventions
        assert "negative total" in prompt                     # requirements
        assert "**Java version**: 17" in prompt               # pom context

    @pytest.mark.asyncio
    async def test_plugin_template_and_python_fences(self, tmp_path):
        with patch("src.test_generation.generate_unit.load_prompt_template",
                   return_value="{{class_name}}") as load:
            code, _prompt = await self._prompt(
                _context(), response="```python\ndef test_total():\n    assert 1\n```",
                prompt_template_dir="testing/python_pytest",
            )
        load.assert_called_once_with("testing/python_pytest/unit_test_generation.md")
        assert code == "def test_total():\n    assert 1"

    @pytest.mark.asyncio
    async def test_output_without_any_test_is_an_error_not_a_template(self):
        """CRITICAL: no silent fallback — a non-test answer must fail loudly."""
        with pytest.raises(ValueError, match="invalid test code"):
            await self._prompt(_context(), response="I cannot write this test.")

    @pytest.mark.asyncio
    async def test_controller_gets_webmvc_instructions(self):
        _code, prompt = await self._prompt(_context(class_type="controller"))
        assert "@WebMvcTest(OrderService.class)" in prompt


class TestFixTestRuntimeErrors:
    @pytest.mark.asyncio
    async def test_prompt_has_failures_and_code_and_fence_is_stripped(self):
        llm = _llm_returning("```java\nclass Fixed {}\n```")
        with patch("src.test_generation.generate_unit.get_llm", return_value=llm):
            fixed = await fix_test_runtime_errors("class Broken {}", "expected:<1> but was:<2>", "X")
        assert fixed == "class Fixed {}"
        prompt = llm.ainvoke.await_args.args[0]
        assert "expected:<1> but was:<2>" in prompt and "class Broken {}" in prompt
