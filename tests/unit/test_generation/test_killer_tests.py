# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.test_generation.killer_tests (LLM mocked)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.test_generation.killer_tests import (
    _find_source_file,
    _generate_killer_tests_llm,
    _get_killer_test_path,
    generate_killer_tests,
)


def _mutant(cls="com.example.OrderService", method="calculateTotal",
            mutator="MATH", line=42, description="Replaced + with -"):
    return {"class": cls, "method": method, "mutator": mutator,
            "line": line, "description": description}


class TestGenerateKillerTests:
    @pytest.mark.asyncio
    async def test_nonexistent_project(self):
        result = json.loads(await generate_killer_tests("/nonexistent/xyz", [_mutant()]))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_mutants(self, tmp_path):
        result = json.loads(await generate_killer_tests(str(tmp_path), []))
        assert result["success"] is False
        assert "No surviving mutants" in result["error"]

    @pytest.mark.asyncio
    async def test_class_without_source_is_skipped_not_templated(self, tmp_path):
        """No source on disk → skipped. The former template fallback wrote
        `isEqualTo(/* expected */)` placeholders that broke compilation of
        the whole test suite."""
        with patch("src.test_generation.killer_tests._generate_killer_tests_llm",
                   new_callable=AsyncMock) as mock_llm:
            result = json.loads(await generate_killer_tests(
                str(tmp_path), [_mutant(), _mutant(method="applyDiscount", line=50)],
            ))
        mock_llm.assert_not_called()
        assert result["success"] is True
        assert result["generated_tests"] == []
        assert result["skipped"] == [
            {"class": "com.example.OrderService", "reason": "source file not found"}
        ]

    @pytest.mark.asyncio
    async def test_llm_answer_without_test_is_skipped(self, tmp_path):
        _write_source(tmp_path, "src/main/java/com/example/OrderService.java")
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content="Sorry, I cannot help.")
        with patch("src.test_generation.killer_tests.get_llm", return_value=llm):
            result = json.loads(await generate_killer_tests(str(tmp_path), [_mutant()]))
        assert result["generated_tests"] == []
        assert result["skipped"][0]["reason"] == "LLM returned no @Test method"

    @pytest.mark.asyncio
    async def test_class_name_from_pit_cannot_escape_the_project(self, tmp_path):
        with patch("src.test_generation.killer_tests._generate_killer_tests_llm",
                   new_callable=AsyncMock) as mock_llm:
            result = json.loads(await generate_killer_tests(
                str(tmp_path), [_mutant(cls="../../etc/passwd")],
            ))
        mock_llm.assert_not_called()
        assert result["skipped"][0]["reason"] == "invalid class name"

    @pytest.mark.asyncio
    async def test_llm_path_with_source_and_hints(self, tmp_path):
        _write_source(tmp_path, "src/main/java/com/example/OrderService.java")

        captured = {}
        async def fake_llm(class_name, mutants, source_code, hints=None):
            captured["hints"] = hints
            captured["class_name"] = class_name
            return "import org.junit.jupiter.api.Test;\nclass K { @Test void k() {} }"

        with patch("src.test_generation.killer_tests._generate_killer_tests_llm",
                   new=AsyncMock(side_effect=fake_llm)):
            result = json.loads(await generate_killer_tests(
                str(tmp_path), [_mutant()],
                hints={"OrderService.calculateTotal": "round half-up",
                       "OtherClass.x": "irrelevant"},
            ))

        assert result["success"] is True
        # Only the hints matching the class are forwarded
        assert captured["hints"] == {"OrderService.calculateTotal": "round half-up"}

    @pytest.mark.asyncio
    async def test_max_tests_caps_mutants(self, tmp_path):
        mutants = [_mutant(cls=f"com.example.C{i}") for i in range(5)]
        for i in range(5):
            _write_source(tmp_path, f"src/main/java/com/example/C{i}.java")
        with patch("src.test_generation.killer_tests._generate_killer_tests_llm",
                   new=AsyncMock(return_value="class K { @Test void k() {} }")):
            result = json.loads(await generate_killer_tests(
                str(tmp_path), mutants, max_tests=2,
            ))
        assert result["total_mutants_targeted"] == 2
        assert len(result["generated_tests"]) == 2


class TestKillerHelpers:
    def test_killer_test_path(self, tmp_path):
        path = _get_killer_test_path(tmp_path, "com.example.OrderService")
        assert path == tmp_path / "src/test/java/com/example/OrderServiceKillerTest.java"

    def test_multi_module_source_and_test_stay_in_their_module(self, tmp_path):
        src = _write_source(tmp_path, "billing/src/main/java/com/example/OrderService.java")
        found = _find_source_file(tmp_path, "com.example.OrderService$Line")
        assert found == src
        assert _get_killer_test_path(tmp_path, "com.example.OrderService$Line", found) == (
            tmp_path / "billing/src/test/java/com/example/OrderServiceKillerTest.java"
        )

    @pytest.mark.asyncio
    async def test_llm_prompt_carries_mutants_source_and_hints(self):
        llm = AsyncMock()
        llm.ainvoke.return_value = AsyncMock(content="```java\nclass K { @Test void k() {} }\n```")
        with patch("src.test_generation.killer_tests.get_llm", return_value=llm):
            code = await _generate_killer_tests_llm(
                "com.example.OrderService", [_mutant()], "class OrderService {}",
                hints={"OrderService.calculateTotal": "round half-up"},
            )
        assert code == "class K { @Test void k() {} }"
        prompt = llm.ainvoke.await_args.args[0]
        assert "Replaced + with -" in prompt
        assert "class OrderService {}" in prompt
        assert "round half-up" in prompt


def _write_source(root, rel):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("package com.example;\npublic class X {}")
    return path
