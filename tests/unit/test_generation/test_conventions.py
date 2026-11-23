# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.test_generation.conventions (test style detection)."""

import json
from pathlib import Path

import pytest

from src.test_generation.conventions import detect_test_conventions


def _make_java_project(tmp_path: Path) -> Path:
    (tmp_path / "pom.xml").write_text("<project></project>")
    tests_dir = tmp_path / "src/test/java/com/example"
    tests_dir.mkdir(parents=True)
    (tests_dir / "OrderServiceTest.java").write_text(
        """
package com.example;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.BeforeEach;
import org.mockito.Mock;
import static org.assertj.core.api.Assertions.assertThat;

class OrderServiceTest {
    @Mock OrderRepository repo;

    @BeforeEach
    void setUp() {}

    @Test
    void shouldComputeTotal() {
        assertThat(1 + 1).isEqualTo(2);
    }

    @Test
    void shouldRejectNegative() {
        assertThat(true).isTrue();
    }
}
"""
    )
    (tests_dir / "UserServiceTest.java").write_text(
        """
package com.example;
import org.junit.jupiter.api.Test;
import static org.assertj.core.api.Assertions.assertThat;

class UserServiceTest {
    @Test
    void shouldFindUser() {
        assertThat("x").isNotNull();
    }
}
"""
    )
    return tmp_path


class TestDetectTestConventions:
    @pytest.mark.asyncio
    async def test_nonexistent_path(self):
        result = json.loads(await detect_test_conventions("/nonexistent/xyz"))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_no_test_files(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = json.loads(await detect_test_conventions(str(tmp_path)))
        assert result["success"] is False
        assert "No test files" in result["error"]

    @pytest.mark.asyncio
    async def test_detects_naming_assertions_and_mocking(self, tmp_path):
        project = _make_java_project(tmp_path)
        result = json.loads(await detect_test_conventions(str(project)))
        assert result["success"] is True
        assert result["sample_size"] == 2
        # shouldXxx naming dominates (the case style is reported separately:
        # it used to win the "dominant pattern" vote on every project)
        assert result["naming"]["dominant_pattern"] == "should"
        assert result["naming"]["uses_snake_case"] is False
        assert any("should" in m for m in result["naming"]["sample_methods"])
        # assertj is the dominant assertion style
        assert result["assertions"]["dominant_style"] == "assertj"
        assert result["assertions"]["styles"]["assertj"] == 3
        # mockito usage detected (annotation style)
        assert result["mocking"]["uses_mockito"] is True
        assert result["mocking"]["prefers_annotations"] is True
        # @BeforeEach setup detected
        assert result["setup_patterns"]["uses_setup"] is True
        assert result["setup_patterns"]["patterns"]["before_each"] == 1


class TestConventionsReachThePrompt:
    """The generate prompt reads conventions["setup_patterns"]: the detector
    used to store them under "setup", so @Nested/@ParameterizedTest
    conventions never reached the LLM."""

    @pytest.mark.asyncio
    async def test_nested_and_parameterized_are_announced(self, tmp_path):
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, patch

        from src.test_generation.generate_unit import _generate_test_code_with_llm

        project = _make_java_project(tmp_path)
        (project / "src/test/java/com/example/MoreTest.java").write_text(
            "import org.junit.jupiter.api.Nested;\n@Nested class Inner {\n"
            "  @ParameterizedTest void given_x_when_y_then_z(int v) {}\n}\n"
        )
        conventions = json.loads(await detect_test_conventions(str(project)))

        llm = SimpleNamespace(ainvoke=AsyncMock(return_value=SimpleNamespace(
            content="class T { @Test void t() {} }")))
        context = {"class_name": "A", "package": "p", "class_type": "service", "methods": [],
                   "dependencies": [], "conventions": conventions, "project_path": ""}
        with patch("src.test_generation.generate_unit.get_llm", return_value=llm):
            await _generate_test_code_with_llm(context, "class A {}")
        prompt = llm.ainvoke.await_args.args[0]
        assert "**Uses @Nested classes**: yes" in prompt
        assert "**Uses @ParameterizedTest**: yes" in prompt
        assert "**Naming pattern**: should" in prompt


class TestStyleDetection:
    @pytest.mark.parametrize(("imports", "body", "style"), [
        ("import static org.hamcrest.MatcherAssert.assertThat;", "assertThat(a, is(b));", "hamcrest"),
        ("import static org.junit.jupiter.api.Assertions.*;", "assertEquals(1, x); assertTrue(y);", "junit_assertions"),
        ("import static com.google.common.truth.Truth.assertThat;", "assertThat(x).isTrue();", "truth"),
    ])
    @pytest.mark.asyncio
    async def test_dominant_assertion_style(self, tmp_path, imports, body, style):
        (tmp_path / "pom.xml").write_text("<project/>")
        test = tmp_path / "src/test/java/a/XTest.java"
        test.parent.mkdir(parents=True)
        test.write_text(f"{imports}\nclass XTest {{\n @Test\n void given_a_when_b_then_c() {{ {body} }}\n}}")
        result = json.loads(await detect_test_conventions(str(tmp_path)))
        assert result["assertions"]["dominant_style"] == style
        assert result["naming"]["dominant_pattern"] == "given_when_then"
        assert result["naming"]["uses_snake_case"] is True

    @pytest.mark.asyncio
    async def test_spring_mock_bean_and_inline_mocks(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        test = tmp_path / "src/test/java/a/WebTest.java"
        test.parent.mkdir(parents=True)
        test.write_text("class WebTest { @MockBean Svc s; Repo r = Mockito.mock(Repo.class); "
                        "@Test void testGet() { verify(r).find(); } }")
        mocking = json.loads(await detect_test_conventions(str(tmp_path)))["mocking"]
        assert mocking["uses_mockito"] is True
        assert mocking["uses_spring_mock_bean"] is True
        assert mocking["prefers_annotations"] is False
