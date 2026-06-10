# SPDX-License-Identifier: Apache-2.0
"""Resume round-trips: resume/sign-answer commands, cursor, batched questions.

LLM calls are mocked via the bridge so the workflow is tested without an
API key. CRITICAL: if the LLM is unreachable, the error MUST propagate.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.lib.cli import (
    cmd_init,
)
from src.lib.session_tracker import (
    get_current_session,
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

    @pytest.mark.asyncio
    async def test_cursor_advances_per_file_success(self, initialized_project):
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import load_generation_cursor
        await setup_gaps(initialized_project, files=THREE_FILES)

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
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args)

        assert rc == 0
        # On full success, the cursor is cleared
        session = get_current_session(str(initialized_project))
        assert load_generation_cursor(session["session_dir"]) is None

    @pytest.mark.asyncio
    async def test_pause_persists_cursor_at_paused_file(self, initialized_project):
        """Batched pause: files 0 and 2 are generated in the same run; only
        file 1 (no edge cases) is deferred, recorded in the cursor."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import load_generation_cursor
        await setup_gaps(initialized_project, files=THREE_FILES)

        # Return edge_cases for files 0 and 2, empty for file 1
        edge_calls = [
            [{"scenario": "ok", "expected": "ok"}],  # file 0
            [],                                       # file 1 -> deferred
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
                   new_callable=AsyncMock, return_value=gen_result()), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args)

        from src.lib.session_tracker import EXIT_AWAITING_INPUT
        assert rc == EXIT_AWAITING_INPUT

        session = get_current_session(str(initialized_project))
        cursor = load_generation_cursor(session["session_dir"])
        assert cursor is not None
        # Files 0 and 2 completed in the same run (no per-file ping-pong)
        assert len(cursor["completed_files"]) == 2
        assert "OrderService.java" in cursor["completed_files"][0]
        assert "PaymentService.java" in cursor["completed_files"][1]
        # File 1 deferred, awaiting the answer
        deferred = cursor.get("deferred", [])
        assert len(deferred) == 1
        assert "UserController.java" in deferred[0]["source_file"]
        assert deferred[0]["reason"] == "missing_business_context"

    @pytest.mark.asyncio
    async def test_resume_skips_completed_files(self, initialized_project, tmp_path):
        """After a batched pause (files 0+2 done, file 1 deferred), resume
        must regenerate only the deferred file 1."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import load_generation_cursor
        await setup_gaps(initialized_project, files=THREE_FILES)

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
                   new_callable=AsyncMock, return_value=gen_result()), \
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
            return gen_result()

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
        # Only the deferred file 1 is regenerated; files 0 and 2 were already
        # completed in the first (batched) run
        assert len(gen_calls) == 1, f"expected 1 LLM call (file 1 only), got {gen_calls}"
        assert "UserController" in gen_calls[0]
        # Cursor cleared on completion
        assert load_generation_cursor(session_dir) is None

    @pytest.mark.asyncio
    async def test_resume_rejects_unsigned_answer(self, initialized_project, tmp_path, capsys):
        """P1.B — unsigned answer must be rejected, no LLM call."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import emit_question
        await setup_gaps(initialized_project, files=THREE_FILES)

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


