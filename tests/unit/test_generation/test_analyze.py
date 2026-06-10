# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.test_generation.analyze (pure filesystem analysis)."""

import json
import shutil
from pathlib import Path

import pytest

from src.test_generation.analyze import analyze_project_context

FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "java-sample-project"


@pytest.fixture
def java_project(tmp_path):
    dest = tmp_path / "java-project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


class TestAnalyzeProjectContext:
    @pytest.mark.asyncio
    async def test_nonexistent_path(self):
        result = json.loads(await analyze_project_context("/nonexistent/xyz"))
        assert result["success"] is False
        assert "does not exist" in result["error"]

    @pytest.mark.asyncio
    async def test_maven_spring_project(self, java_project):
        result = json.loads(await analyze_project_context(str(java_project)))
        assert result["success"] is True
        assert result["build_system"] == "maven"
        # The fixture is a Spring project: detected from imports
        assert "spring" in " ".join(result["frameworks"]).lower() or result["project_type"] in ("spring-boot", "java-spring")
        assert result["source_structure"]["class_count"] >= 5
        assert result["test_structure"]["test_count"] >= 1
        assert result["dependencies"], "pom dependencies should be parsed"

    @pytest.mark.asyncio
    async def test_gradle_project_detected(self, tmp_path):
        (tmp_path / "build.gradle").write_text(
            "plugins { id 'java' }\ndependencies { testImplementation 'org.junit.jupiter:junit-jupiter:5.9.0' }\n"
        )
        (tmp_path / "src/main/java/com/x").mkdir(parents=True)
        (tmp_path / "src/main/java/com/x/A.java").write_text("package com.x;\npublic class A {}")
        result = json.loads(await analyze_project_context(str(tmp_path)))
        assert result["success"] is True
        assert result["build_system"] == "gradle"

    @pytest.mark.asyncio
    async def test_project_without_build_file(self, tmp_path):
        (tmp_path / "README.md").write_text("hello")
        result = json.loads(await analyze_project_context(str(tmp_path)))
        assert result["success"] is True
        assert result["build_system"] == "unknown"
