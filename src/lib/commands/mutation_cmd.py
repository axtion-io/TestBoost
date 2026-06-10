# SPDX-License-Identifier: Apache-2.0
"""testboost mutate + killer — mutation testing and killer tests."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from src.lib.commands._shared import (
    _extract_json_field,
    _read_step_status,
    load_answer_for_step,
)
from src.lib.commands.generate_cmd import _attempt_compile_fix


def cmd_mutate(args: argparse.Namespace) -> int:
    """Run mutation testing and analyze results."""
    return asyncio.run(_cmd_mutate_async(args))


async def _cmd_mutate_async(args: argparse.Namespace) -> int:
    from src.lib.md_logger import MdLogger
    from src.lib.session_tracker import (
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_IN_PROGRESS,
        get_current_session,
        update_step_file,
    )

    project_path = args.project_path
    session = get_current_session(project_path)

    if not session:
        print("Error: No active session. Run `init` first.", file=sys.stderr)
        return 1

    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "mutation", verbose=getattr(args, "verbose", False))

    # Check prerequisites: validation must have passed
    val_file = Path(session_dir) / "validation.md"
    if not val_file.exists():
        logger.error("Validation step not completed. Run `validate` first.")
        return 1
    val_status = _read_step_status(val_file)
    if val_status != "completed":
        logger.error(
            f"Validation step has status '{val_status}'. "
            "Tests must pass before running mutation testing. "
            "Fix the failing tests and re-run `validate`."
        )
        return 1

    update_step_file(session_dir, "mutation", STATUS_IN_PROGRESS, "# Mutation Testing\n\nRunning PIT...")

    try:
        from src.lib.bridge import analyze_mutants, run_mutation_testing

        # Build PIT arguments
        pit_kwargs: dict[str, Any] = {}
        if hasattr(args, "target_classes") and args.target_classes:
            pit_kwargs["target_classes"] = args.target_classes
        if hasattr(args, "target_tests") and args.target_tests:
            pit_kwargs["target_tests"] = args.target_tests
        min_score = getattr(args, "min_score", 80)

        # Step 1: Run mutation testing
        logger.info("Running PIT mutation testing...")
        pit_result_json = await run_mutation_testing(project_path, **pit_kwargs)
        pit_result = json.loads(pit_result_json)

        if not pit_result.get("success"):
            error_msg = pit_result.get("error", "PIT execution failed")
            logger.error(f"Mutation testing failed: {error_msg}")
            content = f"# Mutation Testing - FAILED\n\n**Error**: {error_msg}\n"
            if pit_result.get("output"):
                content += f"\n### PIT Output\n\n```\n{pit_result['output'][-3000:]}\n```\n"
            update_step_file(session_dir, "mutation", STATUS_FAILED, content)
            logger.result("Mutation Testing Failed", content)
            return 1

        mutation_score = pit_result.get("mutation_score", 0)
        mutations = pit_result.get("mutations", {})
        surviving = pit_result.get("surviving_mutants", [])

        logger.info(
            f"PIT complete: score={mutation_score}%, "
            f"killed={mutations.get('killed', 0)}, "
            f"survived={mutations.get('survived', 0)}, "
            f"total={mutations.get('total', 0)}"
        )

        # Step 2: Analyze mutants
        logger.info("Analyzing mutation results...")
        report_path = pit_result.get("report_path")
        analysis_json = await analyze_mutants(
            project_path, report_path=report_path, min_score=min_score,
        )
        analysis = json.loads(analysis_json)

        # Build report
        content = "# Mutation Testing Results\n\n"
        content += f"**Mutation score**: {mutation_score}%\n"
        content += f"**Threshold**: {min_score}%\n"
        content += f"**Meets threshold**: {'Yes' if analysis.get('meets_threshold') else 'No'}\n\n"

        content += "## Summary\n\n"
        content += "| Metric | Count |\n"
        content += "|--------|-------|\n"
        content += f"| Total mutants | {mutations.get('total', 0)} |\n"
        content += f"| Killed | {mutations.get('killed', 0)} |\n"
        content += f"| Survived | {mutations.get('survived', 0)} |\n"
        content += f"| No coverage | {mutations.get('no_coverage', 0)} |\n"
        content += f"| Timed out | {mutations.get('timed_out', 0)} |\n\n"

        # By-class breakdown
        by_class = pit_result.get("by_class", [])
        if by_class:
            content += "## Mutation Score by Class\n\n"
            content += "| Class | Killed | Total | Score |\n"
            content += "|-------|--------|-------|-------|\n"
            for cls in by_class:
                cls_name = cls["class"].split(".")[-1]
                content += f"| `{cls_name}` | {cls['killed']} | {cls['total']} | {cls['score']}% |\n"
            content += "\n"

        # Hard-to-kill patterns
        hard_to_kill = analysis.get("hard_to_kill", [])
        if hard_to_kill:
            content += "## Hard-to-Kill Mutant Patterns\n\n"
            for pattern in hard_to_kill:
                content += f"### {pattern['mutator']} ({pattern['count']} surviving)\n\n"
                for ex in pattern.get("examples", []):
                    content += f"- `{ex['class']}.{ex['method']}` line {ex['line']}: {ex['description']}\n"
                content += "\n"

        # Recommendations
        recommendations = analysis.get("recommendations", [])
        if recommendations:
            content += "## Recommendations\n\n"
            for rec in recommendations:
                content += f"- {rec}\n"
            content += "\n"

        # Priority improvements
        priorities = analysis.get("priority_improvements", [])
        if priorities:
            content += "## Priority Improvements\n\n"
            content += "| Class | Method | Type | Count | Action |\n"
            content += "|-------|--------|------|-------|--------|\n"
            for p in priorities:
                content += f"| `{p['class']}` | `{p['method']}` | {p['type']} | {p['count']} | {p['action']} |\n"
            content += "\n"

        if surviving:
            content += f"\n**{len(surviving)} surviving mutants** can be targeted with `/testboost.killer`.\n"

        update_step_file(
            session_dir, "mutation", STATUS_COMPLETED, content,
            data={
                "mutation_score": mutation_score,
                "meets_threshold": analysis.get("meets_threshold", False),
                "mutations": mutations,
                "surviving_mutants": surviving,
                "report_path": report_path,
                "recommendations": recommendations,
            },
        )

        logger.result("Mutation Testing Complete", content)

        from src.lib.integrity import emit_token
        emit_token(project_path, "mutation", session["session_id"])
        return 0

    except Exception as e:
        logger.error(f"Mutation testing failed: {e}")
        update_step_file(
            session_dir, "mutation", STATUS_FAILED,
            f"# Mutation Testing - FAILED\n\n**Error**: {e}\n",
        )
        return 1
def cmd_killer(args: argparse.Namespace) -> int:
    """Generate killer tests for surviving mutants."""
    return asyncio.run(_cmd_killer_async(args))


async def _cmd_killer_async(args: argparse.Namespace) -> int:
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
    logger = MdLogger(session_dir, "killer-tests", verbose=getattr(args, "verbose", False))

    # --- Human-in-the-loop: verify answer file if provided (finalized on success) ---
    answer_payload, abort = load_answer_for_step(
        session_dir, getattr(args, "answer_file", None), project_path, logger
    )
    if abort is not None:
        return abort

    fail_on_uncertainty = bool(getattr(args, "fail_on_uncertainty", False))
    killer_hints = (
        answer_payload.get("killer_hints", {})
        if isinstance(answer_payload, dict) else {}
    )

    # Check prerequisites: mutation step must have passed
    mutation_file = Path(session_dir) / "mutation.md"
    if not mutation_file.exists():
        logger.error("Mutation testing step not completed. Run `mutate` first.")
        return 1
    mutation_status = _read_step_status(mutation_file)
    if mutation_status != "completed":
        logger.error(
            f"Mutation step has status '{mutation_status}'. "
            "Mutation testing must succeed before generating killer tests. "
            "Fix the issue and re-run `mutate`."
        )
        return 1

    update_step_file(
        session_dir, "killer-tests", STATUS_IN_PROGRESS,
        "# Killer Tests\n\nGenerating tests to kill surviving mutants...",
    )

    try:
        # Read surviving mutants from mutation step
        mutation_content = mutation_file.read_text(encoding="utf-8")
        surviving_mutants = _extract_json_field(mutation_content, "surviving_mutants")

        # Distinguish None (missing data / corrupt file) from [] (genuinely zero survivors)
        if surviving_mutants is None:
            logger.error(
                "Could not read surviving_mutants from mutation.md. "
                "The mutation step may have been corrupted. Re-run `mutate`."
            )
            update_step_file(
                session_dir, "killer-tests", STATUS_FAILED,
                "# Killer Tests - FAILED\n\n"
                "**Error**: No surviving_mutants data found in mutation.md. Re-run `mutate`.\n",
            )
            return 1

        if len(surviving_mutants) == 0:
            logger.info("No surviving mutants found. All mutants already killed!")
            update_step_file(
                session_dir, "killer-tests", STATUS_COMPLETED,
                "# Killer Tests\n\nNo surviving mutants — mutation score is already perfect.\n",
            )
            from src.lib.integrity import emit_token
            emit_token(project_path, "killer-tests", session["session_id"])
            return 0

        max_tests = getattr(args, "max_tests", 10)
        logger.info(f"Generating killer tests for {len(surviving_mutants)} surviving mutants (max {max_tests})...")

        # Verify LLM connectivity
        from src.lib.bridge import generate_killer_tests
        from src.lib.startup_checks import check_llm_connection
        try:
            await check_llm_connection()
        except Exception as e:
            logger.error(f"LLM connection failed: {e}")
            print(f"\nERROR: Cannot connect to LLM provider. {e}")
            return 1

        if killer_hints:
            logger.info(f"Injecting {len(killer_hints)} developer hint(s) into killer generation")
        result_json = await generate_killer_tests(
            project_path, surviving_mutants, max_tests=max_tests,
            hints=killer_hints if killer_hints else None,
        )
        result = json.loads(result_json)

        if not result.get("success"):
            error_msg = result.get("error", "Killer test generation failed")
            logger.error(f"Generation failed: {error_msg}")
            update_step_file(
                session_dir, "killer-tests", STATUS_FAILED,
                f"# Killer Tests - FAILED\n\n**Error**: {error_msg}\n",
            )
            return 1

        generated_tests = result.get("generated_tests", [])

        # --- HITL trigger: no killer tests produced + flag on → pause.
        # Pauses again even when hints were provided (the hints didn't work);
        # the new question shows which hints were already tried.
        if not generated_tests and fail_on_uncertainty:
            top_survivors = surviving_mutants[:10]
            if answer_payload is not None:
                finalize_answer(session_dir, answer_payload)
            question_text = (
                f"Killer-test generation produced 0 tests for "
                f"{len(surviving_mutants)} surviving mutants. "
                f"Provide hints about what these mutants represent or how to kill them."
            )
            if killer_hints:
                question_text += (
                    f" (Note: {len(killer_hints)} previous hint(s) were applied "
                    f"and still yielded nothing — try being more specific.)"
                )
            qpath = emit_question(
                session_dir, "killer-tests",
                {
                    "kind": "killer_generation_yielded_nothing",
                    "subject": {
                        "surviving_mutant_count": len(surviving_mutants),
                        "top_survivors": top_survivors,
                        "previous_hints": killer_hints or None,
                    },
                    "question": question_text,
                    "answer_schema": {
                        "killer_hints": {
                            "<ClassName.methodName>": "natural-language hint for the LLM"
                        }
                    },
                },
                project_path=project_path,
                session_id=session["session_id"],
            )
            raise AwaitingInputError(qpath, "killer-tests")

        # Write killer test files
        content = "# Killer Test Generation Results\n\n"
        content += f"**Surviving mutants targeted**: {result.get('total_mutants_targeted', 0)}\n"
        content += f"**Test classes generated**: {len(generated_tests)}\n"
        content += f"**Total test methods**: {result.get('total_tests', 0)}\n\n"

        if generated_tests:
            content += "## Generated Killer Tests\n\n"
            content += "| # | Class | Test File | Mutants Targeted |\n"
            content += "|---|-------|-----------|------------------|\n"

            written_files = []
            for i, test in enumerate(generated_tests, 1):
                class_name = test.get("class", "").split(".")[-1]
                test_path = test.get("test_file", "")
                test_code = test.get("test_code", "")
                mutants_targeted = test.get("mutants_targeted", 0)

                content += f"| {i} | `{class_name}` | `{test_path}` | {mutants_targeted} |\n"

                # Write test file to disk
                if test_path and test_code:
                    full_path = Path(project_path) / test_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(test_code, encoding="utf-8")
                    logger.info(f"Wrote killer test: {test_path}")
                    written_files.append((full_path, test))

            content += "\n"

            # Compile-and-fix loop for killer tests
            maven_compile_cmd = None
            from src.lib.session_tracker import read_project_analysis_data
            project_data = read_project_analysis_data(project_path)
            if project_data:
                maven_compile_cmd = project_data.get("maven_compile_cmd")

            for full_path, test in written_files:
                class_name = test.get("class", "").split(".")[-1]
                fixed, _exhausted = await _attempt_compile_fix(
                    project_path, full_path, test.get("test_code", ""),
                    class_name, logger, session_dir, maven_compile_cmd,
                )
                if fixed != test.get("test_code", ""):
                    test["test_code"] = fixed

            content += "## Next Steps\n\n"
            content += "1. Run `/testboost.validate` to compile and execute the killer tests\n"
            content += "2. Run `/testboost.mutate` again to verify the mutation score improved\n"

        update_step_file(
            session_dir, "killer-tests", STATUS_COMPLETED, content,
            data={
                "generated_tests": [
                    {k: v for k, v in t.items() if k != "test_code"}
                    for t in generated_tests
                ],
                "total_mutants_targeted": result.get("total_mutants_targeted", 0),
                "total_tests": result.get("total_tests", 0),
            },
        )

        logger.result("Killer Test Generation Complete", content)

        if answer_payload is not None:
            finalize_answer(session_dir, answer_payload)

        from src.lib.integrity import emit_token
        emit_token(project_path, "killer-tests", session["session_id"])
        return 0

    except AwaitingInputError as wait:
        logger.info(f"Killer-tests paused — awaiting human input ({wait.question_path})")
        print(f"[TESTBOOST_AWAITING_INPUT:step=killer-tests:question={wait.question_path}]")
        return EXIT_AWAITING_INPUT
    except Exception as e:
        logger.error(f"Killer test generation failed: {e}")
        update_step_file(
            session_dir, "killer-tests", STATUS_FAILED,
            f"# Killer Tests - FAILED\n\n**Error**: {e}\n",
        )
        return 1
