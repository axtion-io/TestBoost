# SPDX-License-Identifier: Apache-2.0
"""Unit tests for src.test_generation.analyze_mutants (PIT report analysis)."""

import json
from pathlib import Path

import pytest

from src.test_generation.analyze_mutants import analyze_mutants

PIT_XML = """<?xml version="1.0" encoding="UTF-8"?>
<mutations>
  <mutation status="KILLED" detected="true">
    <sourceFile>OrderService.java</sourceFile>
    <mutatedClass>com.example.OrderService</mutatedClass>
    <mutatedMethod>calculateTotal</mutatedMethod>
    <lineNumber>10</lineNumber>
    <mutator>org.pitest.mutationtest.engine.gregor.mutators.MathMutator</mutator>
    <description>Replaced + with -</description>
    <killingTest>OrderServiceTest.t</killingTest>
  </mutation>
  <mutation status="SURVIVED" detected="false">
    <sourceFile>OrderService.java</sourceFile>
    <mutatedClass>com.example.OrderService</mutatedClass>
    <mutatedMethod>applyDiscount</mutatedMethod>
    <lineNumber>22</lineNumber>
    <mutator>org.pitest.mutationtest.engine.gregor.mutators.ConditionalsBoundaryMutator</mutator>
    <description>changed conditional boundary</description>
    <killingTest/>
  </mutation>
  <mutation status="SURVIVED" detected="false">
    <sourceFile>OrderService.java</sourceFile>
    <mutatedClass>com.example.OrderService</mutatedClass>
    <mutatedMethod>applyDiscount</mutatedMethod>
    <lineNumber>25</lineNumber>
    <mutator>org.pitest.mutationtest.engine.gregor.mutators.ConditionalsBoundaryMutator</mutator>
    <description>changed conditional boundary</description>
    <killingTest/>
  </mutation>
  <mutation status="NO_COVERAGE" detected="false">
    <sourceFile>UserService.java</sourceFile>
    <mutatedClass>com.example.UserService</mutatedClass>
    <mutatedMethod>create</mutatedMethod>
    <lineNumber>5</lineNumber>
    <mutator>org.pitest.mutationtest.engine.gregor.mutators.VoidMethodCallMutator</mutator>
    <description>removed call</description>
    <killingTest/>
  </mutation>
</mutations>
"""


def _write_report(base: Path) -> Path:
    report_dir = base / "target" / "pit-reports" / "202606100000"
    report_dir.mkdir(parents=True)
    (report_dir / "mutations.xml").write_text(PIT_XML)
    return report_dir


class TestAnalyzeMutants:
    @pytest.mark.asyncio
    async def test_nonexistent_project(self):
        result = json.loads(await analyze_mutants("/nonexistent/xyz"))
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_missing_report(self, tmp_path):
        result = json.loads(await analyze_mutants(str(tmp_path)))
        assert result["success"] is False
        assert "PIT report not found" in result["error"]

    @pytest.mark.asyncio
    async def test_full_analysis(self, tmp_path):
        _write_report(tmp_path)
        result = json.loads(await analyze_mutants(str(tmp_path), min_score=80))

        assert result["success"] is True
        assert result["summary"] == {
            "total_mutants": 4, "killed": 1, "survived": 2, "no_coverage": 1,
        }
        # 1 killed / 4 total = 25%
        assert result["mutation_score"] == 25.0
        assert result["meets_threshold"] is False
        # The repeated surviving mutator surfaces as a hard-to-kill pattern
        mutators = [h["mutator"] for h in result["hard_to_kill"]]
        assert "ConditionalsBoundaryMutator" in mutators
        # Per-class breakdown present
        classes = {c["class"] for c in result["by_class"]}
        assert "com.example.OrderService" in classes
        assert result["recommendations"], "should produce recommendations"

    @pytest.mark.asyncio
    async def test_meets_threshold(self, tmp_path):
        _write_report(tmp_path)
        result = json.loads(await analyze_mutants(str(tmp_path), min_score=20))
        assert result["meets_threshold"] is True

    @pytest.mark.asyncio
    async def test_explicit_report_path(self, tmp_path):
        report_dir = _write_report(tmp_path)
        result = json.loads(
            await analyze_mutants(str(tmp_path), report_path=str(report_dir))
        )
        assert result["success"] is True
        assert result["summary"]["total_mutants"] == 4


