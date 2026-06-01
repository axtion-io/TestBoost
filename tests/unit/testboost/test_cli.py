# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.lib.cli.

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

from src.lib.cli import (
    _extract_json_field,
    _read_step_status,
    cmd_init,
    cmd_status,
)
from src.lib.session_tracker import (
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
    """A Java project with testboost initialized."""
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
        from src.lib.cli import _cmd_analyze_async

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

        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=mock_conventions), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            result = await _cmd_analyze_async(args)

        assert result == 0

        # Session-level analysis.md still exists (lightweight reference)
        session = get_current_session(str(initialized_project))
        analysis_file = Path(session["session_dir"]) / "analysis.md"
        assert analysis_file.exists()

        # Rich content is in the project-level .testboost/analysis.md
        project_analysis = Path(initialized_project) / ".testboost" / "analysis.md"
        assert project_analysis.exists()
        content = project_analysis.read_text()
        assert "status: completed" in content
        assert "spring-boot" in content
        assert "maven" in content

    @pytest.mark.asyncio
    async def test_analyze_detects_source_files(self, initialized_project):
        from src.lib.cli import _cmd_analyze_async

        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": ["spring"], "test_frameworks": ["junit5"],
            "source_structure": {"class_count": 3, "packages": []},
            "test_structure": {"test_count": 1}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/UserService.java",
                       "src/main/java/com/example/web/UserController.java"]

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)

        # Rich content (source file names) is in the project-level .testboost/analysis.md
        project_analysis = Path(initialized_project) / ".testboost" / "analysis.md"
        content = project_analysis.read_text()
        assert "UserService" in content
        assert "UserController" in content

    @pytest.mark.asyncio
    async def test_analyze_no_session(self, tmp_path):
        from src.lib.cli import _cmd_analyze_async
        # Use a bare directory with no .testboost/ at all
        bare_project = tmp_path / "bare-java"
        bare_project.mkdir()
        (bare_project / "pom.xml").write_text("<project/>")
        args = argparse.Namespace(project_path=str(bare_project), verbose=False)
        result = await _cmd_analyze_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_analyze_detects_java_version(self, initialized_project):
        from src.lib.cli import _cmd_analyze_async

        mock_context = json.dumps({
            "success": True, "project_type": "java", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=[]), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)

        # Java version is in the project-level .testboost/analysis.md
        project_analysis = Path(initialized_project) / ".testboost" / "analysis.md"
        content = project_analysis.read_text()
        assert "17" in content

    @pytest.mark.asyncio
    async def test_analyze_detects_test_conventions(self, initialized_project):
        from src.lib.cli import _cmd_analyze_async

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
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=mock_conventions), \
             patch("src.lib.bridge.find_source_files", return_value=[]), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)

        # Conventions are in the project-level .testboost/analysis.md
        project_analysis = Path(initialized_project) / ".testboost" / "analysis.md"
        content = project_analysis.read_text()
        assert "Conventions" in content
        assert "assertj" in content


# ============================================================================
# cmd_gaps
# ============================================================================


