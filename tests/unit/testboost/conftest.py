# SPDX-License-Identifier: Apache-2.0
"""Shared fixtures for the testboost CLI test suite."""

import argparse

import pytest

from src.lib.cli import cmd_init


@pytest.fixture
def initialized_project(java_project):
    """A Java project with testboost initialized."""
    args = argparse.Namespace(project_path=str(java_project), name=None, description="")
    cmd_init(args)
    return java_project
