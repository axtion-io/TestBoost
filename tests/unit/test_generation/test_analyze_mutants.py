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