# ============================================================================
# Phase 2 — Hints mode for compile-fix (2.1) + markdown_preview snapshot (2.4)
# ============================================================================
class TestBatchedQuestions:
    """P6.A/P6.B — one question per run, answers scoped per class."""

    @pytest.mark.asyncio
    async def test_one_question_for_multiple_uncertain_files(self, initialized_project):
        """P6.A — 3 files, 2 uncertain → ONE question.json with 2 items;
        the certain file IS generated in the same run."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.session_tracker import EXIT_AWAITING_INPUT
        await setup_gaps(initialized_project, files=THREE_FILES)

        # Edge cases only for file 2 (PaymentService); files 0 and 1 uncertain
        async def fake_edge(source_code, class_name, class_type):
            if class_name == "PaymentService":
                return [{"scenario": "ok", "expected": "ok"}]
            return []

        gen_calls: list[str] = []
        async def track_gen(**kwargs):
            gen_calls.append(kwargs.get("source_file", ""))
            return gen_result("PaymentService")

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new=AsyncMock(side_effect=fake_edge)), \
             patch("src.lib.bridge.generate_adaptive_tests", new=AsyncMock(side_effect=track_gen)), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args)

        assert rc == EXIT_AWAITING_INPUT
        # The certain file was generated in the same run
        assert len(gen_calls) == 1 and "PaymentService" in gen_calls[0]

        session = get_current_session(str(initialized_project))
        question = json.loads(
            (Path(session["session_dir"]) / "question.json").read_text()
        )
        assert question["kind"] == "batch"
        assert len(question["items"]) == 2
        classes = {it["subject"]["class_name"] for it in question["items"]}
        assert classes == {"OrderService", "UserController"}
        # Combined schema keyed per class
        assert set(question["answer_schema"]["test_requirements"].keys()) == classes

    @pytest.mark.asyncio
    async def test_answers_are_scoped_per_class(self, initialized_project, tmp_path):
        """P6.B — requirements answered for class X only reach X's prompt."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        await setup_gaps(initialized_project, files=THREE_FILES)

        # First run: everything uncertain → batch question
        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock):
            await _cmd_generate_async(gen_args)

        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        question = json.loads((session_dir / "question.json").read_text())

        # Answer ALL classes (so the run completes), with distinct scenarios
        signed = sign_answer(
            {"test_requirements": {
                "OrderService": [{"scenario": "order-specific rule", "expected": "x"}],
                "UserController": [{"scenario": "controller-specific rule", "expected": "y"}],
                "PaymentService": [{"scenario": "payment-specific rule", "expected": "z"}],
            }},
            question,
            str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        prompts_by_file: dict[str, list] = {}
        async def track_gen(**kwargs):
            src = kwargs.get("source_file", "")
            prompts_by_file[Path(src).stem] = kwargs.get("test_requirements") or []
            return gen_result(Path(src).stem)

        gen_args2 = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new=AsyncMock(side_effect=track_gen)), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args2)

        assert rc == 0
        order_reqs = [r["scenario"] for r in prompts_by_file["OrderService"]]
        assert order_reqs == ["order-specific rule"]
        controller_reqs = [r["scenario"] for r in prompts_by_file["UserController"]]
        assert controller_reqs == ["controller-specific rule"]

    @pytest.mark.asyncio
    async def test_crashed_resume_is_retryable(self, initialized_project, tmp_path):
        """P6.C — if the resume run crashes, question.json survives and the
        same answer file can be replayed."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        await setup_gaps(initialized_project, files=THREE_FILES)

        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=None,
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new_callable=AsyncMock):
            await _cmd_generate_async(gen_args)

        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        question = json.loads((session_dir / "question.json").read_text())
        signed = sign_answer(
            {"test_requirements": {
                "OrderService": [{"scenario": "s", "expected": "e"}],
                "UserController": [{"scenario": "s", "expected": "e"}],
                "PaymentService": [{"scenario": "s", "expected": "e"}],
            }},
            question, str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        # Resume crashes mid-run (LLM blows up)
        gen_args2 = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=None,
            fail_on_uncertainty=True, answer_file=str(answer),
        )
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new=AsyncMock(side_effect=RuntimeError("LLM exploded"))):
            rc = await _cmd_generate_async(gen_args2)

        assert rc == 1
        # The question is still pending, the answer was NOT consumed
        assert (session_dir / "question.json").exists()
        assert not (session_dir / "answer.json.consumed").exists()

        # Replay the SAME answer file → completes
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        async def ok_gen(**kwargs):
            return gen_result(Path(kwargs.get("source_file", "")).stem)
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases", new_callable=AsyncMock, return_value=[]), \
             patch("src.lib.bridge.generate_adaptive_tests", new=AsyncMock(side_effect=ok_gen)), \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _cmd_generate_async(gen_args2)

        assert rc == 0
        assert not (session_dir / "question.json").exists()
        assert (session_dir / "answer.json.consumed").exists()

    @pytest.mark.asyncio
    async def test_fixed_code_skips_regeneration(self, initialized_project, tmp_path):
        """P6.E — a deferred compile-fix answered with fixed_code is applied
        with ZERO generation LLM calls for that file."""
        from src.lib.cli import _cmd_generate_async
        from src.lib.integrity import sign_answer
        from src.lib.session_tracker import EXIT_AWAITING_INPUT
        await setup_gaps(initialized_project, files=THREE_FILES)

        # First run: only OrderService targeted (files filter), compile-fix
        # exhausts → deferred with its test_path recorded in the cursor
        gen_args = argparse.Namespace(
            project_path=str(initialized_project),
            verbose=False, files=["OrderService.java"],
            fail_on_uncertainty=True, answer_file=None,
        )
        fix_outputs = iter([
            "package c;\n// fix 1\nclass OrderServiceTest {}",
            "package c;\n// fix 2\nclass OrderServiceTest {}",
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
                   new_callable=AsyncMock, return_value=gen_result("OrderService")), \
             patch("src.lib.bridge.fix_compilation_errors", new=AsyncMock(side_effect=fake_fix)), \
             patch("subprocess.run", return_value=failing_compile()):
            rc = await _cmd_generate_async(gen_args)
        assert rc == EXIT_AWAITING_INPUT

        session = get_current_session(str(initialized_project))
        session_dir = Path(session["session_dir"])
        question = json.loads((session_dir / "question.json").read_text())
        assert question["kind"] == "compilation_fix_exhausted"

        dev_code = (
            "package c;\nimport org.junit.jupiter.api.Test;\n"
            "class OrderServiceTest {\n  @Test void developer_fix() {}\n}\n"
        )
        signed = sign_answer(
            {"compile_fixes": {"OrderService": {"fixed_code": dev_code}}},
            question, str(initialized_project),
        )
        answer = tmp_path / "answer.json"
        answer.write_text(json.dumps(signed))

        # Resume via cmd_resume (also exercises the files_filter replay).
        # cmd_resume is sync and calls asyncio.run internally → run it in a
        # thread since this test already sits inside an event loop.
        import asyncio as _asyncio

        from src.lib.cli import cmd_resume
        mock_compile = MagicMock(returncode=0, stdout="", stderr="")
        with patch("src.lib.startup_checks.check_llm_connection", new_callable=AsyncMock), \
             patch("src.lib.bridge.analyze_edge_cases",
                   new_callable=AsyncMock, return_value=[]) as mock_edge, \
             patch("src.lib.bridge.generate_adaptive_tests",
                   new_callable=AsyncMock) as mock_gen, \
             patch("subprocess.run", return_value=mock_compile):
            rc = await _asyncio.to_thread(cmd_resume, argparse.Namespace(
                project_path=str(initialized_project),
                answer_file=str(answer), verbose=False,
            ))

        assert rc == 0
        # ZERO generation LLM calls: the dev's code was applied directly
        mock_gen.assert_not_called()
        mock_edge.assert_not_called()
        test_file = (initialized_project / "src" / "test" / "java" / "com"
                     / "example" / "OrderServiceTest.java")
        assert "developer_fix" in test_file.read_text()


class TestResumeDispatch:
    """Resume must dispatch to the step recorded in the pending question."""

    def _plant_question(self, project_path, step):
        from src.lib.session_tracker import emit_question
        cmd_init(argparse.Namespace(
            project_path=str(project_path), name=None, description="", tech="java-spring",
        ))
        session = get_current_session(str(project_path))
        emit_question(
            session["session_dir"], step,
            {"kind": "x", "question": "?"},
            project_path=str(project_path), session_id=session["session_id"],
        )

    def test_dispatches_to_validate(self, tmp_path):
        from src.lib.cli import cmd_resume
        self._plant_question(tmp_path, "validation")
        seen = {}
        def fake(args):
            seen["fail_on_uncertainty"] = args.fail_on_uncertainty
            seen["answer_file"] = args.answer_file
            return 0
        with patch("src.lib.cli.cmd_validate", side_effect=fake):
            rc = cmd_resume(argparse.Namespace(
                project_path=str(tmp_path), answer_file="/tmp/a.json", verbose=False,
            ))
        assert rc == 0
        assert seen == {"fail_on_uncertainty": True, "answer_file": "/tmp/a.json"}

    def test_dispatches_to_killer(self, tmp_path):
        from src.lib.cli import cmd_resume
        self._plant_question(tmp_path, "killer-tests")
        with patch("src.lib.cli.cmd_killer", return_value=0) as mock_killer:
            rc = cmd_resume(argparse.Namespace(
                project_path=str(tmp_path), answer_file="/tmp/a.json", verbose=False,
            ))
        assert rc == 0
        assert mock_killer.call_args.args[0].max_tests == 10

    def test_unknown_step_errors(self, tmp_path, capsys):
        from src.lib.cli import cmd_resume
        self._plant_question(tmp_path, "mutation")
        rc = cmd_resume(argparse.Namespace(
            project_path=str(tmp_path), answer_file="/tmp/a.json", verbose=False,
        ))
        assert rc == 1
        assert "not yet wired" in capsys.readouterr().err

    def test_answer_without_pending_question(self, tmp_path, capsys):
        from src.lib.cli import cmd_resume
        cmd_init(argparse.Namespace(
            project_path=str(tmp_path), name=None, description="", tech="java-spring",
        ))
        rc = cmd_resume(argparse.Namespace(
            project_path=str(tmp_path), answer_file="/tmp/a.json", verbose=False,
        ))
        assert rc == 1
        assert "no pending question" in capsys.readouterr().err
