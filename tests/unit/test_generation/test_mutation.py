# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.test_generation.mutation (PIT runner, subprocess mocked)."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.test_generation.mutation import run_mutation_testing
from tests.unit.test_generation.test_analyze_mutants import _write_report


def _fake_process(returncode=0, stdout=b"", stderr=b""):
    proc = AsyncMock()
    proc.returncode = returncode
    proc.communicate = AsyncMock(return_value=(stdout, stderr))
    return proc


class TestRunMutationTesting:
    @pytest.mark.asyncio
    async def test_nonexistent_project(self):
        result = json.loads(await run_mutation_testing("/nonexistent/xyz"))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_requires_pom(self, tmp_path):
        result = json.loads(await run_mutation_testing(str(tmp_path)))
        assert result["success"] is False
        assert "pom.xml" in result["error"]

    @pytest.mark.asyncio
    async def test_pit_failure_propagates_stderr(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        with patch("asyncio.create_subprocess_exec",
                   return_value=_fake_process(1, b"build log", b"BOOM")) as mock_exec:
            result = json.loads(await run_mutation_testing(str(tmp_path)))
        assert result["success"] is False
        assert "BOOM" in result["error"]
        assert result["output"] == "build log"
        # PIT goal + output formats are on the command line
        cmd = mock_exec.call_args.args
        # no pitest-maven in the pom: TestBoost's pinned version, never Maven's "latest"
        assert "org.pitest:pitest-maven:1.30.2:mutationCoverage" in cmd
        assert cmd.index("test-compile") < cmd.index("org.pitest:pitest-maven:1.30.2:mutationCoverage")
        assert any("-DoutputFormats=XML,HTML" in c for c in cmd)

    @pytest.mark.asyncio
    async def test_success_parses_report_and_score(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        _write_report(tmp_path)
        with patch("asyncio.create_subprocess_exec", return_value=_fake_process(0)):
            result = json.loads(await run_mutation_testing(
                str(tmp_path),
                target_classes=["com.example.*"],
                target_tests=["com.example.*Test"],
            ))
        assert result["success"] is True
        # 1 killed of 4 → 25%
        assert result["mutations"]["total"] == 4
        assert result["mutations"]["killed"] == 1
        assert result["mutations"]["survived"] == 2
        assert len(result["surviving_mutants"]) == 2
        assert result["surviving_mutants"][0]["class"] == "com.example.OrderService"
        assert result["report_path"]

    @pytest.mark.asyncio
    async def test_targets_forwarded_to_pit(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        _write_report(tmp_path)
        with patch("asyncio.create_subprocess_exec", return_value=_fake_process(0)) as mock_exec:
            await run_mutation_testing(
                str(tmp_path), target_classes=["com.a.*", "com.b.*"], mutators=["MATH"],
            )
        cmd = " ".join(mock_exec.call_args.args)
        assert "-DtargetClasses=com.a.*,com.b.*" in cmd
        assert "-Dmutators=MATH" in cmd


class TestReportsAndSetup:
    @pytest.mark.asyncio
    async def test_every_module_report_is_aggregated(self, tmp_path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        _write_report(tmp_path / "engine")
        _write_report(tmp_path / "app")
        with patch("asyncio.create_subprocess_exec", return_value=_fake_process(0)):
            result = json.loads(await run_mutation_testing(str(tmp_path)))
        assert result["mutations"]["total"] == 8 and len(result["report_paths"]) == 2

    @pytest.mark.asyncio
    async def test_a_report_older_than_the_run_is_ignored(self, tmp_path):
        import os
        (tmp_path / "pom.xml").write_text("<project></project>")
        stale = _write_report(tmp_path) / "mutations.xml"
        os.utime(stale, (1, 1))
        with patch("asyncio.create_subprocess_exec", return_value=_fake_process(0)):
            result = json.loads(await run_mutation_testing(str(tmp_path)))
        assert result["error"] == "PIT report not found"

    @pytest.mark.asyncio
    async def test_junit5_project_without_the_plugin_is_refused_before_running(self, tmp_path):
        (tmp_path / "pom.xml").write_text(
            "<project><dependencies><dependency><artifactId>junit-jupiter</artifactId>"
            "</dependency></dependencies></project>")
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            result = json.loads(await run_mutation_testing(str(tmp_path)))
        mock_exec.assert_not_called()
        assert "testboost pit-setup" in result["error"]
