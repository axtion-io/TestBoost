"""Shared fixtures for TestBoost tests (markers are declared in pyproject.toml)."""

import shutil
from pathlib import Path

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "java-sample-project"


@pytest.fixture
def java_project(tmp_path):
    """A fresh copy of the Spring Boot sample project."""
    dest = tmp_path / "java-project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


@pytest.fixture
def initialized_project(java_project):
    """The sample project with `testboost init` done."""
    import argparse

    from src.lib.cli import cmd_init

    cmd_init(argparse.Namespace(project_path=str(java_project), name=None, description=""))
    return java_project
