"""Unit tests for Maven MCP tools.

Tests cover run_tests, compile_tests, and analyze functions.
All tests mock subprocess calls to avoid external dependencies.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

# ============================================================================
# Tests for get_mvn_command()
# ============================================================================


class TestGetMvnCommand:
    """Tests for get_mvn_command utility function."""

    def test_get_mvn_command_windows(self):
        """On Windows, should return mvn.cmd."""
        from src.mcp_servers.maven_maintenance.utils import get_mvn_command

        with patch("sys.platform", "win32"), patch("shutil.which", return_value=None):
            result = get_mvn_command()
            assert result == "mvn.cmd"

    def test_get_mvn_command_windows_with_which(self):
        """On Windows with mvn.cmd found, should return full path."""
        from src.mcp_servers.maven_maintenance.utils import get_mvn_command

        with (
            patch("sys.platform", "win32"),
            patch("shutil.which", return_value="C:/tools/maven/bin/mvn.cmd"),
        ):
            result = get_mvn_command()
            assert result == "C:/tools/maven/bin/mvn.cmd"

    def test_get_mvn_command_unix(self):
        """On Unix, should return mvn."""
        from src.mcp_servers.maven_maintenance.utils import get_mvn_command

        with patch("sys.platform", "linux"):
            result = get_mvn_command()
            assert result == "mvn"


# ============================================================================
# Tests for run_tests()
# ============================================================================


class TestRunTests:
    """Tests for run_tests function."""

    @pytest.mark.asyncio
    async def test_run_tests_no_pom_returns_error(self, tmp_path):
        """Should return error if pom.xml not found."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

        result_json = await run_tests(str(tmp_path))
        result = json.loads(result_json)

        assert result["success"] is False
        assert "pom.xml not found" in result["error"]

    @pytest.mark.asyncio
    async def test_run_tests_success(self, temp_project_dir, mock_subprocess_success):
        """Should return success when tests pass."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await mock_subprocess_success()

            result_json = await run_tests(str(temp_project_dir))
            result = json.loads(result_json)

            assert result["success"] is True
            assert result["return_code"] == 0

    @pytest.mark.asyncio
    async def test_run_tests_failure(self, temp_project_dir, mock_subprocess_failure):
        """Should return failure details when tests fail."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await mock_subprocess_failure()

            result_json = await run_tests(str(temp_project_dir))
            result = json.loads(result_json)

            assert result["success"] is False
            assert result["return_code"] == 1

    @pytest.mark.asyncio
    async def test_run_tests_with_profiles(self, temp_project_dir, mock_subprocess_success):
        """Should include profiles in Maven command."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await mock_subprocess_success()

            await run_tests(str(temp_project_dir), profiles=["test", "coverage"])

            # Verify profiles were passed to Maven
            call_args = mock_exec.call_args[0]
            assert any("-Ptest,coverage" in str(arg) for arg in call_args)

    @pytest.mark.asyncio
    async def test_run_tests_parallel_mode(self, temp_project_dir, mock_subprocess_success):
        """Should configure parallel execution when requested."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await mock_subprocess_success()

            await run_tests(str(temp_project_dir), parallel=True)

            call_args = mock_exec.call_args[0]
            command_str = " ".join(str(arg) for arg in call_args)
            assert "-DforkCount" in command_str or "parallel" in command_str.lower()


# ============================================================================
# Tests for console output parsing
# ============================================================================


class TestParseConsoleOutput:
    """Tests for _parse_console_output function."""

    def test_parse_console_output_extracts_counts(self, maven_test_output_success):
        """Should extract test counts from Maven output."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import _parse_console_output

        result = _parse_console_output(maven_test_output_success)

        # Parser processes lines in order - verify it finds test counts
        assert result["total"] > 0
        assert result["failed"] == 0
        assert result["errors"] == 0

    def test_parse_console_output_with_failures(self, maven_test_output_failure):
        """Should extract failure counts from Maven output."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import _parse_console_output

        result = _parse_console_output(maven_test_output_failure)

        assert result["total"] == 5
        assert result["failed"] == 2
        assert result["errors"] == 0

    def test_parse_console_output_empty_returns_zeros(self):
        """Should return zeros for empty output."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import _parse_console_output

        result = _parse_console_output("")

        assert result["total"] == 0
        assert result["failed"] == 0


# ============================================================================
# Tests for compile_tests
# ============================================================================


class TestCompileTests:
    """Tests for compile_tests function."""

    @pytest.mark.asyncio
    async def test_compile_tests_success(self, temp_project_dir, mock_subprocess_success):
        """Should return success when compilation succeeds."""
        from src.mcp_servers.maven_maintenance.tools.compile import compile_tests

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await mock_subprocess_success()

            result_json = await compile_tests(str(temp_project_dir))
            result = json.loads(result_json)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_compile_tests_failure(self, temp_project_dir, mock_subprocess_failure):
        """Should return errors when compilation fails."""
        from src.mcp_servers.maven_maintenance.tools.compile import compile_tests

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_exec.return_value = await mock_subprocess_failure()

            result_json = await compile_tests(str(temp_project_dir))
            result = json.loads(result_json)

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_compile_tests_no_pom_returns_error(self, tmp_path):
        """Should return error if pom.xml not found."""
        from src.mcp_servers.maven_maintenance.tools.compile import compile_tests

        result_json = await compile_tests(str(tmp_path))
        result = json.loads(result_json)

        assert result["success"] is False
        assert "pom.xml" in result.get("error", "")


# ============================================================================
# Tests for analyze
# ============================================================================


class TestAnalyzeDependencies:
    """Tests for analyze_dependencies function."""

    @pytest.mark.asyncio
    async def test_analyze_dependencies_extracts_from_pom(self, temp_project_dir):
        """Should extract dependencies from pom.xml."""
        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        # The function parses pom.xml directly, no subprocess needed
        result_json = await analyze_dependencies(str(temp_project_dir))
        result = json.loads(result_json)

        # Basic pom.xml has no dependencies, but function should succeed
        assert result["success"] is True
        assert "dependencies" in result or "project_path" in result

    @pytest.mark.asyncio
    async def test_analyze_dependencies_no_pom_returns_error(self, tmp_path):
        """Should return error if pom.xml not found."""
        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        result_json = await analyze_dependencies(str(tmp_path))
        result = json.loads(result_json)

        assert result["success"] is False


# ============================================================================
# Tests for output truncation
# ============================================================================


class TestOutputTruncation:
    """Tests for output truncation behavior."""

    @pytest.mark.asyncio
    async def test_large_output_is_truncated(self, temp_project_dir):
        """Should truncate output larger than 5000 characters."""
        from src.mcp_servers.maven_maintenance.tools.run_tests import run_tests

        # Create mock with very large output
        large_output = "X" * 10000

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_proc = AsyncMock()
            mock_proc.returncode = 0
            mock_proc.communicate = AsyncMock(return_value=(large_output.encode(), b""))
            mock_exec.return_value = mock_proc

            result_json = await run_tests(str(temp_project_dir))
            result = json.loads(result_json)

            # Output should be truncated to last 5000 characters
            assert len(result["output"]) <= 5000
