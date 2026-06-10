# SPDX-License-Identifier: Apache-2.0
"""HITL pause triggers: generate/compile-fix/validate interruptions, hints mode.

LLM calls are mocked via the bridge so the workflow is tested without an
API key. CRITICAL: if the LLM is unreachable, the error MUST propagate.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


class TestCmdGenerateInterruption:
    """Round-trip: pause on missing context → answer file → resume."""

    @pytest.mark.asyncio
    async def test_pauses_and_emits_question_when_uncertain(self, initialized_project):
        """fail_on_uncertainty=True + empty edge_cases + no answer → exit 78."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import (
            EXIT_AWAITING_INPUT,
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
        )
        await setup_gaps(initialized_project)

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
        await setup_gaps(initialized_project)

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
        await setup_gaps(initialized_project)

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

    @pytest.mark.asyncio
    async def test_pauses_when_compile_fix_exhausted(self, initialized_project):
        """3 retries fail → fail_on_uncertainty=True → exit 78, question with compile errors."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import (
            EXIT_AWAITING_INPUT,
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
        )
        await setup_gaps(initialized_project)

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
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("src.lib.bridge.fix_compilation_errors",
                   new=AsyncMock(side_effect=fake_fix)), \
             patch("subprocess.run", return_value=failing_compile()):
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
        await setup_gaps(initialized_project)

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
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("src.lib.bridge.fix_compilation_errors",
                   new=AsyncMock(side_effect=fake_fix)), \
             patch("subprocess.run", return_value=failing_compile()):
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
        await setup_gaps(initialized_project)

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
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            result = await _cmd_generate_async(gen_args)

        assert result == 0
        # The on-disk file must contain the dev's code, not the LLM-generated one
        test_file = (initialized_project / "src" / "test" / "java" / "com" / "example"
                     / "service" / "OrderServiceTest.java")
        assert test_file.exists()
        assert "developer_fixed_test" in test_file.read_text()
        # Answer must be marked consumed
        session = get_current_session(str(initialized_project))
        assert (Path(session["session_dir"]) / "answer.json.consumed").exists()


# ============================================================================
# Phase 1 — `resume` and `sign-answer` commands, per-file cursor end-to-end
# ============================================================================
class TestHintsMode:
    """P2.A — exactly one LLM retry with hint injected when answer has hints."""

    @pytest.mark.asyncio
    async def test_hint_is_injected_into_llm_fix(self, initialized_project, tmp_path):
        """When answer has hints, fix_compilation_errors is called with hint in errors."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import emit_question
        await setup_gaps(initialized_project)

        session = get_current_session(str(initialized_project))
        emit_question(
            str(Path(session["session_dir"])), "generation",
            {"kind": "compilation_fix_exhausted", "question": "?"},
            project_path=str(initialized_project),
            session_id=session["session_id"],
        )
        question = json.loads((Path(session["session_dir"]) / "question.json").read_text())

        signed = sign_answer(
            {"compile_fixes": {"OrderService": {"hints": ["use Mockito.mock instead of @Mock"]}}},
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        # Compile fails first time, succeeds after LLM fix
        compile_responses = [
            MagicMock(returncode=1, stdout="",
                      stderr="[ERROR] OrderServiceTest.java:[5,12] cannot find symbol\n"),
            MagicMock(returncode=0, stdout="", stderr=""),
        ]
        compile_iter = iter(compile_responses)

        def fake_compile(*a, **k):
            return next(compile_iter)

        fix_calls: list[tuple] = []
        async def fake_fix(code, errors, class_name):
            fix_calls.append((code, errors, class_name))
            return code + "\n// fixed by hint"

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[{"scenario": "x", "expected": "y"}]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("src.lib.bridge.fix_compilation_errors", new=AsyncMock(side_effect=fake_fix)), \
             patch("subprocess.run", side_effect=fake_compile):
            rc = await _cmd_generate_async(gen_args)

        assert rc == 0
        # Exactly ONE LLM fix call, and it contained the hint
        assert len(fix_calls) == 1, f"expected 1 LLM fix call, got {len(fix_calls)}"
        _, errors_passed, _ = fix_calls[0]
        assert "use Mockito.mock" in errors_passed
        assert "Developer hints" in errors_passed

    @pytest.mark.asyncio
    async def test_fixed_code_wins_over_hints(self, initialized_project, tmp_path):
        """If both fixed_code and hints are provided, fixed_code wins; no LLM fix needed."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import emit_question
        await setup_gaps(initialized_project)

        session = get_current_session(str(initialized_project))
        emit_question(
            str(Path(session["session_dir"])), "generation",
            {"kind": "compilation_fix_exhausted", "question": "?"},
            project_path=str(initialized_project),
            session_id=session["session_id"],
        )
        question = json.loads((Path(session["session_dir"]) / "question.json").read_text())

        signed = sign_answer(
            {"compile_fixes": {"OrderService": {
                "fixed_code": "package c;\nimport org.junit.jupiter.api.Test;\nclass OrderServiceTest {\n  @Test void winner() {}\n}",
                "hints": ["this hint should be ignored"],
            }}},
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        fix_mock = AsyncMock(return_value="never-called")
        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[{"scenario": "x", "expected": "y"}]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("src.lib.bridge.fix_compilation_errors", new=fix_mock), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args)

        assert rc == 0
        # No LLM fix call: fixed_code was applied directly and compiled clean
        fix_mock.assert_not_called()
        # On-disk file contains the winner code
        test_file = (initialized_project / "src" / "test" / "java" / "com" / "example"
                     / "service" / "OrderServiceTest.java")
        assert "winner" in test_file.read_text()
class TestMarkdownPreview:
    """P2.D — question.json must carry an MR-ready markdown_preview."""

    def test_emit_question_includes_preview(self, tmp_path):
        from src.lib.session_tracker import create_session, emit_question, init_project
        init_project(str(tmp_path))
        session = create_session(str(tmp_path), name="prev")
        emit_question(
            session["session_dir"],
            "generation",
            {
                "kind": "missing_business_context",
                "subject": {"class_name": "Foo"},
                "question": "Provide the rules.",
                "answer_schema": {"test_requirements": []},
            },
            project_path=str(tmp_path),
            session_id=session["session_id"],
        )
        payload = json.loads(
            (Path(session["session_dir"]) / "question.json").read_text()
        )
        preview = payload["markdown_preview"]
        # Heading present
        assert "TestBoost needs input" in preview
        assert "missing_business_context" in preview
        # Question text present
        assert "Provide the rules" in preview
        # Subject section present and JSON-fenced
        assert "**Subject**" in preview
        assert '"class_name": "Foo"' in preview
        # Answer schema section present
        assert "Reply with this shape" in preview
        # Question ID present
        assert payload["question_id"] in preview

    def test_preview_is_part_of_signed_content(self, tmp_path):
        """The markdown_preview field must be covered by the HMAC so tampering is detected."""
        from src.lib.integrity import verify_question
        from src.lib.session_tracker import create_session, emit_question, init_project
        init_project(str(tmp_path))
        session = create_session(str(tmp_path), name="prev-sign")
        emit_question(
            session["session_dir"],
            "generation",
            {"kind": "x", "question": "?"},
            project_path=str(tmp_path),
            session_id=session["session_id"],
        )
        payload = json.loads(
            (Path(session["session_dir"]) / "question.json").read_text()
        )
        assert verify_question(payload, str(tmp_path)) is True
        # Tamper the preview only
        payload["markdown_preview"] = "evil"
        assert verify_question(payload, str(tmp_path)) is False


# ============================================================================
# Phase 2 — Validate pause + resume (2.2)
# ============================================================================
class TestValidatePause:
    """P2.B — validate pauses on runtime test failure with stack trace in question."""

    def _prepare_generation(self, project_path):
        session = get_current_session(str(project_path))
        update_step_file(
            session["session_dir"], "generation", STATUS_COMPLETED,
            "# Generation\n\nDone.",
            data={"generated": [{
                "path": "src/test/java/com/example/service/OrderServiceTest.java",
                "class_name": "OrderServiceTest",
            }]},
        )
        return session

    @pytest.mark.asyncio
    async def test_pauses_on_runtime_failure_with_stack_trace(self, initialized_project):
        from src.lib.cli import _cmd_validate_async
        from src.lib.session_tracker import (
            EXIT_AWAITING_INPUT,
            STATUS_AWAITING_INPUT,
            _parse_frontmatter,
        )
        session = self._prepare_generation(initialized_project)

        # Compile passes, test run fails
        mock_compile = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
        mock_test = MagicMock(
            returncode=1,
            stdout=(
                "[INFO] Tests run: 3, Failures: 1, Errors: 0\n"
                "[ERROR] OrderServiceTest.testOrderTotal:42 expected:<100> but was:<99>\n"
                "FAILED: OrderServiceTest.testOrderTotal\n"
            ),
            stderr="",
        )

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            fail_on_uncertainty=True, answer_file=None,
        )
        with patch("subprocess.run", side_effect=[mock_compile, mock_test]):
            rc = await _cmd_validate_async(args)

        assert rc == EXIT_AWAITING_INPUT

        session_dir = Path(session["session_dir"])
        qpath = session_dir / "question.json"
        assert qpath.exists()
        payload = json.loads(qpath.read_text())
        assert payload["kind"] == "tests_failed_at_runtime"
        assert "OrderServiceTest" in payload["subject"]["failing_classes"]
        # Stack trace included but bounded
        assert "expected:<100>" in payload["stack_trace"]
        # The validation step status is awaiting_input, not failed
        fm = _parse_frontmatter((session_dir / "validation.md").read_text())
        assert fm["status"] == STATUS_AWAITING_INPUT

    @pytest.mark.asyncio
    async def test_no_pause_when_flag_off(self, initialized_project):
        """Regression guard: existing behaviour preserved when flag is off."""
        from src.lib.cli import _cmd_validate_async
        from src.lib.session_tracker import STATUS_FAILED, _parse_frontmatter
        session = self._prepare_generation(initialized_project)

        mock_compile = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
        mock_test = MagicMock(
            returncode=1,
            stdout="[INFO] Tests run: 1, Failures: 1\nFAILED: Foo.bar\n", stderr="",
        )

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            fail_on_uncertainty=False, answer_file=None,
        )
        with patch("subprocess.run", side_effect=[mock_compile, mock_test]):
            rc = await _cmd_validate_async(args)

        assert rc == 1
        session_dir = Path(session["session_dir"])
        assert not (session_dir / "question.json").exists()
        fm = _parse_frontmatter((session_dir / "validation.md").read_text())
        assert fm["status"] == STATUS_FAILED

    @pytest.mark.asyncio
    async def test_resume_applies_validate_fixes(self, initialized_project, tmp_path):
        """Developer-provided fixed_code is written before re-running tests."""
        from src.lib.cli import _cmd_validate_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import emit_question
        session = self._prepare_generation(initialized_project)
        session_dir = Path(session["session_dir"])

        emit_question(
            str(session_dir), "validation",
            {"kind": "tests_failed_at_runtime", "question": "fix"},
            project_path=str(initialized_project),
            session_id=session["session_id"],
        )
        question = json.loads((session_dir / "question.json").read_text())

        fixed = (
            "package com.example;\n"
            "import org.junit.jupiter.api.Test;\n"
            "class OrderServiceTest {\n"
            "  @Test void developer_test() {}\n"
            "}\n"
        )
        signed = sign_answer(
            {"validate_fixes": {"OrderServiceTest": {"fixed_code": fixed}}},
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        # Compile + test both pass on the second attempt
        mock_compile = MagicMock(returncode=0, stdout="BUILD SUCCESS", stderr="")
        mock_test = MagicMock(returncode=0, stdout="Tests run: 1, Failures: 0", stderr="")

        args = argparse.Namespace(
            project_path=str(initialized_project), verbose=False,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("subprocess.run", side_effect=[mock_compile, mock_test]):
            rc = await _cmd_validate_async(args)

        assert rc == 0
        test_file = (initialized_project / "src" / "test" / "java" / "com" / "example"
                     / "service" / "OrderServiceTest.java")
        assert test_file.exists()
        assert "developer_test" in test_file.read_text()
class TestGuessFailingClass:
    def test_extracts_test_class_from_failure_line(self):
        from src.lib.cli import _guess_failing_class
        assert _guess_failing_class(
            "[ERROR] OrderServiceTest.testFoo:42 expected:<1>"
        ) == "OrderServiceTest"

    def test_extracts_from_at_stack_frame(self):
        from src.lib.cli import _guess_failing_class
        assert _guess_failing_class(
            "  at com.example.UserControllerTests.doStuff(UserControllerTests.java:99)"
        ) == "UserControllerTests"

    def test_returns_none_when_no_match(self):
        from src.lib.cli import _guess_failing_class
        assert _guess_failing_class("nothing relevant here") is None


# ============================================================================
# Phase 2 — Killer pause (2.3, minimal wiring)
# ============================================================================
