# SPDX-License-Identifier: Apache-2.0
"""Declared equivalent mutants (docs/workflow.md, Mutate / Killer).

A mutant no test can observe is declared once, with a reason; it then leaves
the effective score's denominator and is never a killer-test target again,
until the code moves (its id changes and it comes back).
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib import equivalents
from src.lib.cli import _cmd_mutate_async, cmd_context, cmd_equivalent, cmd_killer
from src.lib.commands._shared import _extract_json_field
from src.lib.session_tracker import STATUS_COMPLETED, get_current_session, update_step_file

SORT = {"class": "com.example.Vaud", "method": "feriesVaud", "line": 57,
        "mutator": "org.pitest.VoidMethodCallMutator", "description": "removed call to List::sort"}
BOUND = {"class": "com.example.Occurrences", "method": "occurrences", "line": 52,
         "mutator": "org.pitest.ConditionalsBoundaryMutator", "description": "changed conditional boundary"}
REASON = "the list is always built in chronological order"


def _args(project, **kw):
    return argparse.Namespace(project_path=str(project), verbose=False, **kw)


def _session_dir(project):
    return Path(get_current_session(str(project))["session_dir"])


async def _mutate(project, survivors=(SORT, BOUND), total=10, killed=8, min_score=90):
    update_step_file(str(_session_dir(project)), "validation", STATUS_COMPLETED, "# Validation\n")
    pit = json.dumps({"success": True, "mutation_score": round(100 * killed / total, 1),
                      "mutations": {"total": total, "killed": killed, "survived": len(survivors),
                                    "no_coverage": 0, "timed_out": 0},
                      "by_class": [], "surviving_mutants": list(survivors), "report_path": "/tmp/pit"})
    with patch("src.lib.bridge.run_mutation_testing", new=AsyncMock(return_value=pit)), \
         patch("src.lib.bridge.analyze_mutants", new=AsyncMock(return_value=json.dumps({"success": True}))):
        assert await _cmd_mutate_async(_args(project, target_classes=None, target_tests=None,
                                             min_score=min_score)) == 0
    md = (_session_dir(project) / "mutation.md").read_text()
    return md, lambda field: _extract_json_field(md, field)


class TestIds:
    def test_stable_and_location_sensitive(self):
        assert equivalents.mutant_id(SORT) == equivalents.mutant_id(dict(SORT))
        assert equivalents.mutant_id(SORT) != equivalents.mutant_id({**SORT, "line": 58})
        assert len(equivalents.mutant_id(SORT)) == 10


class TestDeclare:
    @pytest.mark.asyncio
    async def test_declared_mutant_leaves_score_and_killer_targets(self, initialized_project, capsys):
        _md, data = await _mutate(initialized_project)
        sort_id = equivalents.mutant_id(SORT)
        assert sort_id in [m["id"] for m in data("surviving_mutants")]     # ids shown in the report

        assert cmd_equivalent(_args(initialized_project, ids=[sort_id], reason=REASON, remove=False)) == 0
        assert "Declared equivalent" in capsys.readouterr().out

        md, data = await _mutate(initialized_project)
        assert data("mutation_score") == 80.0                  # raw PIT score unchanged
        assert data("effective_score") == round(100 * 8 / 9, 1)
        assert [m["id"] for m in data("surviving_mutants")] == [equivalents.mutant_id(BOUND)]
        assert data("equivalent_mutants")[0]["reason"] == REASON
        assert "Declared Equivalent Mutants" in md and REASON in md

    @pytest.mark.asyncio
    async def test_threshold_applies_to_the_effective_score(self, initialized_project):
        await _mutate(initialized_project, survivors=(SORT,), total=10, killed=9, min_score=95)
        cmd_equivalent(_args(initialized_project, ids=[equivalents.mutant_id(SORT)], reason=REASON, remove=False))
        _md, data = await _mutate(initialized_project, survivors=(SORT,), total=10, killed=9, min_score=95)
        assert data("mutation_score") == 90.0
        assert data("effective_score") == 100.0 and data("meets_threshold") is True

    @pytest.mark.asyncio
    async def test_refused_without_reason_or_for_an_unknown_id(self, initialized_project, capsys):
        await _mutate(initialized_project)
        sort_id = equivalents.mutant_id(SORT)
        assert cmd_equivalent(_args(initialized_project, ids=[sort_id], reason="", remove=False)) == 1
        assert cmd_equivalent(_args(initialized_project, ids=["0123456789"], reason=REASON, remove=False)) == 1
        err = capsys.readouterr().err
        assert "reason is required" in err and "Not a surviving mutant" in err
        assert equivalents.load(str(initialized_project)) == {}

    def test_requires_a_mutation_run(self, initialized_project):
        assert cmd_equivalent(_args(initialized_project, ids=["0123456789"], reason=REASON, remove=False)) == 1

    @pytest.mark.asyncio
    async def test_list_and_withdraw(self, initialized_project, capsys):
        await _mutate(initialized_project)
        sort_id = equivalents.mutant_id(SORT)
        cmd_equivalent(_args(initialized_project, ids=[sort_id], reason=REASON, remove=False))
        capsys.readouterr()
        assert cmd_equivalent(_args(initialized_project, ids=[], reason="", remove=False)) == 0
        assert sort_id in capsys.readouterr().out
        assert cmd_equivalent(_args(initialized_project, ids=[sort_id], reason="", remove=True)) == 0
        assert equivalents.load(str(initialized_project)) == {}
        _md, data = await _mutate(initialized_project)
        assert len(data("surviving_mutants")) == 2                       # back as a survivor

    @pytest.mark.asyncio
    async def test_declarations_are_project_level(self, initialized_project):
        await _mutate(initialized_project)
        cmd_equivalent(_args(initialized_project, ids=[equivalents.mutant_id(SORT)], reason=REASON, remove=False))
        assert (Path(initialized_project) / ".testboost" / "equivalents.json").exists()


class TestKillerSkipsEquivalents:
    def _source(self, project, rel):
        path = Path(project) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("package com.example;\npublic class X {}")

    @pytest.mark.asyncio
    async def test_declared_after_mutate_is_not_a_target(self, initialized_project):
        for c in ("Vaud", "Occurrences"):
            self._source(initialized_project, f"src/main/java/com/example/{c}.java")
        await _mutate(initialized_project)
        cmd_equivalent(_args(initialized_project, ids=[equivalents.mutant_id(SORT)], reason=REASON, remove=False))

        assert cmd_context(_args(initialized_project, files=None, killer=True, max_tests=10)) == 0
        manifest = json.loads((_session_dir(initialized_project) / "agent/killer/manifest.json").read_text())
        assert [m["class"] for m in manifest] == ["com.example.Occurrences"]
        brief = Path(manifest[0]["prompt_file"]).read_text()
        assert "testboost equivalent" in brief and equivalents.mutant_id(BOUND) in brief

    @pytest.mark.asyncio
    async def test_class_declared_equivalent_after_context_needs_no_file(self, initialized_project):
        for c in ("Vaud", "Occurrences"):
            self._source(initialized_project, f"src/main/java/com/example/{c}.java")
        await _mutate(initialized_project)
        assert cmd_context(_args(initialized_project, files=None, killer=True, max_tests=10)) == 0
        for m in (SORT, BOUND):
            cmd_equivalent(_args(initialized_project, ids=[equivalents.mutant_id(m)], reason=REASON, remove=False))
        with patch("subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mvn:
            assert cmd_killer(_args(initialized_project, agent=True)) == 0
        mvn.assert_not_called()
        assert "status: completed" in (_session_dir(initialized_project) / "killer-tests.md").read_text()