TIMEOUT = """  <mutation status="TIMED_OUT" detected="true">
    <sourceFile>OrderService.java</sourceFile>
    <mutatedClass>com.example.OrderService</mutatedClass>
    <mutatedMethod>loop</mutatedMethod>
    <lineNumber>30</lineNumber>
    <mutator>org.pitest.mutationtest.engine.gregor.mutators.IncrementsMutator</mutator>
    <description>Changed increment from 1 to -1</description>
    <killingTest/>
  </mutation>
</mutations>"""


class TestScoreConventions:
    """Same conventions as PIT, and declared equivalents left out of the analysis."""

    def _report(self, base):
        report_dir = base / "target" / "pit-reports"
        report_dir.mkdir(parents=True)
        (report_dir / "mutations.xml").write_text(PIT_XML.replace("</mutations>", TIMEOUT))
        return report_dir

    @pytest.mark.asyncio
    async def test_a_timed_out_mutant_is_detected(self, tmp_path):
        from unittest.mock import patch

        from src.test_generation.mutation import run_mutation_testing
        from tests.unit.test_generation.test_mutation import _fake_process

        (tmp_path / "pom.xml").write_text("<project/>")
        report = self._report(tmp_path)
        with patch("asyncio.create_subprocess_exec", return_value=_fake_process(0)):
            pit = json.loads(await run_mutation_testing(str(tmp_path)))
        assert pit["mutation_score"] == 40.0            # (1 killed + 1 timed out) / 5
        order = next(c for c in pit["by_class"] if c["class"] == "com.example.OrderService")
        assert (order["killed"], order["total"]) == (2, 4)
        analysis = json.loads(await analyze_mutants(str(tmp_path), report_path=str(report)))
        assert analysis["mutation_score"] == 40.0

    @pytest.mark.asyncio
    async def test_declared_equivalents_are_left_out(self, tmp_path):
        from src.lib.equivalents import mutant_id

        report = self._report(tmp_path)
        line22 = mutant_id({"class": "com.example.OrderService", "method": "applyDiscount", "line": 22,
                            "mutator": "org.pitest.mutationtest.engine.gregor.mutators.ConditionalsBoundaryMutator",
                            "description": "changed conditional boundary"})
        analysis = json.loads(await analyze_mutants(str(tmp_path), report_path=str(report), exclude_ids=[line22]))
        assert analysis["summary"]["survived"] == 1
        assert analysis["mutation_score"] == 50.0       # 2 detected / 4 left
        assert all(p.get("count", 1) == 1 for p in analysis["priority_improvements"])


class TestRecommendationsCountSurvivorsOnly:
    @pytest.mark.asyncio
    async def test_killed_mutants_are_not_reported_as_survivors(self, tmp_path):
        """Seen in a real run: '40 negated conditional mutants survived' with 0 survivors."""
        report_dir = tmp_path / "pit"
        report_dir.mkdir()
        killed = PIT_XML.replace('status="SURVIVED" detected="false"', 'status="KILLED" detected="true"')
        (report_dir / "mutations.xml").write_text(killed)
        analysis = json.loads(await analyze_mutants(str(tmp_path), report_path=str(report_dir)))
        assert analysis["summary"]["survived"] == 0
        assert not any("survived" in r for r in analysis["recommendations"])

    @pytest.mark.asyncio
    async def test_survivor_counts_match_the_survivors(self, tmp_path):
        report_dir = _write_report(tmp_path)
        analysis = json.loads(await analyze_mutants(str(tmp_path), report_path=str(report_dir)))
        assert "2 boundary condition mutants survived. Add tests for boundary values (<=, >=, <, >)." \
            in analysis["recommendations"]
