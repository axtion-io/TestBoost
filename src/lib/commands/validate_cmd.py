# SPDX-License-Identifier: Apache-2.0
"""testboost validate — compile and run generated tests."""

import argparse
import asyncio
import re
import subprocess
import sys
from pathlib import Path

from src.lib.commands._shared import _extract_json_field, load_answer_for_step


def _guess_failing_class(line: str) -> str | None:
    """Best-effort extraction of a test class name from a JUnit/Maven failure line.

    Handles patterns like 'OrderServiceTest.someMethod', 'FAILED ... OrderServiceTest',
    and 'at com.example.OrderServiceTest.someMethod(...)'. Returns None if no
    Test/Tests suffix is recognised.
    """
    m = re.search(r"([A-Z][A-Za-z0-9_]*Tests?)\b", line)
    return m.group(1) if m else None
def cmd_validate(args: argparse.Namespace) -> int:
    """Compile and validate generated tests."""
    return asyncio.run(_cmd_validate_async(args))


async def _cmd_validate_async(args: argparse.Namespace) -> int:
    from src.lib.md_logger import MdLogger
    from src.lib.session_tracker import (
        EXIT_AWAITING_INPUT,
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_IN_PROGRESS,
        AwaitingInputError,
        emit_question,
        finalize_answer,
        get_current_session,
        update_step_file,
    )

    project_path = args.project_path
    session = get_current_session(project_path)

    if not session:
        print("Error: No active session. Run `init` first.", file=sys.stderr)
        return 1

    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "validation", verbose=getattr(args, "verbose", False))

    # Check prerequisites
    gen_file = Path(session_dir) / "generation.md"
    if not gen_file.exists():
        logger.error("Generation step not completed. Run `generate` first.")
        return 1

    update_step_file(session_dir, "validation", STATUS_IN_PROGRESS, "# Validation\n\nCompiling and testing...")

    # --- Human-in-the-loop: verify answer file if provided (finalized on success) ---
    answer_payload, abort = load_answer_for_step(
        session_dir, getattr(args, "answer_file", None), project_path, logger
    )
    if abort is not None:
        return abort

    fail_on_uncertainty = bool(getattr(args, "fail_on_uncertainty", False))
    validate_fixes = (
        answer_payload.get("validate_fixes", {})
        if isinstance(answer_payload, dict) else {}
    )

    try:
        # Resolve plugin for this session's technology
        from pathlib import Path as _Path

        from src.lib.bridge import get_plugin_for_session

        plugin = get_plugin_for_session(project_path)

        # Build session_config from analysis.md (allows profile/property customization)
        session_config: dict = {}
        analysis_file = Path(session_dir) / "analysis.md"
        if analysis_file.exists():
            analysis_content = analysis_file.read_text(encoding="utf-8")
            maven_compile_cmd = _extract_json_field(analysis_content, "maven_compile_cmd")
            maven_test_cmd = _extract_json_field(analysis_content, "maven_test_cmd")
            if maven_compile_cmd:
                session_config["maven_compile_cmd"] = maven_compile_cmd
            if maven_test_cmd:
                session_config["maven_test_cmd"] = maven_test_cmd

        compile_cmd_tpl = plugin.validation_command(_Path(project_path), session_config)
        test_run_cmd_tpl = plugin.test_run_command(_Path(project_path), session_config)

        # Collect generated test files from the generation step
        gen_content = gen_file.read_text(encoding="utf-8")
        generated_files = _extract_json_field(gen_content, "generated") or []
        test_file_paths = [g["path"] for g in generated_files if g.get("path")]

        # Apply developer-provided test fixes from the answer payload
        if isinstance(validate_fixes, dict) and validate_fixes:
            for g in generated_files:
                cls = g.get("class_name") or Path(g.get("path", "")).stem
                fix = validate_fixes.get(cls)
                if isinstance(fix, dict) and "fixed_code" in fix:
                    target = Path(project_path) / g["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(fix["fixed_code"], encoding="utf-8")
                    logger.info(f"Applied developer-provided validate fix for {cls}")

        # Helper: substitute {test_file} placeholder or run as-is
        def _expand_cmd(cmd_tpl: list[str], test_file: str) -> list[str]:
            return [part.replace("{test_file}", test_file) for part in cmd_tpl]

        has_placeholder = any("{test_file}" in part for part in compile_cmd_tpl)

        content = "# Validation Results\n\n"
        content += f"- **Compile**: `{' '.join(compile_cmd_tpl)}`\n"
        content += f"- **Test**: `{' '.join(test_run_cmd_tpl)}`\n\n"

        # Step 1: Compile tests
        compile_failed = False
        if has_placeholder:
            # Per-file validation (Python, Go, etc.)
            for tf in test_file_paths:
                compile_cmd = _expand_cmd(compile_cmd_tpl, tf)
                logger.info(f"Validating: {' '.join(compile_cmd)}")
                compile_result = subprocess.run(
                    compile_cmd, cwd=project_path, capture_output=True, text=True, timeout=120,
                )
                if compile_result.returncode != 0:
                    content += f"## Compilation: FAILED (`{tf}`)\n\n"
                    content += f"```\n{(compile_result.stdout + compile_result.stderr)[-2000:]}\n```\n"
                    logger.error(f"Validation failed for {tf}")
                    compile_failed = True
        else:
            # Whole-project validation (Java/Maven)
            compile_cmd = compile_cmd_tpl
            logger.info(f"Compiling tests: {' '.join(compile_cmd)}")
            compile_result = subprocess.run(
                compile_cmd, cwd=project_path, capture_output=True, text=True, timeout=120,
            )
            if compile_result.returncode != 0:
                from src.lib.bridge import parse_maven_errors

                parser, errors = parse_maven_errors(compile_result.stdout + compile_result.stderr)

                content += "## Compilation: FAILED\n\n"
                if errors:
                    content += parser.format_for_llm(errors)
                    summary = parser.get_summary(errors)
                    logger.error(f"Compilation failed: {summary['total_errors']} errors")
                    logger.data("Errors by type", summary["errors_by_type"])
                else:
                    content += f"```\n{compile_result.stderr[-2000:]}\n```\n"
                    logger.error("Compilation failed (no structured errors parsed)")
                compile_failed = True

        if compile_failed:
            update_step_file(
                session_dir, "validation", STATUS_FAILED, content,
                data={"compilation": "failed"},
            )
            logger.result("Validation: Compilation Failed", content)
            return 1

        logger.info("Compilation successful")
        content += "## Compilation: PASSED\n\n"

        # Step 2: Run tests
        has_test_placeholder = any("{test_file}" in part for part in test_run_cmd_tpl)
        test_timeout = 300  # 5 minutes

        if has_test_placeholder:
            # Per-file test execution (Python, Go, etc.)
            all_output = ""
            final_returncode = 0
            for tf in test_file_paths:
                test_run_cmd = _expand_cmd(test_run_cmd_tpl, tf)
                logger.info(f"Running tests: {' '.join(test_run_cmd)}")
                test_result = subprocess.run(
                    test_run_cmd, cwd=project_path, capture_output=True, text=True, timeout=test_timeout,
                )
                all_output += test_result.stdout + test_result.stderr + "\n"
                if test_result.returncode != 0:
                    final_returncode = test_result.returncode
            test_output = all_output
            test_returncode = final_returncode
        else:
            # Whole-project test execution (Java/Maven)
            test_run_cmd = test_run_cmd_tpl
            logger.info(f"Running tests: {' '.join(test_run_cmd)}")
            test_result = subprocess.run(
                test_run_cmd, cwd=project_path, capture_output=True, text=True, timeout=test_timeout,
            )
            test_output = test_result.stdout + test_result.stderr
            test_returncode = test_result.returncode

        if test_returncode == 0:
            content += "## Tests: PASSED\n\n"
            content += "All tests passed successfully.\n\n"

            # Try to extract test counts from Maven output
            test_count_match = re.search(r"Tests run: (\d+)", test_output)
            if test_count_match:
                content += f"**Tests run**: {test_count_match.group(1)}\n"

            logger.info("All tests passed")
            status = STATUS_COMPLETED
        else:
            content += "## Tests: FAILED\n\n"

            # Extract failure details
            failure_lines = [
                ln for ln in test_output.split("\n")
                if "FAIL" in ln or "ERROR" in ln or "Tests run:" in ln
            ]
            if failure_lines:
                content += "### Failure Details\n\n```\n"
                content += "\n".join(failure_lines[-20:])
                content += "\n```\n\n"

            content += "### Full Output\n\n"
            content += f"```\n{test_output[-3000:]}\n```\n"

            logger.error("Some tests failed")

            # --- HITL trigger: pause if asked, instead of marking failed ---
            if fail_on_uncertainty:
                failing_classes = sorted({
                    _guess_failing_class(ln) for ln in failure_lines
                    if _guess_failing_class(ln)
                })
                stack_trace = "\n".join(failure_lines[-30:])
                # A new question supersedes the answered one
                if answer_payload is not None:
                    finalize_answer(session_dir, answer_payload)
                qpath = emit_question(
                    session_dir,
                    "validation",
                    {
                        "kind": "tests_failed_at_runtime",
                        "subject": {
                            "failing_classes": failing_classes,
                            "command": " ".join(test_run_cmd_tpl),
                        },
                        "question": (
                            f"{len(failing_classes) or '?'} test class(es) failed at runtime. "
                            f"Review the stack trace and provide fixed code."
                        ),
                        "stack_trace": stack_trace,
                        # Only fixed_code is applied by validate — natural-language
                        # hints are a generate-step (compile_fixes) feature.
                        "answer_schema": {
                            "validate_fixes": {
                                "<TestClassName>": {
                                    "fixed_code": "string (full test file content)",
                                }
                            }
                        },
                    },
                    project_path=project_path,
                    session_id=session["session_id"],
                )
                raise AwaitingInputError(qpath, "validation")

            status = STATUS_FAILED

        update_step_file(
            session_dir, "validation", status, content,
            data={
                "compilation": "passed",
                "tests": "passed" if test_returncode == 0 else "failed",
                "return_code": test_returncode,
            },
        )

        logger.result("Validation Results", content)

        if test_returncode == 0:
            if answer_payload is not None:
                finalize_answer(session_dir, answer_payload)
            from src.lib.integrity import emit_token
            emit_token(project_path, "validation", session["session_id"])
        return 0 if test_returncode == 0 else 1

    except AwaitingInputError as wait:
        logger.info(f"Validation paused — awaiting human input ({wait.question_path})")
        print(f"[TESTBOOST_AWAITING_INPUT:step=validation:question={wait.question_path}]")
        return EXIT_AWAITING_INPUT
    except subprocess.TimeoutExpired:
        logger.error(f"Maven timed out after {test_timeout}s")
        update_step_file(
            session_dir, "validation", STATUS_FAILED,
            "# Validation - FAILED\n\n**Error**: Maven timed out.\n",
        )
        return 1
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        update_step_file(
            session_dir, "validation", STATUS_FAILED,
            f"# Validation - FAILED\n\n**Error**: {e}\n",
        )
        return 1
