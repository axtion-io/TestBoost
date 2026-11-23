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


def _java(root, rel, body):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


class TestMultiModuleAndFrameworks:
    @pytest.mark.asyncio
    async def test_multi_module_sources_tests_and_frameworks(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        for module in ("api", "core"):
            (tmp_path / module).mkdir()
            (tmp_path / module / "pom.xml").write_text("<project/>")
        _java(tmp_path, "api/src/main/java/a/Resource.java",
              "package a;\nimport jakarta.ws.rs.GET;\nimport io.quarkus.runtime.Startup;\nclass Resource {}")
        _java(tmp_path, "core/src/main/java/c/Repo.java",
              "package c;\nimport jakarta.persistence.Entity;\nimport org.hibernate.Session;\nclass Repo {}")
        _java(tmp_path, "core/src/test/java/c/RepoTest.java",
              "package c;\nimport org.junit.jupiter.api.Test;\nimport org.testcontainers.Testcontainers;\n"
              "import static org.assertj.core.api.Assertions.*;\n@DataJpaTest class RepoTest {}")

        result = json.loads(await analyze_project_context(str(tmp_path)))

        assert result["source_structure"]["class_count"] == 2
        assert result["source_structure"]["packages"] == ["a", "c"]
        assert result["test_structure"] == {
            "test_sources": [str(tmp_path / "core/src/test/java")],
            "test_count": 1, "test_packages": ["c"],
        }
        assert result["frameworks"] == ["hibernate", "jax-rs", "jpa", "quarkus"]
        assert result["project_type"] == "quarkus"
        assert result["test_frameworks"] == ["assertj", "junit5", "spring-test-slices", "testcontainers"]

    @pytest.mark.asyncio
    async def test_gradle_java_version(self, tmp_path):
        (tmp_path / "build.gradle").write_text("sourceCompatibility = '21'\n")
        result = json.loads(await analyze_project_context(str(tmp_path)))
        assert result["java_version"] == "21"

    @pytest.mark.asyncio
    async def test_spring_boot_application_type(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project/>")
        _java(tmp_path, "src/main/java/a/App.java",
              "package a;\nimport org.springframework.boot.SpringApplication;\n@SpringBootApplication class App {}")
        _java(tmp_path, "src/test/java/a/AppTest.java", "import org.junit.Test;\nclass AppTest {}")
        result = json.loads(await analyze_project_context(str(tmp_path)))
        assert result["project_type"] == "spring-boot"
        assert result["test_frameworks"] == ["junit4"]

    @pytest.mark.asyncio
    async def test_malformed_pom_is_reported_not_fatal(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project><unclosed>")
        result = json.loads(await analyze_project_context(str(tmp_path)))
        assert result["success"] is True
        assert "pom_parse_error" in result
