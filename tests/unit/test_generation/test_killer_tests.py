# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.test_generation.killer_tests (LLM mocked)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.test_generation.killer_tests import (
    _get_kill_strategy,
    _get_killer_test_path,
    _sanitize_method_name,
    _to_camel_case,
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
    async def test_template_fallback_without_source(self, tmp_path):
        """No source file on disk → template-based generation, zero LLM calls."""
        with patch("src.test_generation.killer_tests._generate_killer_tests_llm",
                   new_callable=AsyncMock) as mock_llm:
            result = json.loads(await generate_killer_tests(
                str(tmp_path), [_mutant(), _mutant(method="applyDiscount", line=50)],
            ))
        mock_llm.assert_not_called()
        assert result["success"] is True
        assert len(result["generated_tests"]) == 1  # grouped by class
        test = result["generated_tests"][0]
        assert test["class"] == "com.example.OrderService"
        assert test["mutants_targeted"] == 2
        assert "@Test" in test["test_code"]
        assert "KillerTest" in test["test_file"]

    @pytest.mark.asyncio
    async def test_llm_path_with_source_and_hints(self, tmp_path):
        src = tmp_path / "src/main/java/com/example/OrderService.java"
        src.parent.mkdir(parents=True)
        src.write_text("package com.example;\npublic class OrderService {}")

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
        with patch("src.test_generation.killer_tests._generate_killer_tests_llm",
                   new_callable=AsyncMock):
            result = json.loads(await generate_killer_tests(
                str(tmp_path), mutants, max_tests=2,
            ))
        assert result["total_mutants_targeted"] == 2
        assert len(result["generated_tests"]) == 2


class TestKillerHelpers:
    def test_killer_test_path(self, tmp_path):
        path = _get_killer_test_path(tmp_path, "com.example.OrderService")
        assert path == tmp_path / "src/test/java/com/example/OrderServiceKillerTest.java"

    def test_kill_strategies_cover_known_mutators(self):
        for mutator, needle in [
            ("MATH", ""), ("ConditionalsBoundaryMutator", "boundary"),
            ("NegateConditionalsMutator", ""), ("VoidMethodCallMutator", ""),
            ("UnknownMutator", ""),
        ]:
            strategy = _get_kill_strategy(mutator, "desc")
            assert strategy["strategy"], mutator
            assert strategy["assert"], mutator
            if needle:
                assert needle in json.dumps(strategy).lower()

    def test_to_camel_case_lowercases_first_letter(self):
        assert _to_camel_case("CalculateTotal") == "calculateTotal"
        assert _to_camel_case("") == ""

    def test_sanitize_method_name(self):
        assert _sanitize_method_name("a-b c") == "abc"
        assert _sanitize_method_name("9lives").startswith("_")
        assert _sanitize_method_name("@@@") == "method"
