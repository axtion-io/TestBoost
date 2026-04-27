# SPDX-License-Identifier: Apache-2.0
"""Integration tests for PluginRegistry auto-detection.

These tests use real temp directories with real files — no mocks.
"""

import pytest
from pathlib import Path

from src.lib.plugins import get_registry


@pytest.fixture
def registry():
    return get_registry()


# ---------------------------------------------------------------------------
# Java / Maven project
# ---------------------------------------------------------------------------

def test_detect_java_maven_project(registry, tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "java-spring"


def test_detect_java_gradle_project(registry, tmp_path):
    (tmp_path / "build.gradle").write_text("plugins { id 'java' }")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "java-spring"


def test_detect_java_gradle_kts_project(registry, tmp_path):
    (tmp_path / "build.gradle.kts").write_text('plugins { java }')
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "java-spring"


# ---------------------------------------------------------------------------
# Python / pytest project
# ---------------------------------------------------------------------------

def test_detect_python_pyproject_project(registry, tmp_path):
    (tmp_path / "pyproject.toml").write_text("[build-system]")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "python-pytest"


def test_detect_python_setup_py_project(registry, tmp_path):
    (tmp_path / "setup.py").write_text("from setuptools import setup; setup()")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "python-pytest"


def test_detect_python_setup_cfg_project(registry, tmp_path):
    (tmp_path / "setup.cfg").write_text("[metadata]\nname = mypackage")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "python-pytest"


# ---------------------------------------------------------------------------
# Go project
# ---------------------------------------------------------------------------

def test_detect_go_project(registry, tmp_path):
    (tmp_path / "go.mod").write_text("module example.com/myapp\n\ngo 1.21\n")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "go-testing"


# ---------------------------------------------------------------------------
# Ambiguous project (Java wins due to registration priority)
# ---------------------------------------------------------------------------

def test_detect_polyglot_project_java_wins(registry, tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    (tmp_path / "pyproject.toml").write_text("[build-system]")
    plugin = registry.detect(tmp_path)
    assert plugin is not None
    assert plugin.identifier == "java-spring"


# ---------------------------------------------------------------------------
# Unknown project
# ---------------------------------------------------------------------------

def test_detect_empty_directory_returns_none(registry, tmp_path):
    plugin = registry.detect(tmp_path)
    assert plugin is None


def test_detect_unknown_project_returns_none(registry, tmp_path):
    (tmp_path / "Makefile").write_text("build:\n\tmake all")
    plugin = registry.detect(tmp_path)
    assert plugin is None


# ---------------------------------------------------------------------------
# Registry get() and list_plugins()
# ---------------------------------------------------------------------------

def test_get_java_spring_plugin(registry):
    plugin = registry.get("java-spring")
    assert plugin.identifier == "java-spring"


def test_get_python_pytest_plugin(registry):
    plugin = registry.get("python-pytest")
    assert plugin.identifier == "python-pytest"


def test_get_go_testing_plugin(registry):
    plugin = registry.get("go-testing")
    assert plugin.identifier == "go-testing"


def test_list_plugins_includes_all_three(registry):
    identifiers = {p["identifier"] for p in registry.list_plugins()}
    assert "java-spring" in identifiers
    assert "python-pytest" in identifiers
    assert "go-testing" in identifiers
