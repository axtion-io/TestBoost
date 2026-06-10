# SPDX-License-Identifier: Apache-2.0
"""CLI mutation commands: mutate, killer, killer HITL pause and hints.

LLM calls are mocked via the bridge so the workflow is tested without an
API key. CRITICAL: if the LLM is unreachable, the error MUST propagate.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib.cli import (
    _extract_json_field,
)
from src.lib.session_tracker import (
    STATUS_COMPLETED,
    get_current_session,
    update_step_file,
)
from tests.unit.testboost.helpers import (  # noqa: F401
    ORDER_SERVICE,
    PAYMENT_SERVICE,
    THREE_FILES,
    USER_CONTROLLER,
    USER_SERVICE,
    failing_compile,
    gen_result,
    prepare_mutation,
    setup_gaps,
)


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
class TestKillerPause:
    """P2.C — killer pauses when no killer tests are generated."""

    @pytest.mark.asyncio
    async def test_pauses_when_no_killer_tests_generated(self, initialized_project):
        from src.lib.cli import _cmd_killer_async
        from src.lib.session_tracker import EXIT_AWAITING_INPUT
        session = prepare_mutation(initialized_project)

        # generate_killer_tests returns success with 0 tests
        mock_result = json.dumps({
            "success": True,
            "generated_tests": [],
            "total_mutants_targeted": 0,
            "total_tests": 0,
        })

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            max_tests=10,
            fail_on_uncertainty=True, answer_file=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.generate_killer_tests",
                   new_callable=AsyncMock, return_value=mock_result):
            rc = await _cmd_killer_async(args)

        assert rc == EXIT_AWAITING_INPUT
        session_dir = Path(session["session_dir"])
        qpath = session_dir / "question.json"
        assert qpath.exists()
        payload = json.loads(qpath.read_text())
        assert payload["kind"] == "killer_generation_yielded_nothing"
        assert payload["subject"]["surviving_mutant_count"] == 1
        # Question payload contains the top-priority survivor
        assert payload["subject"]["top_survivors"][0]["class"] == "com.example.OrderService"

    @pytest.mark.asyncio
    async def test_no_pause_when_flag_off(self, initialized_project):
        """Regression: existing behaviour preserved when flag off."""
        from src.lib.cli import _cmd_killer_async
        session = prepare_mutation(initialized_project)

        mock_result = json.dumps({
            "success": True,
            "generated_tests": [],
            "total_mutants_targeted": 0,
            "total_tests": 0,
        })

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            max_tests=10,
            fail_on_uncertainty=False, answer_file=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.generate_killer_tests",
                   new_callable=AsyncMock, return_value=mock_result):
            rc = await _cmd_killer_async(args)

        # Existing behaviour: status completed (or failed, depending on flow),
        # but NO question.json
        assert not (Path(session["session_dir"]) / "question.json").exists()
        assert rc in (0, 1)


# ============================================================================
# Phase 3 — cleanup, doctor, metrics (3.1, 3.2, 3.3)
# ============================================================================
class TestKillerHintsWiring:
    """P5.D — killer_hints reach the LLM call and a fruitless retry re-pauses."""

    @pytest.mark.asyncio
    async def test_hints_are_passed_to_generation(self, initialized_project, tmp_path):
        from src.lib.cli import _cmd_killer_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import emit_question
        session = prepare_mutation(initialized_project)
        session_dir = Path(session["session_dir"])

        emit_question(
            str(session_dir), "killer-tests",
            {"kind": "killer_generation_yielded_nothing", "question": "?"},
            project_path=str(initialized_project),
            session_id=session["session_id"],
        )
        question = json.loads((session_dir / "question.json").read_text())
        signed = sign_answer(
            {"killer_hints": {"OrderService.calculateTotal": "totals must round half-up"}},
            question, str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        mock_result = json.dumps({
            "success": True,
            "generated_tests": [{
                "class": "com.example.OrderService",
                "test_file": "src/test/java/com/example/OrderServiceKillerTest.java",
                "test_code": "import org.junit.jupiter.api.Test;\nclass K { @Test void k() {} }",
                "mutants_targeted": 1,
            }],
            "total_mutants_targeted": 1, "total_tests": 1,
        })
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.generate_killer_tests",
                   new_callable=AsyncMock, return_value=mock_result) as mock_killer, \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_killer_async(args)

        assert rc == 0
        hints_passed = mock_killer.call_args.kwargs.get("hints")
        assert hints_passed == {"OrderService.calculateTotal": "totals must round half-up"}
        # Answer consumed on success
        assert not (session_dir / "question.json").exists()
        assert (session_dir / "answer.json.consumed").exists()

    @pytest.mark.asyncio
    async def test_fruitless_hints_pause_again(self, initialized_project, tmp_path):
        """Hints applied but still 0 tests → pause again (not silent success),
        with the previous hints echoed in the new question."""
        from src.lib.cli import _cmd_killer_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import EXIT_AWAITING_INPUT, emit_question
        session = prepare_mutation(initialized_project)
        session_dir = Path(session["session_dir"])

        emit_question(
            str(session_dir), "killer-tests",
            {"kind": "killer_generation_yielded_nothing", "question": "?"},
            project_path=str(initialized_project),
            session_id=session["session_id"],
        )
        question = json.loads((session_dir / "question.json").read_text())
        signed = sign_answer(
            {"killer_hints": {"OrderService": "vague hint"}},
            question, str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        empty_result = json.dumps({
            "success": True, "generated_tests": [],
            "total_mutants_targeted": 0, "total_tests": 0,
        })
        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False, max_tests=10,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.generate_killer_tests",
                   new_callable=AsyncMock, return_value=empty_result):
            rc = await _cmd_killer_async(args)

        assert rc == EXIT_AWAITING_INPUT
        new_question = json.loads((session_dir / "question.json").read_text())
        assert new_question["kind"] == "killer_generation_yielded_nothing"
        assert new_question["subject"]["previous_hints"] == {"OrderService": "vague hint"}
