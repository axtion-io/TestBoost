# SPDX-License-Identifier: Apache-2.0
"""Unit tests for testboost_lite.lib.cli.

Tests each CLI command with the Java sample project fixture.
LLM calls are mocked via testboost_bridge to test the workflow without an API key.

CRITICAL: In production, if the LLM is unreachable, the error MUST
propagate immediately. We test this explicitly.
"""

import argparse
import json
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from testboost_lite.lib.cli import (
    _extract_json_field,
    cmd_init,
    cmd_status,
)
from testboost_lite.lib.session_tracker import (
    STATUS_COMPLETED,
    get_current_session,
    update_step_file,
)

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
    """A Java project with testboost_lite initialized."""
    args = argparse.Namespace(project_path=str(java_project), name=None, description="")
    cmd_init(args)
    return java_project


# ============================================================================
# cmd_init
# ============================================================================


class TestCmdInit:
    def test_init_creates_testboost_dir(self, java_project):
        args = argparse.Namespace(project_path=str(java_project), name=None, description="")
        result = cmd_init(args)
        assert result == 0
        assert (java_project / ".testboost").is_dir()
        assert (java_project / ".testboost" / "sessions").is_dir()

    def test_init_creates_session(self, java_project):
        args = argparse.Namespace(project_path=str(java_project), name="auth-tests", description="Test auth module")
        result = cmd_init(args)
        assert result == 0
        sessions = list((java_project / ".testboost" / "sessions").iterdir())
        assert any("auth-tests" in s.name for s in sessions)

    def test_init_nonexistent_path(self, tmp_path):
        args = argparse.Namespace(project_path=str(tmp_path / "nonexistent"), name=None, description="")
        result = cmd_init(args)
        assert result == 1

    def test_init_prints_output(self, java_project, capsys):
        args = argparse.Namespace(project_path=str(java_project), name=None, description="")
        cmd_init(args)
        captured = capsys.readouterr()
        assert "Initialized" in captured.out
        assert "Created session" in captured.out
        assert "[TESTBOOST_INTEGRITY:" in captured.out

    def test_init_creates_integrity_secret(self, java_project):
        args = argparse.Namespace(project_path=str(java_project), name=None, description="")
        cmd_init(args)
        assert (java_project / ".testboost" / ".tb_secret").exists()


# ============================================================================
# cmd_analyze (mocked bridge)
# ============================================================================


class TestCmdAnalyze:
    @pytest.mark.asyncio
    async def test_analyze_writes_analysis_md(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_analyze_async

        # Mock the bridge functions
        mock_context = json.dumps({
            "success": True,
            "project_type": "spring-boot",
            "build_system": "maven",
            "java_version": "17",
            "frameworks": ["spring", "spring-boot"],
            "test_frameworks": ["junit5", "mockito", "assertj"],
            "source_structure": {"class_count": 6, "packages": ["com.example"]},
            "test_structure": {"test_count": 1},
            "dependencies": [],
        })
        mock_conventions = json.dumps({
            "success": True,
            "naming": {"dominant_pattern": "should_when"},
            "assertions": {"dominant_style": "assertj"},
            "mocking": {"uses_mockito": True, "uses_spring_mock_bean": False},
        })
        mock_files = [
            "src/main/java/com/example/service/UserService.java",
            "src/main/java/com/example/service/OrderService.java",
            "src/main/java/com/example/web/UserController.java",
        ]

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)

        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=mock_conventions), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=mock_files):
            result = await _cmd_analyze_async(args)

        assert result == 0

        session = get_current_session(str(initialized_project))
        analysis_file = Path(session["session_dir"]) / "analysis.md"
        assert analysis_file.exists()
        content = analysis_file.read_text()
        assert "status: completed" in content
        assert "spring-boot" in content
        assert "maven" in content

    @pytest.mark.asyncio
    async def test_analyze_detects_source_files(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_analyze_async

        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": ["spring"], "test_frameworks": ["junit5"],
            "source_structure": {"class_count": 3, "packages": []},
            "test_structure": {"test_count": 1}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/UserService.java",
                       "src/main/java/com/example/web/UserController.java"]

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=mock_files):
            await _cmd_analyze_async(args)

        session = get_current_session(str(initialized_project))
        analysis_file = Path(session["session_dir"]) / "analysis.md"
        content = analysis_file.read_text()
        assert "UserService" in content
        assert "UserController" in content

    @pytest.mark.asyncio
    async def test_analyze_no_session(self, tmp_path):
        from testboost_lite.lib.cli import _cmd_analyze_async
        # Use a bare directory with no .testboost/ at all
        bare_project = tmp_path / "bare-java"
        bare_project.mkdir()
        (bare_project / "pom.xml").write_text("<project/>")
        args = argparse.Namespace(project_path=str(bare_project), verbose=False)
        result = await _cmd_analyze_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_analyze_detects_java_version(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_analyze_async

        mock_context = json.dumps({
            "success": True, "project_type": "java", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=[]):
            await _cmd_analyze_async(args)

        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "analysis.md").read_text()
        assert "17" in content

    @pytest.mark.asyncio
    async def test_analyze_detects_test_conventions(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_analyze_async

        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": ["spring"], "test_frameworks": ["junit5"],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 1}, "dependencies": [],
        })
        mock_conventions = json.dumps({
            "success": True,
            "naming": {"dominant_pattern": "should_when"},
            "assertions": {"dominant_style": "assertj"},
            "mocking": {"uses_mockito": True, "uses_spring_mock_bean": False},
        })

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=mock_conventions), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=[]):
            await _cmd_analyze_async(args)

        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "analysis.md").read_text()
        assert "Conventions" in content
        assert "assertj" in content