class TestCmdGaps:
    async def _setup_analysis(self, project_path):
        """Helper: create a completed analysis step."""
        from src.lib.cli import _cmd_analyze_async
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
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)

    @pytest.mark.asyncio
    async def test_gaps_identifies_missing_tests(self, initialized_project):
        from src.lib.cli import _cmd_gaps_async
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
        from src.lib.cli import _cmd_gaps_async
        await self._setup_analysis(initialized_project)

        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        await _cmd_gaps_async(args)

        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "coverage-gaps.md").read_text()
        # UserService has UserServiceTest, should be covered
        assert "Already Covered" in content or "UserService" in content

    @pytest.mark.asyncio
    async def test_gaps_without_analysis(self, initialized_project):
        from src.lib.cli import _cmd_gaps_async
        args = argparse.Namespace(project_path=str(initialized_project), verbose=False)
        result = await _cmd_gaps_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_gaps_has_priority(self, initialized_project):
        from src.lib.cli import _cmd_gaps_async
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
        from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async
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
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    @pytest.mark.asyncio
    async def test_generate_calls_bridge(self, initialized_project):
        from src.lib.cli import _cmd_generate_async
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
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_result), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        session = get_current_session(str(initialized_project))
        content = (Path(session["session_dir"]) / "generation.md").read_text()
        assert "status: completed" in content

    @pytest.mark.asyncio
    async def test_generate_writes_test_files(self, initialized_project):
        from src.lib.cli import _cmd_generate_async
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
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_result), \
             patch("subprocess.run", return_value=mock_compile):
            await _cmd_generate_async(gen_args)

        test_file = initialized_project / "src" / "test" / "java" / "com" / "example" / "OrderServiceTest.java"
        assert test_file.exists()
        assert "@Test" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_generate_without_gaps(self, initialized_project):
        from src.lib.cli import _cmd_generate_async
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
        from src.lib.cli import _cmd_validate_async

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
        from src.lib.cli import _cmd_validate_async

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
             patch("src.lib.bridge.parse_maven_errors", return_value=(mock_parser, mock_errors)):
            result = await _cmd_validate_async(args)

        assert result == 1
        content = (Path(session["session_dir"]) / "validation.md").read_text()
        assert "FAILED" in content

    @pytest.mark.asyncio
    async def test_validate_test_failure(self, initialized_project):
        from src.lib.cli import _cmd_validate_async

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
        from src.lib.cli import _cmd_validate_async
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
        from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "java", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/OrderService.java"]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    @pytest.mark.asyncio
    async def test_llm_connection_check_fails(self, initialized_project):
        """When LLM connection check fails at startup, generate MUST fail with clear error."""
        from src.lib.cli import _cmd_generate_async
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
        from src.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch(
            "src.lib.bridge.generate_adaptive_tests",
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
        from src.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch(
            "src.lib.bridge.generate_adaptive_tests",
            new_callable=AsyncMock,
            side_effect=TimeoutError("LLM request timed out after 120s"),
        ):
            result = await _cmd_generate_async(gen_args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_llm_network_error_propagates(self, initialized_project):
        """Network errors connecting to LLM must propagate."""
        from src.lib.cli import _cmd_generate_async
        await self._setup_for_generate(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, files=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch(
            "src.lib.bridge.generate_adaptive_tests",
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


# ============================================================================
# _read_step_status helper
# ============================================================================


class TestReadStepStatus:
    def test_reads_completed_status(self, tmp_path):
        f = tmp_path / "step.md"
        f.write_text("---\nstatus: completed\nstep: validation\n---\n\n# Done\n")
        assert _read_step_status(f) == "completed"

    def test_reads_failed_status(self, tmp_path):
        f = tmp_path / "step.md"
        f.write_text("---\nstatus: failed\nstep: validation\n---\n\n# Failed\n")
        assert _read_step_status(f) == "failed"

    def test_returns_unknown_for_missing_file(self, tmp_path):
        assert _read_step_status(tmp_path / "nonexistent.md") == "unknown"

    def test_returns_unknown_for_no_frontmatter(self, tmp_path):
        f = tmp_path / "step.md"
        f.write_text("# No frontmatter here\n")
        assert _read_step_status(f) == "unknown"


# ============================================================================
# cmd_mutate (with mocked bridge)
# ============================================================================


class TestCmdMutate:
    def _setup_validation(self, session_dir):
        """Helper: create a completed validation step."""
        update_step_file(session_dir, "generation", STATUS_COMPLETED, "# Generation\n\nDone.")
        update_step_file(session_dir, "validation", STATUS_COMPLETED, "# Validation\n\nAll tests passed.")

    @pytest.mark.asyncio
    async def test_mutate_runs_pit_and_analyzes(self, initialized_project):
        from src.lib.cli import _cmd_mutate_async

        session = get_current_session(str(initialized_project))
        self._setup_validation(session["session_dir"])

        pit_result = json.dumps({
            "success": True,
            "mutation_score": 75.0,
            "mutations": {"total": 20, "killed": 15, "survived": 4, "no_coverage": 1, "timed_out": 0},
            "by_class": [{"class": "com.example.UserService", "killed": 10, "total": 12, "score": 83.3}],
            "surviving_mutants": [
                {"class": "com.example.UserService", "method": "findById", "line": 25,
                 "mutator": "ConditionalsBoundaryMutator", "description": "changed > to >="},
            ],
            "report_path": "/tmp/pit-reports",
        })
        analysis_result = json.dumps({
            "success": True,
            "mutation_score": 75.0,
            "meets_threshold": False,
            "threshold": 80,
            "summary": {"total_mutants": 20, "killed": 15, "survived": 4, "no_coverage": 1},
            "hard_to_kill": [{"mutator": "ConditionalsBoundaryMutator", "count": 2, "examples": []}],
            "by_mutator": {"ConditionalsBoundaryMutator": 2},
            "by_class": [{"class": "com.example.UserService", "score": 83.3, "killed": 10, "survived": 2, "no_coverage": 0, "methods_count": 5}],
            "recommendations": ["Add boundary value tests."],
            "priority_improvements": [],
        })

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            target_classes=None, target_tests=None, min_score=80,
        )

        with patch("src.lib.bridge.run_mutation_testing", new_callable=AsyncMock, return_value=pit_result), \
             patch("src.lib.bridge.analyze_mutants", new_callable=AsyncMock, return_value=analysis_result):
            result = await _cmd_mutate_async(args)

        assert result == 0
        mutation_file = Path(session["session_dir"]) / "mutation.md"
        assert mutation_file.exists()
        content = mutation_file.read_text()
        assert "status: completed" in content
        assert "75.0%" in content
        assert "killer" in content.lower()

    @pytest.mark.asyncio
    async def test_mutate_without_validation(self, initialized_project):
        from src.lib.cli import _cmd_mutate_async

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            target_classes=None, target_tests=None, min_score=80,
        )
        result = await _cmd_mutate_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_mutate_blocked_by_failed_validation(self, initialized_project):
        """Mutation testing must refuse to run when validation failed."""
        from src.lib.cli import _cmd_mutate_async
        from src.lib.session_tracker import STATUS_FAILED

        session = get_current_session(str(initialized_project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Generation\n\nDone.")
        update_step_file(session["session_dir"], "validation", STATUS_FAILED, "# Validation\n\nTests failed.")

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            target_classes=None, target_tests=None, min_score=80,
        )
        result = await _cmd_mutate_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_mutate_pit_failure(self, initialized_project):
        from src.lib.cli import _cmd_mutate_async

        session = get_current_session(str(initialized_project))
        self._setup_validation(session["session_dir"])

        pit_result = json.dumps({
            "success": False,
            "error": "PIT execution failed: pitest-maven not found",
            "output": "BUILD FAILURE",
        })

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            target_classes=None, target_tests=None, min_score=80,
        )

        with patch("src.lib.bridge.run_mutation_testing", new_callable=AsyncMock, return_value=pit_result):
            result = await _cmd_mutate_async(args)

        assert result == 1
        content = (Path(session["session_dir"]) / "mutation.md").read_text()
        assert "FAILED" in content

    @pytest.mark.asyncio
    async def test_mutate_stores_surviving_mutants_in_data(self, initialized_project):
        from src.lib.cli import _cmd_mutate_async

        session = get_current_session(str(initialized_project))
        self._setup_validation(session["session_dir"])

        surviving = [
            {"class": "com.example.Foo", "method": "bar", "line": 10,
             "mutator": "NegateConditionalsMutator", "description": "negated conditional"},
        ]
        pit_result = json.dumps({
            "success": True, "mutation_score": 50.0,
            "mutations": {"total": 2, "killed": 1, "survived": 1, "no_coverage": 0, "timed_out": 0},
            "by_class": [], "surviving_mutants": surviving, "report_path": "/tmp/pit",
        })
        analysis_result = json.dumps({
            "success": True, "mutation_score": 50.0, "meets_threshold": False,
            "threshold": 80, "summary": {"total_mutants": 2, "killed": 1, "survived": 1, "no_coverage": 0},
            "hard_to_kill": [], "by_mutator": {}, "by_class": [],
            "recommendations": [], "priority_improvements": [],
        })

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            target_classes=None, target_tests=None, min_score=80,
        )

        with patch("src.lib.bridge.run_mutation_testing", new_callable=AsyncMock, return_value=pit_result), \
             patch("src.lib.bridge.analyze_mutants", new_callable=AsyncMock, return_value=analysis_result):
            await _cmd_mutate_async(args)

        # Verify surviving mutants are stored in the JSON data block
        content = (Path(session["session_dir"]) / "mutation.md").read_text()
        data = _extract_json_field(content, "surviving_mutants")
        assert data is not None
        assert len(data) == 1
        assert data[0]["class"] == "com.example.Foo"

    @pytest.mark.asyncio
    async def test_mutate_no_session(self, tmp_path):
        from src.lib.cli import _cmd_mutate_async
        bare_project = tmp_path / "bare"
        bare_project.mkdir()
        args = argparse.Namespace(
            project_path=str(bare_project), verbose=False,
            target_classes=None, target_tests=None, min_score=80,
        )
        result = await _cmd_mutate_async(args)
        assert result == 1


# ============================================================================
# cmd_killer (with mocked bridge)
# ============================================================================


class TestCmdKiller:
    def _setup_mutation(self, session_dir, surviving_mutants=None):
        """Helper: create completed validation + mutation steps."""
        update_step_file(session_dir, "generation", STATUS_COMPLETED, "# Generation\n\nDone.")
        update_step_file(session_dir, "validation", STATUS_COMPLETED, "# Validation\n\nPassed.")
        if surviving_mutants is None:
            surviving_mutants = [
                {"class": "com.example.UserService", "method": "findById", "line": 25,
                 "mutator": "ConditionalsBoundaryMutator", "description": "changed > to >="},
            ]
        update_step_file(
            session_dir, "mutation", STATUS_COMPLETED,
            "# Mutation Testing\n\nDone.",
            data={"mutation_score": 70.0, "surviving_mutants": surviving_mutants, "report_path": "/tmp/pit"},
        )

    @pytest.mark.asyncio
    async def test_killer_generates_tests(self, initialized_project):
        from src.lib.cli import _cmd_killer_async

        session = get_current_session(str(initialized_project))
        self._setup_mutation(session["session_dir"])

        killer_result = json.dumps({
            "success": True,
            "generated_tests": [
                {"class": "com.example.UserService", "test_file": "src/test/java/com/example/UserServiceKillerTest.java",
                 "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass UserServiceKillerTest {\n    @Test\n    void killMutant() {}\n}",
                 "mutants_targeted": 1},
            ],
            "total_tests": 1,
            "total_mutants_targeted": 1,
        })

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
        )

        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.generate_killer_tests", new_callable=AsyncMock, return_value=killer_result), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_killer_async(args)

        assert result == 0
        killer_file = Path(session["session_dir"]) / "killer-tests.md"
        assert killer_file.exists()
        content = killer_file.read_text()
        assert "status: completed" in content
        assert "UserServiceKillerTest" in content

        # Verify test file was written to disk
        test_file = initialized_project / "src" / "test" / "java" / "com" / "example" / "UserServiceKillerTest.java"
        assert test_file.exists()
        assert "@Test" in test_file.read_text()

    @pytest.mark.asyncio
    async def test_killer_without_mutation(self, initialized_project):
        from src.lib.cli import _cmd_killer_async

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
        )
        result = await _cmd_killer_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_killer_blocked_by_failed_mutation(self, initialized_project):
        """Killer generation must refuse to run when mutation step failed."""
        from src.lib.cli import _cmd_killer_async
        from src.lib.session_tracker import STATUS_FAILED

        session = get_current_session(str(initialized_project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Gen\n\nDone.")
        update_step_file(session["session_dir"], "validation", STATUS_COMPLETED, "# Val\n\nPassed.")
        update_step_file(session["session_dir"], "mutation", STATUS_FAILED, "# Mutation\n\nPIT crashed.")

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
        )
        result = await _cmd_killer_async(args)
        assert result == 1

    @pytest.mark.asyncio
    async def test_killer_fails_when_surviving_mutants_data_missing(self, initialized_project):
        """A completed mutation.md without surviving_mutants JSON must fail, not report perfect score."""
        from src.lib.cli import _cmd_killer_async

        session = get_current_session(str(initialized_project))
        update_step_file(session["session_dir"], "generation", STATUS_COMPLETED, "# Gen\n\nDone.")
        update_step_file(session["session_dir"], "validation", STATUS_COMPLETED, "# Val\n\nPassed.")
        # Write a completed mutation.md but WITHOUT any JSON data block
        update_step_file(
            session["session_dir"], "mutation", STATUS_COMPLETED,
            "# Mutation\n\nDone but data was lost.",
        )

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
        )
        result = await _cmd_killer_async(args)
        assert result == 1
        content = (Path(session["session_dir"]) / "killer-tests.md").read_text()
        assert "FAILED" in content

    @pytest.mark.asyncio
    async def test_killer_no_surviving_mutants(self, initialized_project):
        from src.lib.cli import _cmd_killer_async

        session = get_current_session(str(initialized_project))
        self._setup_mutation(session["session_dir"], surviving_mutants=[])

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
        )
        result = await _cmd_killer_async(args)
        assert result == 0
        content = (Path(session["session_dir"]) / "killer-tests.md").read_text()
        assert "perfect" in content.lower() or "No surviving" in content

    @pytest.mark.asyncio
    async def test_killer_llm_connection_failure(self, initialized_project):
        from src.lib.cli import _cmd_killer_async

        session = get_current_session(str(initialized_project))
        self._setup_mutation(session["session_dir"])

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
        )
        with patch(
            "src.lib.startup_checks.check_llm_connection",
            new_callable=AsyncMock,
            side_effect=Exception("API key not configured"),
        ):
            result = await _cmd_killer_async(args)

        assert result == 1

    @pytest.mark.asyncio
    async def test_killer_no_session(self, tmp_path):
        from src.lib.cli import _cmd_killer_async
        bare_project = tmp_path / "bare"
        bare_project.mkdir()
        args = argparse.Namespace(
            project_path=str(bare_project), verbose=False, max_tests=10,
        )
        result = await _cmd_killer_async(args)
        assert result == 1


