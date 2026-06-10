# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the testboost CLI test suite."""

import argparse
import shutil
from pathlib import Path

import pytest

from src.lib.cli import cmd_init

# Path to the Java sample project fixture
FIXTURE_DIR = Path(__file__).parent.parent.parent / "fixtures" / "java-sample-project"


@pytest.fixture
def java_project(tmp_path):
    """Copy the Java sample project fixture to a temp directory."""
    dest = tmp_path / "java-project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


@pytest.fixture
def initialized_project(java_project):
    """A Java project with testboost initialized."""
    args = argparse.Namespace(project_path=str(java_project), name=None, description="")
    cmd_init(args)
    return java_project