# ============================================================================
# cmd_gaps
# ============================================================================


class TestCmdGaps:
    async def _setup_analysis(self, project_path):
        """Helper: create a completed analysis step."""
        from testboost_lite.lib.cli import _cmd_analyze_async
        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": ["spring"], "test_frameworks": ["junit5"],
            "source_structure": {"class_count": 3, "packages": []},
            "test_structure": {"test_count": 1}, "dependencies": [],
        })
        mock_files = [
            "src/main/java/com/example/service/UserService.java",
            "src/main/java/com/example/service/OrderService.java",
            "src/main/java/com/example/web/UserController.java",
        ]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=mock_files):
            await _cmd_analyze_async(args)

    @pytest.mark.asyncio
    async def test_gaps_identifies_missing_tests(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_gaps_async
        await self._setup_analysis(initialized_project)

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        result = await _cmd_gaps_async(args)
        assert result == 0

        session = get_current_session(str(initialized_project))
        gaps_file = Path(session["session_dir"]) / "coverage-gaps.md"
        assert gaps_file.exists()
        content = gaps_file.read_text()
        assert "status: completed" in content
        assert "WITHOUT tests" in content

    @pytest.mark.asyncio
    async def test_gaps_recognizes_existing_tests(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_gaps_async
        await self._setup_analysis(initialized_project)

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        await _cmd_gaps_async(args)

        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "coverage-gaps.md").read_text()
        # UserService has UserServiceTest, should be covered
        assert "Already Covered" in content or "UserService" in content

    @pytest.mark.asyncio
    async def test_gaps_without_analysis(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_gaps_async
        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        result = await _cmd_gaps_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_gaps_has_priority(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_gaps_async
        await self._setup_analysis(initialized_project)

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        await _cmd_gaps_async(args)

        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "coverage-gaps.md").read_text()
        assert "high" in content.lower()


# ============================================================================
# cmd_generate (with mocked LLM via bridge)
# ============================================================================


class TestCmdGenerate:
    async def _setup_gaps(self, project_path):
        """Helper: run analyze + gaps with mocks."""
        from testboost_lite.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 2, "packages": []},
            "test_structure": {"test_count": 1}, "dependencies": [],
        })
        mock_files = [
            "src/main/java/com/example/service/OrderService.java",
            "src/main/java/com/example/web/UserController.java",
        ]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=mock_files):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    @pytest.mark.asyncio
    async def test_generate_calls_bridge(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_generate_async
        await self._setup_gaps(initialized_project)

        mock_result = json.dumps({
            "success": True,
            "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass OrderServiceTest {\n    @Test\n    void test() {}\n}",
            "test_file": "src/test/java/com/example/OrderServiceTest.java",
            "test_count": 1,
            "context": {"class_name": "OrderService", "package": "com.example"},
        })

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("testboost_lite.lib.testboost_bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_result), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "generation.md").read_text()
        assert "status: completed" in content

    @pytest.mark.asyncio
    async def test_generate_writes_test_files(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_generate_async
        await self._setup_gaps(initialized_project)

        mock_result = json.dumps({
            "success": True,
            "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass OrderServiceTest {\n    @Test\n    void test() {}\n}",
            "test_file": "src/test/java/com/example/OrderServiceTest.java",
            "test_count": 1,
            "context": {"class_name": "OrderService", "package": "com.example"},
        })

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("testboost_lite.lib.testboost_bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_result), \
             patch("subprocess.run", return_value=mock_compile):
            await _cmd_generate_async(gen_args)

        test_file = initialized_project / "src" / "test" / "java" / "com" / "example" / "OrderServiceTest.java"
        assert test_file.exists()
        assert "@Test" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_generate_without_gaps(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_generate_async
        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        result = await _cmd_generate_async(args)
        assert result == 1


# ============================================================================
# cmd_validate (with mocked subprocess)
# ============================================================================


class TestCmdValidate:
    @pytest.mark.asyncio
    async def test_validate_compilation_success(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_validate_async

        session = get_current_session(str(initialized_project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Generation\n\nDone.")

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        mock_compile = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
        mock_test = MagicMock(returncode=0, stdout="Tests run: 5, Failures: 0\nBUILD SUCCESS", stderr="")

        with patch("subprocess.run", side_effect=[mock_compile, mock_test]):
            result = await _cmd_validate_async(args)

        assert result == 0
        content = (Path(session["session_dir"]) / "validation.md").read_text()
        assert "PASSED" in content

    @pytest.mark.asyncio
    async def test_validate_compilation_failure_uses_maven_parser(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_validate_async

        session = get_current_session(str(initialized_project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Generation\n\nDone.")

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        maven_error = "[ERROR] /test/OrderServiceTest.java:[10,5] cannot find symbol\n  symbol:   class Foo\n  location: class Bar\n"
        mock_compile = MagicMock(returncode=1, stdout=maven_error, stderr="BUILD FAILURE")

        # Mock the bridge's parse_maven_errors
        mock_parser = MagicMock()
        mock_parser.format_for_llm.return_value = "**Errors**: cannot find symbol"
        mock_parser.get_summary.return_value = {"total_errors": 1, "errors_by_type": {"cannot_find_symbol": 1}, "errors_by_file": {}}
        mock_errors = [MagicMock()]

        with patch("subprocess.run", return_value=mock_compile), \
             patch("testboost_lite.lib.testboost_bridge.parse_maven_errors", return_value=(mock_parser, mock_errors)):
            result = await _cmd_validate_async(args)

        assert result == 1
        content = (Path(session["session_dir"]) / "validation.md").read_text()
        assert "FAILED" in content

    @pytest.mark.asyncio
    async def test_validate_test_failure(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_validate_async

        session = get_current_session(str(initialized_project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Generation\n\nDone.")

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        mock_compile = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
        mock_test = MagicMock(returncode=1, stdout="Tests run: 5, Failures: 2\n[ERROR] FAIL: testCreate", stderr="BUILD FAILURE")

        with patch("subprocess.run", side_effect=[mock_compile, mock_test]):
            result = await _cmd_validate_async(args)

        assert result == 1
        content = (Path(session["session_dir"]) / "validation.md").read_text()
        assert "FAILED" in content

    @pytest.mark.asyncio
    async def test_validate_without_generation(self, initialized_project):
        from testboost_lite.lib.cli import _cmd_validate_async
        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        result = await _cmd_validate_async(args)
        assert result == 1


# ============================================================================
# cmd_status
# ============================================================================


class TestCmdStatus:
    def test_status_no_session(self, tmp_path, capsys):
        # Use a bare directory with no .testboost/ at all
        bare_project = tmp_path / "bare-java"
        bare_project.mkdir()
        (bare_project / "pom.xml").write_text("<project/>")
        args = argparse.Namespace(project_path=str(bare_project))
        result = cmd_status(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "No active session" in captured.out

    def test_status_with_session(self, initialized_project, capsys):
        args = argparse.Namespace(project_path=str(initialized_project))
        result = cmd_status(args)
        assert result == 0
        captured = capsys.readouterr()
        assert "Session" in captured.out
        assert "pending" in captured.out


# ============================================================================
# LLM Error Propagation - CRITICAL
# ============================================================================


class TestLLMErrorPropagation:
    """CRITICAL: If the LLM is not reachable, we MUST get an immediate error.
    The system should NEVER silently degrade or mock the LLM response.
    """

    async def _setup_for_generate(self, project_path):
        """Helper: prepare project up to gaps step."""
        from testboost_lite.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "java", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/OrderService.java"]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("testboost_lite.lib.testboost_bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("testboost_lite.lib.testboost_bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("testboost_lite.lib.testboost_bridge.find_source_files", return_value=mock_files):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    @pytest.mark.asyncio
    async def test_llm_connection_check_fails(self, initialized_project):
        """When LLM connection check fails at startup, generate MUST fail with clear error."""
        from testboost_lite.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch(
            "src.lib.startup_checks.check_llm_connection",
            new_callable=AsyncMock,
            side_effect=Exception("API key not configured for provider 'anthropic'"),
        ):
            result = await _cmd_generate_async(gen_args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_llm_provider_error_propagates(self, initialized_project):
        """When LLM API key is missing, generate MUST fail with clear error."""
        from testboost_lite.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch(
            "testboost_lite.lib.testboost_bridge.generate_adaptive_tests",
            new_callable=AsyncMock,
            side_effect=Exception("API key not configured for provider 'anthropic'"),
        ):
            result = await _cmd_generate_async(gen_args)

        assert result == 1
        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "generation.md").read_text()
        assert "FAILED" in content
        assert "API key" in content

    @pytest.mark.asyncio
    async def test_llm_timeout_propagates(self, initialized_project):
        """When LLM times out, the error must propagate."""
        from testboost_lite.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch(
            "testboost_lite.lib.testboost_bridge.generate_adaptive_tests",
            new_callable=AsyncMock,
            side_effect=TimeoutError("LLM request timed out after 120s"),
        ):
            result = await _cmd_generate_async(gen_args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_llm_network_error_propagates(self, initialized_project):
        """Network errors connecting to LLM must propagate."""
        from testboost_lite.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch(
            "testboost_lite.lib.testboost_bridge.generate_adaptive_tests",
            new_callable=AsyncMock,
            side_effect=ConnectionError("Failed to connect to LLM API"),
        ):
            result = await _cmd_generate_async(gen_args)

        assert result == 1


# ============================================================================
# _extract_json_field helper
# ============================================================================


class TestExtractJsonField:
    def test_extracts_field(self):
        md = "# Title\n\n```json\n{\"source_files\": [\"a.java\", \"b.java\"]}\n```\n"
        result = _extract_json_field(md, "source_files")
        assert result == ["a.java", "b.java"]

    def test_returns_none_for_missing_field(self):
        md = "# Title\n\n```json\n{\"other\": 42}\n```\n"
        result = _extract_json_field(md, "source_files")
        assert result is None

    def test_returns_none_for_no_json(self):
        md = "# Title\n\nNo JSON here."
        result = _extract_json_field(md, "source_files")
        assert result is None

    def test_handles_multiple_json_blocks(self):
        md = "```json\n{\"a\": 1}\n```\n\n```json\n{\"target\": \"found\"}\n```\n"
        result = _extract_json_field(md, "target")
        assert result == "found"

    def test_handles_malformed_json(self):
        md = "```json\n{invalid json}\n```\n\n```json\n{\"valid\": true}\n```\n"
        result = _extract_json_field(md, "valid")
        assert result is True
