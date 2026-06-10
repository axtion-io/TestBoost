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
        # camelCase naming dominates and should-methods are sampled
        assert result["naming"]["dominant_pattern"] == "camelCase"
        assert any("should" in m for m in result["naming"]["sample_methods"])
        # assertj is the dominant assertion style
        assert result["assertions"]["dominant_style"] == "assertj"
        assert result["assertions"]["styles"]["assertj"] == 3
        # mockito usage detected (annotation style)
        assert result["mocking"]["uses_mockito"] is True
        assert result["mocking"]["prefers_annotations"] is True
        # @BeforeEach setup detected
        assert result["setup"]["uses_setup"] is True
        assert result["setup"]["patterns"]["before_each"] == 1
