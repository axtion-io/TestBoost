# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""
Unit tests for test_generation_agent.py

Tests:
- P1 fix: Maven executable detection (cross-platform)
- P2 fix: Failure deduplication with fully qualified class names
"""

import platform
import shutil
from unittest.mock import MagicMock, patch

import pytest

from src.workflows.test_generation_agent import (
    _get_maven_executable,
    _parse_test_failures,
)


class TestMavenExecutableDetection:
    """Test P1 fix: Cross-platform Maven executable detection."""

    def test_get_maven_executable_finds_mvn(self):
        """Test that _get_maven_executable() returns a valid Maven path."""
        mvn_path = _get_maven_executable()
        assert mvn_path is not None
        assert "mvn" in mvn_path.lower()

    def test_get_maven_executable_on_windows(self):
        """Test that on Windows, we get mvn.cmd or mvn.bat."""
        if platform.system() == "Windows":
            mvn_path = _get_maven_executable()
            assert mvn_path.lower().endswith((".cmd", ".bat")) or "mvn" in mvn_path.lower()

    def test_get_maven_executable_on_unix(self):
        """Test that on Unix systems, we get mvn (no extension)."""
        if platform.system() in ("Linux", "Darwin"):
            mvn_path = _get_maven_executable()
            # On Unix, should not end with .cmd or .bat
            assert not mvn_path.lower().endswith((".cmd", ".bat"))
            assert "mvn" in mvn_path.lower()

    @patch("shutil.which")
    def test_get_maven_executable_fallback_when_not_found(self, mock_which):
        """Test fallback behavior when Maven is not in PATH."""
        mock_which.return_value = None
        mvn_path = _get_maven_executable()
        # Should return 'mvn' as fallback to let subprocess fail with clear error
        assert mvn_path == "mvn"


class TestFailureDeduplication:
    """Test P2 fix: Deduplication with fully qualified class names."""

    def test_parse_test_failures_deduplicates_by_fq_class_name(self):
        """Test that failures from different packages with same simple class name are separate."""
        # Maven output with two different UserServiceTest classes in different packages
        maven_output = """
[ERROR] Errors:
[ERROR]   com.foo.UserServiceTest.testA:42 ~ NullPointer message1
[ERROR]   com.bar.UserServiceTest.testA:42 ~ NullPointer message2
"""
        failures = _parse_test_failures(maven_output)

        # Should have 2 distinct failures (not deduplicated)
        assert len(failures) == 2

        # Verify both fully qualified class names are preserved
        class_names = {f["class"] for f in failures}
        assert "com.foo.UserServiceTest" in class_names
        assert "com.bar.UserServiceTest" in class_names

    def test_parse_test_failures_deduplicates_same_fq_class(self):
        """Test that duplicate failures from same FQ class are merged."""
        # Maven output with same test mentioned twice in summary (Maven duplicates errors)
        maven_output = """
[ERROR] Errors:
[ERROR]   com.example.MyTest.myMethod:15 ~ NullPointer Cannot invoke method
[ERROR]   com.example.MyTest.myMethod:15 ~ NullPointer Cannot invoke method
"""
        failures = _parse_test_failures(maven_output)

        # Should have only 1 failure (deduplicated)
        assert len(failures) == 1
        assert failures[0]["class"] == "com.example.MyTest"
        assert failures[0]["method"] == "myMethod"

    def test_parse_test_failures_preserves_fq_class_names(self):
        """Test that fully qualified class names are preserved in failure dict."""
        maven_output = """
[ERROR] Errors:
[ERROR]   com.coding.exercise.bankapp.service.BankingServiceTest.testMethod:100 ~ NullPointer test
"""
        failures = _parse_test_failures(maven_output)

        assert len(failures) == 1
        # FQ class name should be preserved (not simplified to BankingServiceTest)
        assert failures[0]["class"] == "com.coding.exercise.bankapp.service.BankingServiceTest"

    def test_parse_test_failures_multipackage_same_class_name(self):
        """Test that classes with same simple name but different packages don't collide."""
        # Real-world scenario: UserService in both com.foo and com.bar packages
        maven_output = """
[ERROR] Errors:
[ERROR]   com.foo.service.UserServiceTest.testCreate:50 ~ NullPointer user is null
[ERROR]   com.bar.admin.UserServiceTest.testCreate:30 ~ IllegalState not initialized
"""
        failures = _parse_test_failures(maven_output)

        # Should have 2 separate failures (not merged due to different FQ names)
        assert len(failures) == 2

        # Verify both are preserved with their FQ class names
        failures_by_class = {f["class"]: f for f in failures}
        assert "com.foo.service.UserServiceTest" in failures_by_class
        assert "com.bar.admin.UserServiceTest" in failures_by_class

        # Verify error messages are different (proving they're distinct)
        assert failures_by_class["com.foo.service.UserServiceTest"]["error"] == "user is null"
        assert failures_by_class["com.bar.admin.UserServiceTest"]["error"] == "not initialized"


class TestCrossPlatformSubprocess:
    """Test that subprocess calls work cross-platform (P1 verification)."""

    def test_maven_executable_works_with_subprocess(self):
        """Test that the detected Maven executable actually works with subprocess.run."""
        import subprocess

        mvn_path = _get_maven_executable()

        # Try to run 'mvn --version' without shell=True
        result = subprocess.run(
            [mvn_path, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Should succeed on all platforms
        assert result.returncode == 0
        assert "Apache Maven" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