# ============================================================================
# Edge case analysis integration in generate
# ============================================================================


class TestEdgeCaseIntegration:
    async def _setup_gaps(self, project_path):
        """Helper: run analyze + gaps with mocks."""
        from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/OrderService.java"]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    @pytest.mark.asyncio
    async def test_generate_calls_edge_case_analysis(self, initialized_project):
        """Edge case analysis should be called and results passed as test_requirements."""
        from src.lib.cli import _cmd_generate_async
        await self._setup_gaps(initialized_project)

        edge_cases = [
            {"method": "processOrder", "scenario": "null input", "description": "null order",
             "input_hint": "null", "expected_behavior": "throws NullPointerException", "category": "null_input"},
        ]

        mock_gen_result = json.dumps({
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
        mock_analyze_edge = AsyncMock(return_value=edge_cases)
        mock_generate = AsyncMock(return_value=mock_gen_result)

        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", mock_analyze_edge), \
             patch("src.lib.bridge.generate_adaptive_tests", mock_generate), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        # Verify edge cases were passed as test_requirements
        mock_generate.assert_called_once()
        call_kwargs = mock_generate.call_args
        assert call_kwargs.kwargs.get("test_requirements") == edge_cases

    @pytest.mark.asyncio
    async def test_generate_continues_if_edge_analysis_fails(self, initialized_project):
        """If edge case analysis fails, generation should still proceed."""
        from src.lib.cli import _cmd_generate_async
        await self._setup_gaps(initialized_project)

        mock_gen_result = json.dumps({
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
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, side_effect=Exception("LLM error")), \
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_gen_result), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0


# ============================================================================
# cmd_generate — human-in-the-loop interruption (spike)
# ============================================================================


class TestCmdGenerateInterruption:
    """Round-trip: pause on missing context → answer file → resume."""

    async def _setup_gaps(self, project_path):
        from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/OrderService.java"]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    @pytest.mark.asyncio
    async def test_pauses_and_emits_question_when_uncertain(self, initialized_project):
        """fail_on_uncertainty=True + empty edge_cases + no answer → exit 78."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import (
            EXIT_AWAITING_INPUT,
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
        )
        await self._setup_gaps(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock) as mock_gen:
            result = await _cmd_generate_async(gen_args)

        assert result == EXIT_AWAITING_INPUT, f"expected exit 78, got {result}"
        # LLM generation must NOT have run when we paused
        mock_gen.assert_not_called()

        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])

        # question.json must exist and be well-formed
        qpath = session_dir / "question.json"
        assert qpath.exists(), "question.json was not written"
        payload = json.loads(qpath.read_text())
        assert payload["kind"] == "missing_business_context"
        assert payload["step"] == "generation"
        assert payload["subject"]["class_name"] == "OrderService"
        assert "answer_schema" in payload

        # Step status must be awaiting_input (not failed)
        step_md = (session_dir / "generation.md").read_text()
        fm = _parse_frontmatter(step_md)
        assert fm["status"] == STATUS_AWAITING_INPUT

    @pytest.mark.asyncio
    async def test_does_not_pause_when_flag_off(self, initialized_project):
        """fail_on_uncertainty=False → existing behaviour, generation completes."""
        from src.lib.cli import _cmd_generate_async
        await self._setup_gaps(initialized_project)

        mock_result = json.dumps({
            "success": True,
            "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass OrderServiceTest {\n  @Test\n  void t() {}\n}",
            "test_file": "src/test/java/com/example/OrderServiceTest.java",
            "test_count": 1,
            "context": {"class_name": "OrderService", "package": "com.example"},
        })
        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=False, answer_file=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_result), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        session = get_current_session(str(initialized_project))
        assert not (Path(session["session_dir"]) / "question.json").exists()

    @pytest.mark.asyncio
    async def test_resumes_with_answer_file(self, initialized_project, tmp_path):
        """answer-file provided → injected into test_requirements, generation completes."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer, sign_question
        await self._setup_gaps(initialized_project)

        # Simulate a prior paused run with a properly signed question
        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        question = sign_question(
            {"step": "generation", "kind": "missing_business_context"},
            str(initialized_project),
        )
        (session_dir / "question.json").write_text(json.dumps(question))

        # The developer's signed answer (the shape the question advertised)
        answer_payload = sign_answer(
            {
                "test_requirements": [
                    {"scenario": "order with zero items must throw", "expected": "IllegalArgumentException"},
                    {"scenario": "discount > 100% must be capped", "expected": "value = 100"},
                ],
            },
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(answer_payload))

        mock_result = json.dumps({
            "success": True,
            "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass OrderServiceTest {\n  @Test\n  void t() {}\n}",
            "test_file": "src/test/java/com/example/OrderServiceTest.java",
            "test_count": 1,
            "context": {"class_name": "OrderService", "package": "com.example"},
        })
        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock, return_value=mock_result) as mock_gen, \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0

        # Verify the answer was injected into test_requirements
        call_kwargs = mock_gen.call_args.kwargs
        injected = call_kwargs.get("test_requirements")
        assert injected, "test_requirements should not be empty"
        scenarios = [r["scenario"] for r in injected]
        assert any("zero items" in s for s in scenarios)
        assert any("discount" in s for s in scenarios)

        # Question file must be cleared, consumed marker present
        assert not (session_dir / "question.json").exists()
        assert (session_dir / "answer.json.consumed").exists()


# ============================================================================
# cmd_generate — compile-fix interruption (spike continuation)
# ============================================================================


class TestCompileFixInterruption:
    """Pause / resume around the compile-fix retry budget."""

    async def _setup_gaps(self, project_path):
        from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 1, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })
        mock_files = ["src/main/java/com/example/service/OrderService.java"]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    def _gen_result(self):
        return json.dumps({
            "success": True,
            "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass OrderServiceTest {\n  @Test\n  void t() {}\n}",
            "test_file": "src/test/java/com/example/OrderServiceTest.java",
            "test_count": 1,
            "context": {"class_name": "OrderService", "package": "com.example"},
        })

    def _failing_compile(self):
        # Compile always fails; stderr names the test file so the parser keeps it
        return MagicMock(
            returncode=1,
            stdout="",
            stderr="[ERROR] /tmp/OrderServiceTest.java:[5,12] cannot find symbol\n",
        )

    @pytest.mark.asyncio
    async def test_pauses_when_compile_fix_exhausted(self, initialized_project):
        """3 retries fail → fail_on_uncertainty=True → exit 78, question with compile errors."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import (
            EXIT_AWAITING_INPUT,
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
        )
        await self._setup_gaps(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )

        # LLM fix returns a slightly different code each time so the
        # "identical code → stop" guard doesn't short-circuit retries
        fix_outputs = iter([
            "package com.example;\n// fix 1\nclass OrderServiceTest {}",
            "package com.example;\n// fix 2\nclass OrderServiceTest {}",
        ])

        async def fake_fix(code, errors, name):
            try:
                return next(fix_outputs)
            except StopIteration:
                return code + "\n// final"

        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[{"scenario": "x", "expected": "y"}]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=self._gen_result()), \
             patch("src.lib.bridge.fix_compilation_errors",
                   new=AsyncMock(side_effect=fake_fix)), \
             patch("subprocess.run", return_value=self._failing_compile()):
            result = await _cmd_generate_async(gen_args)

        assert result == EXIT_AWAITING_INPUT, f"expected exit 78, got {result}"

        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        qpath = session_dir / "question.json"
        assert qpath.exists()
        payload = json.loads(qpath.read_text())
        assert payload["kind"] == "compilation_fix_exhausted"
        assert payload["subject"]["class_name"] == "OrderService"
        assert payload["subject"]["attempts"] == 3
        assert "cannot find symbol" in payload["compile_errors"]
        assert "answer_schema" in payload

        fm = _parse_frontmatter((session_dir / "generation.md").read_text())
        assert fm["status"] == STATUS_AWAITING_INPUT

    @pytest.mark.asyncio
    async def test_silent_giveup_when_flag_off(self, initialized_project):
        """fail_on_uncertainty=False → existing behaviour preserved (no pause, exit 0)."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import STATUS_COMPLETED, _parse_frontmatter
        await self._setup_gaps(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=False, answer_file=None,
        )

        fix_outputs = iter([
            "package com.example;\n// fix 1\nclass OrderServiceTest {}",
            "package com.example;\n// fix 2\nclass OrderServiceTest {}",
        ])

        async def fake_fix(code, errors, name):
            try:
                return next(fix_outputs)
            except StopIteration:
                return code + "\n// final"

        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[{"scenario": "x", "expected": "y"}]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=self._gen_result()), \
             patch("src.lib.bridge.fix_compilation_errors",
                   new=AsyncMock(side_effect=fake_fix)), \
             patch("subprocess.run", return_value=self._failing_compile()):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        assert not (session_dir / "question.json").exists()
        fm = _parse_frontmatter((session_dir / "generation.md").read_text())
        assert fm["status"] == STATUS_COMPLETED

    @pytest.mark.asyncio
    async def test_resume_applies_developer_fix(self, initialized_project, tmp_path):
        """answer-file with compile_fixes[class].fixed_code → applied, compile passes, exit 0."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer, sign_question
        await self._setup_gaps(initialized_project)

        # Simulate a prior paused run on compile-fix exhaustion
        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        question = sign_question(
            {"step": "generation", "kind": "compilation_fix_exhausted"},
            str(initialized_project),
        )
        (session_dir / "question.json").write_text(json.dumps(question))

        dev_code = (
            "package com.example;\n"
            "import org.junit.jupiter.api.Test;\n"
            "class OrderServiceTest {\n"
            "  @Test\n"
            "  void developer_fixed_test() {}\n"
            "}\n"
        )
        signed_answer = sign_answer(
            {"compile_fixes": {"OrderService": {"fixed_code": dev_code}}},
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed_answer))

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )

        # Compile passes immediately once dev's code is in place
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[{"scenario": "x", "expected": "y"}]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=self._gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        # The on-disk file must contain the dev's code, not the LLM-generated one
        test_file = (initialized_project / "src" / "test" / "java" / "com" / "example"
                     / "OrderServiceTest.java")
        assert test_file.exists()
        assert "developer_fixed_test" in test_file.read_text()
        # Answer must be marked consumed
        session = get_current_session(str(initialized_project))
        assert (Path(session["session_dir"]) / "answer.json.consumed").exists()


# ============================================================================
# Phase 1 — `resume` and `sign-answer` commands, per-file cursor end-to-end
# ============================================================================


class TestResumeCommand:
    def _setup_session_with_question(self, project_path):
        """Initialize a project, create a session, write a signed question.json."""
        from src.lib.session_tracker import emit_question
        cmd_init(argparse.Namespace(
            project_path=str(project_path), name=None, description="", tech="java-spring",
        ))
        session = get_current_session(str(project_path))
        session_dir = Path(session["session_dir"])
        emit_question(
            str(session_dir),
            "generation",
            {
                "kind": "missing_business_context",
                "subject": {"class_name": "Foo"},
                "question": "what?",
                "answer_schema": {"test_requirements": []},
            },
            project_path=str(project_path),
            session_id=session["session_id"],
        )
        question = json.loads((session_dir / "question.json").read_text())
        return session_dir, question

    def test_no_session_returns_1(self, tmp_path, capsys):
        from src.lib.cli import cmd_resume
        rc = cmd_resume(argparse.Namespace(
            project_path=str(tmp_path), answer_file=None, verbose=False,
        ))
        assert rc == 1
        assert "No active session" in capsys.readouterr().err

    def test_no_pending_question_returns_2(self, tmp_path, capsys):
        from src.lib.cli import cmd_resume
        cmd_init(argparse.Namespace(project_path=str(tmp_path), name=None, description="", tech="java-spring"))
        rc = cmd_resume(argparse.Namespace(
            project_path=str(tmp_path), answer_file=None, verbose=False,
        ))
        assert rc == 2
        assert "No question pending" in capsys.readouterr().err

    def test_show_pending_prints_markdown_preview(self, tmp_path, capsys):
        from src.lib.cli import cmd_resume
        self._setup_session_with_question(tmp_path)
        rc = cmd_resume(argparse.Namespace(
            project_path=str(tmp_path), answer_file=None, verbose=False,
        ))
        assert rc == 0
        out = capsys.readouterr().out
        assert "TestBoost needs input" in out
        assert "missing_business_context" in out

    def test_dispatches_to_generate_with_answer(self, tmp_path):
        """Resume with --answer-file should dispatch to cmd_generate."""
        from unittest.mock import patch

        from src.lib.cli import cmd_resume
        self._setup_session_with_question(tmp_path)
        # We don't need a real answer file here — just verify dispatch
        called_args = {}
        def fake_gen(args):
            called_args["project_path"] = args.project_path
            called_args["answer_file"] = args.answer_file
            return 0
        with patch("src.lib.cli.cmd_generate", side_effect=fake_gen):
            rc = cmd_resume(argparse.Namespace(
                project_path=str(tmp_path),
                answer_file="/tmp/some-answer.json",
                verbose=False,
            ))
        assert rc == 0
        assert called_args["project_path"] == str(tmp_path)
        assert called_args["answer_file"] == "/tmp/some-answer.json"


class TestSignAnswerCommand:
    def test_signs_to_stdout(self, tmp_path, capsys):
        from src.lib.cli import cmd_sign_answer
        from src.lib.integrity import sign_question

        cmd_init(argparse.Namespace(project_path=str(tmp_path), name=None, description="", tech="java-spring"))
        q = sign_question({"k": "v"}, str(tmp_path))
        qfile = tmp_path / "q.json"
        qfile.write_text(json.dumps(q))
        afile = tmp_path / "raw_a.json"
        afile.write_text(json.dumps({"test_requirements": [{"s": 1}]}))

        capsys.readouterr()  # drain noise from cmd_init
        rc = cmd_sign_answer(argparse.Namespace(
            project_path=str(tmp_path),
            question_file=str(qfile),
            answer_file=str(afile),
            output=None,
        ))
        assert rc == 0
        out = capsys.readouterr().out
        signed = json.loads(out)
        assert signed["question_id"] == q["question_id"]
        assert "signature" in signed
        assert signed["test_requirements"] == [{"s": 1}]

    def test_writes_to_output_file(self, tmp_path):
        from src.lib.cli import cmd_sign_answer
        from src.lib.integrity import sign_question

        cmd_init(argparse.Namespace(project_path=str(tmp_path), name=None, description="", tech="java-spring"))
        q = sign_question({"k": "v"}, str(tmp_path))
        qfile = tmp_path / "q.json"
        qfile.write_text(json.dumps(q))
        afile = tmp_path / "raw_a.json"
        afile.write_text(json.dumps({"x": 1}))
        out = tmp_path / "signed.json"

        rc = cmd_sign_answer(argparse.Namespace(
            project_path=str(tmp_path),
            question_file=str(qfile),
            answer_file=str(afile),
            output=str(out),
        ))
        assert rc == 0
        signed = json.loads(out.read_text())
        assert signed["question_id"] == q["question_id"]

    def test_rejects_missing_files(self, tmp_path, capsys):
        from src.lib.cli import cmd_sign_answer
        rc = cmd_sign_answer(argparse.Namespace(
            project_path=str(tmp_path),
            question_file=str(tmp_path / "nope.json"),
            answer_file=str(tmp_path / "nope2.json"),
            output=None,
        ))
        assert rc == 1
        assert "not found" in capsys.readouterr().err


class TestPerFileCursorE2E:
    """P1.A — pause on file N, resume must skip files < N."""

    async def _setup_gaps_3_files(self, project_path):
        """Generate a 3-file gap list."""
        from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async
        mock_context = json.dumps({
            "success": True, "project_type": "spring-boot", "build_system": "maven",
            "java_version": "17", "frameworks": [], "test_frameworks": [],
            "source_structure": {"class_count": 3, "packages": []},
            "test_structure": {"test_count": 0}, "dependencies": [],
        })
        mock_files = [
            "src/main/java/com/example/service/OrderService.java",
            "src/main/java/com/example/web/UserController.java",
            "src/main/java/com/example/service/PaymentService.java",
        ]
        args = argparse.Namespace(project_path=str(project_path), verbose=False)
        with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
             patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
             patch("src.lib.bridge.find_source_files", return_value=mock_files), \
             patch("src.lib.bridge.build_class_index", return_value={}), \
             patch("src.lib.bridge.extract_test_examples", return_value=[]):
            await _cmd_analyze_async(args)
        await _cmd_gaps_async(args)

    def _gen_result(self, class_name="OrderService", pkg="com.example"):
        return json.dumps({
            "success": True,
            "test_code": "package com.example;\nimport org.junit.jupiter.api.Test;\nclass T {\n  @Test void t() {}\n}",
            "test_file": f"src/test/java/com/example/{class_name}Test.java",
            "test_count": 1,
            "context": {"class_name": class_name, "package": pkg},
        })

    @pytest.mark.asyncio
    async def test_cursor_advances_per_file_success(self, initialized_project):
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import load_generation_cursor
        await self._setup_gaps_3_files(initialized_project)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=False, answer_file=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[{"scenario": "x", "expected": "y"}]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=self._gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args)

        assert rc == 0
        # On full success, the cursor is cleared
        session = get_current_session(str(initialized_project))
        assert load_generation_cursor(session["session_dir"]) is None

    @pytest.mark.asyncio
    async def test_pause_persists_cursor_at_paused_file(self, initialized_project):
        """P1.A first half: pause on file index 1 → cursor at 1, file 0 completed."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import load_generation_cursor
        await self._setup_gaps_3_files(initialized_project)

        # Return edge_cases for files 0 and 2, empty for file 1
        edge_calls = [
            [{"scenario": "ok", "expected": "ok"}],  # file 0
            [],                                       # file 1 -> pause
            [{"scenario": "ok", "expected": "ok"}],  # file 2
        ]
        edge_iter = iter(edge_calls)

        async def fake_edge(*a, **k):
            try:
                return next(edge_iter)
            except StopIteration:
                return []

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new=AsyncMock(side_effect=fake_edge)), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=self._gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args)

        from src.lib.session_tracker import EXIT_AWAITING_INPUT
        assert rc == EXIT_AWAITING_INPUT

        session = get_current_session(str(initialized_project))
        cursor = load_generation_cursor(session["session_dir"])
        assert cursor is not None
        assert cursor["current_index"] == 1
        assert len(cursor["completed_files"]) == 1
        assert "OrderService.java" in cursor["completed_files"][0]

    @pytest.mark.asyncio
    async def test_resume_skips_completed_files(self, initialized_project, tmp_path):
        """P1.A second half: after pause at 1, resume must regenerate only files 1 and 2."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import load_generation_cursor
        await self._setup_gaps_3_files(initialized_project)

        # First run: pause at index 1
        edge_calls = [
            [{"scenario": "ok", "expected": "ok"}],
            [],
            [{"scenario": "ok", "expected": "ok"}],
        ]
        edge_iter = iter(edge_calls)
        async def fake_edge_1(*a, **k):
            try:
                return next(edge_iter)
            except StopIteration:
                return []

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new=AsyncMock(side_effect=fake_edge_1)), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=self._gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            await _cmd_generate_async(gen_args)

        # Second run: build a signed answer for the pending question, resume
        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        question = json.loads((session_dir / "question.json").read_text())

        signed_answer = sign_answer(
            {"test_requirements": [{"scenario": "from dev", "expected": "ok"}]},
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed_answer))

        gen_calls: list[str] = []
        async def track_gen(**kwargs):
            gen_calls.append(kwargs.get("source_file", ""))
            return self._gen_result()

        gen_args_2 = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new=AsyncMock(side_effect=track_gen)), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args_2)

        assert rc == 0
        # generate_adaptive_tests must have been called only for files 1 and 2
        assert len(gen_calls) == 2, f"expected 2 LLM calls (files 1,2), got {len(gen_calls)}"
        assert all("OrderService" not in f for f in gen_calls), \
            f"file 0 (OrderService) should have been skipped, got {gen_calls}"
        # Cursor cleared on completion
        assert load_generation_cursor(session_dir) is None

    @pytest.mark.asyncio
    async def test_resume_rejects_unsigned_answer(self, initialized_project, tmp_path, capsys):
        """P1.B — unsigned answer must be rejected, no LLM call."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import emit_question
        await self._setup_gaps_3_files(initialized_project)

        # Plant a pending question
        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        emit_question(
            session_dir, "generation",
            {"kind": "missing_business_context", "question": "?"},
            project_path=str(initialized_project),
            session_id=session["session_id"],
        )

        # Unsigned answer
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps({"test_requirements": [{"scenario": "x"}]}))

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=False, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock) as mock_gen:
            rc = await _cmd_generate_async(gen_args)

        assert rc == 1
        assert "signature" in capsys.readouterr().err.lower()
        mock_gen.assert_not_called()
