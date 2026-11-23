# SPDX-License-Identifier: Apache-2.0
"""pom.xml parsing on REAL (namespaced) POMs.

Regression suite for the `find("m:x", ns) or find("x")` idiom: a found leaf
Element is falsy, so every real POM lost its java.version, activeByDefault
profiles and dependency flags.
"""

import asyncio
import json
import xml.etree.ElementTree as ET

import pytest

from src.java.pom import pom_child, pom_findall, pom_text
from src.lib.plugins.java_spring import _detect_maven_build_config
from src.test_generation.analyze import analyze_project_context
from src.test_generation.generate_unit import (
    _build_framework_instructions,
    _detect_test_dependencies,
    _extract_project_context,
)

NS = 'xmlns="http://maven.apache.org/POM/4.0.0"'


def _pom(body: str, namespaced: bool = True) -> str:
    return f"<project {NS if namespaced else ''}>{body}</project>"


SPRING_BOOT = """
  <parent><artifactId>spring-boot-starter-parent</artifactId><version>3.3.1</version></parent>
  <groupId>com.acme</groupId><artifactId>shop</artifactId><version>2.0</version>
  <properties><java.version>21</java.version></properties>
  <dependencies>
    <dependency><groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId><scope>test</scope></dependency>
  </dependencies>
  <profiles>
    <profile><id>corp</id><activation><activeByDefault>true</activeByDefault></activation></profile>
    <profile><id>ci</id><activation><activeByDefault>false</activeByDefault></activation></profile>
  </profiles>
"""


@pytest.fixture(autouse=True)
def _clear_caches():
    _detect_test_dependencies.cache_clear()
    _extract_project_context.cache_clear()


@pytest.mark.parametrize("namespaced", [True, False])
class TestPomHelpers:
    def test_leaf_children_are_found(self, namespaced):
        root = ET.fromstring(_pom(SPRING_BOOT, namespaced))
        assert pom_text(pom_child(root, "properties"), "java.version") == "21"
        assert pom_text(root, "artifactId") == "shop"
        assert [pom_text(p, "id") for p in pom_findall(root, "profile")] == ["corp", "ci"]

    def test_missing_parent_or_tag_is_none(self, namespaced):
        root = ET.fromstring(_pom("<properties/>", namespaced))
        assert pom_text(None, "x") is None
        assert pom_text(pom_child(root, "properties"), "java.version") is None


class TestConsumers:
    def test_active_by_default_profile_is_added_to_maven_commands(self, tmp_path):
        (tmp_path / "pom.xml").write_text(_pom(SPRING_BOOT))
        config = _detect_maven_build_config(tmp_path)
        assert config["compile_cmd"].endswith("-P corp")
        assert config["test_cmd"].endswith("-P corp")

    def test_invalid_profile_id_is_skipped_with_a_note(self, tmp_path):
        bad = '<profiles><profile><id>x;rm -rf</id><activation><activeByDefault>true' \
              '</activeByDefault></activation></profile></profiles>'
        (tmp_path / "pom.xml").write_text(_pom(bad))
        config = _detect_maven_build_config(tmp_path)
        assert "-P" not in config["compile_cmd"]
        assert any("invalid ID" in n for n in config["notes"])

    def test_analyze_reads_java_version_and_coordinates(self, tmp_path):
        (tmp_path / "pom.xml").write_text(_pom(SPRING_BOOT))
        result = json.loads(asyncio.run(analyze_project_context(str(tmp_path))))
        assert result["java_version"] == "21"
        assert result["module_info"] == {"groupId": "com.acme", "artifactId": "shop", "version": "2.0"}
        assert result["dependencies"][0]["artifactId"] == "spring-boot-starter-test"
        assert result["dependencies"][0]["version"] == "managed"

    def test_prompt_context_has_java_and_spring_boot_versions(self, tmp_path):
        (tmp_path / "pom.xml").write_text(_pom(SPRING_BOOT))
        context = _extract_project_context(str(tmp_path))
        assert "**Java version**: 21" in context
        assert "**Spring Boot version**: 3.3.1" in context
        assert "spring-boot-starter-test (managed)" in context

    def test_spring_boot_starter_test_provides_mockito_and_assertj(self, tmp_path):
        """The starter bundles JUnit 5 + Mockito + AssertJ: the prompt used to
        tell the LLM 'Mockito is NOT available' on every Spring Boot project."""
        (tmp_path / "pom.xml").write_text(_pom(SPRING_BOOT))
        deps = _detect_test_dependencies(str(tmp_path))
        assert deps["framework"] == "junit5"
        assert deps["has_mockito"] and deps["has_assertj"] and deps["has_spring_test"]
        text = _build_framework_instructions(deps)
        assert "Mockito is NOT available" not in text
        assert "ExtendWith(MockitoExtension" in text
