# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.java.discovery (source finding and classification)."""

import shutil
from pathlib import Path

import pytest

from src.java.discovery import classify_source_file, find_existing_test, find_source_files

FIXTURE_DIR = Path(__file__).parent.parent.parent.parent / "fixtures" / "java-sample-project"


@pytest.fixture
def java_project(tmp_path):
    dest = tmp_path / "java-project"
    shutil.copytree(FIXTURE_DIR, dest)
    return dest


class TestFindSourceFiles:
    def test_finds_main_sources_not_tests(self, java_project):
        files = find_source_files(str(java_project))
        assert files, "fixture has source files"
        assert all("src/test" not in f.replace("\\", "/") for f in files)
        names = {Path(f).name for f in files}
        assert "UserService.java" in names
        assert "UserServiceTest.java" not in names

    def test_sorted_and_relative(self, java_project):
        files = find_source_files(str(java_project))
        assert files == sorted(files)
        assert all(not Path(f).is_absolute() for f in files)

    def test_empty_project(self, tmp_path):
        assert find_source_files(str(tmp_path)) == []


class TestClassifySourceFile:
    def test_categories(self):
        cases = [
            ("src/main/java/com/x/web/UserController.java", "controller"),
            ("src/main/java/com/x/service/UserService.java", "service"),
            ("src/main/java/com/x/repository/UserRepository.java", "repository"),
        ]
        for path, expected in cases:
            assert classify_source_file(path) == expected, path


class TestFindExistingTest:
    def test_finds_matching_test(self, java_project):
        result = find_existing_test(
            str(java_project), "src/main/java/com/example/service/UserService.java"
        )
        assert result is not None
        assert "UserServiceTest.java" in result

    def test_none_when_no_test(self, java_project):
        result = find_existing_test(
            str(java_project), "src/main/java/com/example/service/OrderService.java"
        )
        assert result is None
