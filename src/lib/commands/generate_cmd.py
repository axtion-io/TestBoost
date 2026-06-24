# SPDX-License-Identifier: Apache-2.0
"""testboost generate — LLM test generation with HITL pause/resume."""

import argparse
import asyncio
import json
import shutil
import subprocess
import sys
from pathlib import Path

from src.lib.commands._shared import (
    _extract_json_field,
    _warn_maven_config_issue,
    load_answer_for_step,
)


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate tests for identified gaps."""
    return asyncio.run(_cmd_generate_async(args))


async def _cmd_generate_async(args: argparse.Namespace) -> int:
    from src.lib.md_logger import MdLogger
    from src.lib.session_tracker import (
        EXIT_AWAITING_INPUT,
        STATUS_COMPLETED,
        STATUS_FAILED,
        STATUS_IN_PROGRESS,
        AwaitingInputError,
        clear_generation_cursor,
        emit_question,
        finalize_answer,
        get_current_session,
        load_generation_cursor,
        save_generation_cursor,
        update_step_file,
    )

    project_path = args.project_path
    session = get_current_session(project_path)

    if not session:
        print("Error: No active session. Run `init` first.", file=sys.stderr)
        return 1

    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "generation", verbose=getattr(args, "verbose", False))

    # Check prerequisites
    gaps_file = Path(session_dir) / "coverage-gaps.md"
    if not gaps_file.exists():
        logger.error("Coverage gaps step not completed. Run `gaps` first.")
        return 1

    update_step_file(session_dir, "generation", STATUS_IN_PROGRESS, "# Test Generation\n\nGenerating...")

    # --- Human-in-the-loop: verify answer file if provided (finalized on success) ---
    answer_payload, abort = load_answer_for_step(
        session_dir, getattr(args, "answer_file", None), project_path, logger
    )
    if abort is not None:
        return abort

    fail_on_uncertainty = bool(getattr(args, "fail_on_uncertainty", False))

    try:
        # Extract gaps from the coverage-gaps.md
        gaps_content = gaps_file.read_text(encoding="utf-8")
        gaps = _extract_json_field(gaps_content, "gaps")

        if not gaps:
            logger.info("No coverage gaps found. Nothing to generate.")
            update_step_file(
                session_dir, "generation", STATUS_COMPLETED,
                "# Test Generation\n\nNo gaps to fill - all source files have tests.\n",
            )
            return 0

        # Load analysis data: project-level for class_index/test_examples/conventions,
        # session-level for maven command overrides (allows per-session customization).
        from src.lib.session_tracker import read_project_analysis_data
        class_index = None
        test_examples = None
        conventions = None
        maven_compile_cmd = None
        maven_test_cmd = None

        project_data = read_project_analysis_data(project_path)
        if project_data:
            class_index = project_data.get("class_index")
            test_examples = project_data.get("test_examples")
            conventions = project_data.get("conventions")
            maven_compile_cmd = project_data.get("maven_compile_cmd")
            maven_test_cmd = project_data.get("maven_test_cmd")
        else:
            logger.warn(
                "No project-level class index found. Re-run `analyze` to build it "
                "for improved generation quality. Falling back to lazy dependency loading."
            )

        # Session analysis overrides (maven commands edited by user take priority)
        analysis_file = Path(session_dir) / "analysis.md"
        if analysis_file.exists():
            analysis_content = analysis_file.read_text(encoding="utf-8")
            session_conventions = _extract_json_field(analysis_content, "conventions")
            session_compile_cmd = _extract_json_field(analysis_content, "maven_compile_cmd")
            session_test_cmd = _extract_json_field(analysis_content, "maven_test_cmd")
            if session_conventions:
                conventions = session_conventions
            if session_compile_cmd:
                maven_compile_cmd = session_compile_cmd
            if session_test_cmd:
                maven_test_cmd = session_test_cmd

        # Apply file filter if specified
        target_files = gaps
        if hasattr(args, "files") and args.files:
            # Normalize separators so "src/main/..." matches "src\main\..." on Windows
            normalized_patterns = [p.replace("\\", "/") for p in args.files]
            target_files = [
                f for f in gaps
                if any(pattern in f.replace("\\", "/") for pattern in normalized_patterns)
            ]
            if not target_files:
                logger.warn(f"No files matched filter: {args.files}")
                target_files = gaps

        logger.info(f"Generating tests for {len(target_files)} files...")

        # Resolve plugin for prompt template directory
        from src.lib.bridge import get_plugin_for_session
        plugin = get_plugin_for_session(project_path)
        prompt_template_dir = plugin.prompt_template_dir

        # Runtime auto-fix runs `mvn test -Dtest=<class>` after a clean compile,
        # so it only applies to the Maven/Java plugin. Opt out with --no-runtime-fix.
        runtime_fix_enabled = (
            not getattr(args, "no_runtime_fix", False)
            and (plugin is None or plugin.identifier == "java-spring")
        )

        # --- Reuse existing TestBoost test generation via bridge ---
        # Verify LLM connectivity before generating tests
        from src.lib.bridge import (
            analyze_edge_cases,
            generate_adaptive_tests,
        )
        from src.lib.startup_checks import check_llm_connection
        try:
            await check_llm_connection()
        except Exception as e:
            logger.error(f"LLM connection failed: {e}")
            print(f"\nERROR: Cannot connect to LLM provider. {e}")
            print("Check your LLM provider credentials in .env (see .env.example).")
            return 1

        # --- Per-file cursor: resume from where a previous run paused ---
        cursor = load_generation_cursor(session_dir)
        if cursor and cursor.get("target_files") == target_files:
            completed_files = list(cursor.get("completed_files", []))
            prior_deferred = {
                d.get("source_file"): d for d in cursor.get("deferred", [])
                if isinstance(d, dict)
            }
            if completed_files or prior_deferred:
                logger.info(
                    f"Resuming: {len(completed_files)} file(s) already completed, "
                    f"{len(prior_deferred)} deferred"
                )
        else:
            if cursor:
                logger.warn("Cursor target_files mismatch — starting fresh")
            completed_files = []
            prior_deferred = {}
        files_filter = list(args.files) if getattr(args, "files", None) else None
        save_generation_cursor(
            session_dir,
            target_files=target_files,
            current_index=len(completed_files),
            completed_files=completed_files,
            files_filter=files_filter,
        )

        compile_fixes = (
            answer_payload.get("compile_fixes", {})
            if isinstance(answer_payload, dict) else {}
        )
        if not isinstance(compile_fixes, dict):
            compile_fixes = {}
        answered_requirements = (
            answer_payload.get("test_requirements", {})
            if isinstance(answer_payload, dict) else {}
        )

        # Uncertainties are collected across the whole run and emitted as ONE
        # question at the end, so the developer answers a single MR comment
        # instead of one round-trip per file.
        uncertainties: list[dict] = []
        deferred_out: list[dict] = []

        generated: list[dict] = []
        for i, source_file in enumerate(target_files):
            if source_file in completed_files:
                continue

            logger.info(
                f"Generating tests for: {source_file}  (file {i + 1}/{len(target_files)})"
            )
            class_name = Path(source_file).stem
            class_type = "service"

            # Requirements answered for this class. A dict is keyed per class;
            # a bare list is the legacy global form (applies to every file).
            if isinstance(answered_requirements, dict):
                injected = list(answered_requirements.get(class_name, []))
            elif isinstance(answered_requirements, list):
                injected = list(answered_requirements)
            else:
                injected = []

            try:
                # --- Fast path: a deferred compile-fix answered with full
                # fixed_code — write it directly, no generation LLM call.
                prior = prior_deferred.get(source_file)
                if prior and prior.get("reason") == "compilation_fix_exhausted" and prior.get("test_path"):
                    fix_key = prior.get("class_name") or class_name
                    dev_fix = compile_fixes.get(fix_key)
                    if isinstance(dev_fix, dict) and dev_fix.get("fixed_code"):
                        test_path = prior["test_path"]
                        test_code = str(dev_fix["fixed_code"])
                        full_path = _safe_test_target(project_path, test_path, source_file)
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        full_path.write_text(test_code, encoding="utf-8")
                        logger.info(
                            f"Applied developer fixed_code for {fix_key} — skipping regeneration"
                        )
                        test_code, exhausted = await _attempt_compile_fix(
                            project_path, full_path, test_code,
                            fix_key, logger, session_dir, maven_compile_cmd,
                            plugin=plugin,
                        )
                        if exhausted and fail_on_uncertainty:
                            uncertainties.append(
                                _compile_fix_item(fix_key, str(full_path), exhausted, test_code)
                            )
                            deferred_out.append({
                                "source_file": source_file,
                                "class_name": fix_key,
                                "test_path": test_path,
                                "reason": "compilation_fix_exhausted",
                            })
                            continue
                        if runtime_fix_enabled:
                            test_code = await _attempt_test_runtime_fix(
                                project_path, full_path, test_code,
                                fix_key, logger, session_dir, maven_test_cmd,
                            )
                        generated.append({
                            "path": test_path,
                            "content": test_code,
                            "class_name": fix_key,
                            "package": prior.get("package", ""),
                            "source_file": source_file,
                            "test_count": test_code.count("@Test") + test_code.count("def test_"),
                        })
                        completed_files.append(source_file)
                        save_generation_cursor(
                            session_dir,
                            target_files=target_files,
                            current_index=len(completed_files),
                            completed_files=completed_files,
                            files_filter=files_filter,
                            deferred=deferred_out,
                        )
                        continue

                # --- Edge case analysis ---
                edge_cases: list[dict] = []
                try:
                    source_path = Path(source_file)
                    if not source_path.exists():
                        source_path = Path(project_path) / source_file
                    if source_path.exists():
                        source_code = source_path.read_text(encoding="utf-8", errors="replace")
                        if class_index and class_name in class_index:
                            class_type = class_index[class_name].get("category", "service").lower()
                        elif "controller" in source_file.lower():
                            class_type = "controller"
                        elif "repository" in source_file.lower():
                            class_type = "repository"
                        elif "model" in source_file.lower() or "entity" in source_file.lower():
                            class_type = "model"
                        edge_cases = await analyze_edge_cases(source_code, class_name, class_type)
                        if edge_cases:
                            logger.info(
                                f"Edge case analysis: {len(edge_cases)} scenarios for {class_name}"
                            )
                except Exception as ec_err:
                    logger.warn(f"Edge case analysis skipped for {source_file}: {ec_err}")

                # --- HITL trigger: no edge cases + no answered requirements
                # → defer this file (question batched at end of run)
                if not edge_cases and not injected and fail_on_uncertainty:
                    logger.info(f"Deferred {class_name}: missing business context")
                    uncertainties.append({
                        "kind": "missing_business_context",
                        "subject": {
                            "source_file": source_file,
                            "class_name": class_name,
                            "class_type": class_type,
                        },
                        "question": (
                            f"No edge cases were derived for `{class_name}`. "
                            f"Please provide business rules, invariants, or specific "
                            f"scenarios that the generated tests must cover."
                        ),
                        "answer_schema": {
                            "test_requirements": {
                                class_name: [{"scenario": "string", "expected": "string"}]
                            }
                        },
                    })
                    deferred_out.append({
                        "source_file": source_file,
                        "class_name": class_name,
                        "reason": "missing_business_context",
                    })
                    continue

                merged_requirements = list(edge_cases or []) + list(injected or [])

                result_json = await generate_adaptive_tests(
                    project_path=project_path,
                    source_file=source_file,
                    conventions=conventions,
                    class_index=class_index,
                    test_examples=test_examples,
                    test_requirements=merged_requirements if merged_requirements else None,
                    prompt_template_dir=prompt_template_dir,
                )
                result = json.loads(result_json)
                test_code = result.get("test_code", "")
                has_tests = "@Test" in test_code or "def test_" in test_code

                if not (result.get("success") and test_code and has_tests):
                    logger.warn(f"No tests generated for {source_file}")
                else:
                    # Test path comes from the technology plugin, NOT from the
                    # generator's Java-only fallback — that fallback returns
                    # non-Java sources unchanged, which used to overwrite the
                    # production file with the generated test.
                    test_path = plugin.test_file_name(source_file)
                    cls = result.get("context", {}).get("class_name", "") or class_name

                    # Developer-provided fix (fixed_code wins over hints if both)
                    dev_fix = compile_fixes.get(cls)
                    dev_hints: list[str] | None = None
                    if isinstance(dev_fix, dict):
                        if "fixed_code" in dev_fix:
                            test_code = dev_fix["fixed_code"]
                            logger.info(f"Applied developer-provided fixed_code for {cls}")
                        elif "hints" in dev_fix and isinstance(dev_fix["hints"], list):
                            dev_hints = [str(h) for h in dev_fix["hints"]]

                    full_path = _safe_test_target(project_path, test_path, source_file)
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(test_code, encoding="utf-8")
                    logger.info(f"Wrote test file: {test_path}")

                    test_code, exhausted = await _attempt_compile_fix(
                        project_path, full_path, test_code,
                        cls, logger, session_dir, maven_compile_cmd,
                        hints=dev_hints,
                        plugin=plugin,
                    )
                    if exhausted and fail_on_uncertainty:
                        uncertainties.append(
                            _compile_fix_item(cls, str(full_path), exhausted, test_code)
                        )
                        deferred_out.append({
                            "source_file": source_file,
                            "class_name": cls,
                            "test_path": test_path,
                            "package": result.get("context", {}).get("package", ""),
                            "reason": "compilation_fix_exhausted",
                        })
                        continue

                    if runtime_fix_enabled:
                        test_code = await _attempt_test_runtime_fix(
                            project_path, full_path, test_code,
                            cls, logger, session_dir, maven_test_cmd,
                        )

                    generated.append({
                        "path": test_path,
                        "content": test_code,
                        "class_name": cls,
                        "package": result.get("context", {}).get("package", ""),
                        "source_file": source_file,
                        "test_count": result.get("test_count", 0),
                    })

            except Exception as file_err:
                logger.error(f"Failed to generate tests for {source_file}: {file_err}")
                raise

            completed_files.append(source_file)
            save_generation_cursor(
                session_dir,
                target_files=target_files,
                current_index=len(completed_files),
                completed_files=completed_files,
                files_filter=files_filter,
                deferred=deferred_out,
            )

        # --- One batched question for everything that needs human input ---
        if uncertainties:
            # The verified answer (if any) was applied to the files that
            # succeeded above; consume it before emitting the next question.
            if answer_payload is not None:
                finalize_answer(session_dir, answer_payload)
            save_generation_cursor(
                session_dir,
                target_files=target_files,
                current_index=len(completed_files),
                completed_files=completed_files,
                files_filter=files_filter,
                deferred=deferred_out,
            )
            if len(uncertainties) == 1:
                question_payload = uncertainties[0]
            else:
                question_payload = {
                    "kind": "batch",
                    "question": (
                        f"{len(uncertainties)} file(s) need your input to finish "
                        f"this generation run ({len(generated)} other file(s) "
                        f"were generated successfully)."
                    ),
                    "items": uncertainties,
                    "answer_schema": _merge_answer_schemas(uncertainties),
                }
            qpath = emit_question(
                session_dir,
                "generation",
                question_payload,
                project_path=project_path,
                session_id=session["session_id"],
            )
            logger.info(
                f"Paused: {len(uncertainties)} question item(s) written to {qpath}"
            )
            raise AwaitingInputError(qpath, "generation")

        if answer_payload is not None:
            finalize_answer(session_dir, answer_payload)

        # --- Build report ---
        content = "# Test Generation Results\n\n"
        content += f"**Target files**: {len(target_files)}\n"
        content += f"**Tests generated**: {len(generated)}\n\n"

        if generated:
            content += "## Generated Tests\n\n"
            content += "| # | Source File | Test File | Test Count |\n"
            content += "|---|------------|-----------|------------|\n"
            for idx, test in enumerate(generated, 1):
                content += f"| {idx} | `{test.get('source_file', '')}` | `{test.get('path', '')}` | {test.get('test_count', 0)} |\n"
            content += "\n"
            content += "## Generated Test Files\n\n"
            for test in generated:
                test_path = test.get("path", "")
                if test_path:
                    content += f"### `{test_path}`\n\n"
                    content += f"Written to disk. {test.get('test_count', 0)} test methods.\n\n"

        failed = len(target_files) - len(generated)
        if failed > 0:
            content += f"\n**Note**: {failed} file(s) did not produce tests.\n"
            logger.warn(f"{failed} files did not produce tests")

        logger.info(f"Generation complete: {len(generated)} test files created")

        update_step_file(
            session_dir, "generation", STATUS_COMPLETED, content,
            data={"generated": [{k: v for k, v in t.items() if k != "content"} for t in generated]},
        )

        clear_generation_cursor(session_dir)

        logger.result("Test Generation Complete", content)

        from src.lib.integrity import emit_token
        emit_token(project_path, "generation", session["session_id"])
        return 0

    except AwaitingInputError as wait:
        logger.info(f"Generation paused — awaiting human input ({wait.question_path})")
        print(f"[TESTBOOST_AWAITING_INPUT:step=generation:question={wait.question_path}]")
        return EXIT_AWAITING_INPUT
    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        update_step_file(
            session_dir, "generation", STATUS_FAILED,
            f"# Test Generation - FAILED\n\n**Error**: {e}\n",
        )
        return 1
_MAX_COMPILE_FIX_ATTEMPTS = 3


def _compile_fix_item(
    class_name: str, test_file: str, exhausted: dict, current_code: str
) -> dict:
    """Build a question item for a compile-fix budget exhaustion."""
    attempts = exhausted.get("attempts", _MAX_COMPILE_FIX_ATTEMPTS)
    return {
        "kind": "compilation_fix_exhausted",
        "subject": {
            "class_name": class_name,
            "test_file": test_file,
            "attempts": attempts,
        },
        "question": (
            f"Could not fix compilation of `{class_name}` after "
            f"{attempts} LLM attempts. Please review the "
            f"errors and provide either the corrected test code or hints."
        ),
        "compile_errors": exhausted.get("errors", ""),
        "current_test_code": current_code[:8000],
        "answer_schema": {
            "compile_fixes": {
                class_name: {
                    "fixed_code": "string (full test file content)",
                    "hints": ["natural-language hint for the LLM"],
                }
            }
        },
    }
def _merge_answer_schemas(items: list[dict]) -> dict:
    """Combine per-item answer schemas into one reply shape for a batch question."""
    merged: dict = {}
    for item in items:
        for key, value in (item.get("answer_schema") or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key].update(value)
            elif isinstance(value, dict):
                merged[key] = dict(value)
            else:
                merged.setdefault(key, value)
    return merged


def _safe_test_target(project_path: str, test_path: str, source_file: str) -> Path:
    """Resolve the absolute target for a generated test, refusing to clobber
    the source under test.

    Defense in depth behind the plugin's test_file_name(): whatever the
    mapping (or a future bug in it) produces, a generated test must never
    land on the production file it was generated FOR.
    """
    full_path = Path(project_path) / test_path
    source_abs = Path(project_path) / source_file
    try:
        collision = full_path.resolve() == source_abs.resolve()
    except OSError:
        collision = str(full_path) == str(source_abs)
    if collision:
        raise RuntimeError(
            f"refusing to write generated test over its own source file "
            f"({source_file}) — test path mapping returned the source path"
        )
    return full_path


async def _attempt_compile_fix(
    project_path: str,
    test_file: Path,
    test_code: str,
    class_name: str,
    logger,
    session_dir: str | None = None,
    maven_compile_cmd: str | None = None,
    hints: list[str] | None = None,
    plugin=None,
) -> tuple[str, dict | None]:
    """Compile-check the test file and use the LLM to fix errors, retrying up to N times.

    The compile command comes from the technology plugin when one is
    supplied (e.g. `py_compile {test_file}` for Python); the Java path
    keeps honoring maven_compile_cmd from analysis.md so profiles and
    custom properties set there are respected.

    Returns (code, exhausted): exhausted is None when the file compiles (or
    the check was skipped for infra reasons), or a dict with "errors" and
    "attempts" when the retry budget ran out with the code still broken.
    The caller decides whether to queue a question or give up silently.
    """
    from src.lib.plugins.java_spring import _parse_maven_cmd as _java_parse_maven_cmd

    cmd: list[str] | None = None
    if plugin is not None and plugin.identifier != "java-spring":
        # Technology-specific compile/syntax check ({test_file} placeholder)
        cmd = [
            part.replace("{test_file}", str(test_file))
            for part in plugin.validation_command(Path(project_path), {})
        ]
    if cmd is None:
        try:
            cmd = _java_parse_maven_cmd(maven_compile_cmd) if maven_compile_cmd else None
        except ValueError as e:
            logger.warn(f"Invalid maven_compile_cmd, using default: {e}")
            cmd = None
    if not cmd:
        cmd = [shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn", "test-compile", "-q", "--no-transfer-progress"]

    current_code = test_code

    # When the developer provides natural-language hints, cap to a single
    # LLM retry so we don't burn budget on hint-guided iterations.
    max_attempts = 2 if hints else _MAX_COMPILE_FIX_ATTEMPTS
    hint_text = "\n".join(f"- {h}" for h in hints) if hints else ""

    for attempt in range(1, max_attempts + 1):
        # --- compile ---
        try:
            result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warn(f"Compile check skipped ({class_name}): {e}")
            return current_code, None

        if result.returncode == 0:
            if attempt == 1:
                logger.info(f"Compilation OK: {class_name}")
            else:
                logger.info(f"Compilation OK after {attempt - 1} fix(es): {class_name}")
            return current_code, None

        # --- parse errors for our file ---
        all_errors = result.stdout + result.stderr
        file_name = test_file.name
        file_error_lines = [ln for ln in all_errors.splitlines() if file_name in ln]

        if not file_error_lines:
            _warn_maven_config_issue(all_errors, session_dir, project_path, logger)
            return current_code, None

        relevant_lines = [ln for ln in all_errors.splitlines() if file_name in ln or "[ERROR]" in ln]
        relevant_errors = "\n".join(relevant_lines[:80])

        # Log compilation errors at INFO so they appear in generation.md
        logger.info(
            f"Compilation errors in {class_name} "
            f"(attempt {attempt}/{max_attempts}):\n"
            + "\n".join(file_error_lines[:15])
        )

        if attempt == max_attempts:
            logger.info(f"Max fix attempts reached for {class_name}")
            return current_code, {"errors": relevant_errors, "attempts": max_attempts}

        # --- ask LLM to fix ---
        try:
            from src.lib.bridge import fix_compilation_errors
            errors_with_hints = relevant_errors
            if hint_text:
                errors_with_hints = (
                    f"{relevant_errors}\n\n"
                    f"Developer hints (please follow):\n{hint_text}"
                )
                logger.info(f"Applying {len(hints)} developer hint(s) to LLM fix")
            fixed = await fix_compilation_errors(current_code, errors_with_hints, class_name)
            if fixed == current_code:
                logger.info(f"LLM returned identical code for {class_name} — stopping retries")
                return current_code, {"errors": relevant_errors, "attempts": attempt}
            test_file.write_text(fixed, encoding="utf-8")
            current_code = fixed
            logger.info(f"Applied fix attempt {attempt} for {class_name}, recompiling...")
        except Exception as e:
            logger.warn(f"Auto-fix failed for {class_name}: {e}")
            return current_code, None

    return current_code, None


_MAX_TEST_FIX_ATTEMPTS = 2  # `mvn test` is slower than `test-compile`, keep shorter
_TEST_FIX_TIMEOUT_SECONDS = 180
_TEST_FIX_OUTPUT_LINES = 80


async def _attempt_test_runtime_fix(
    project_path: str,
    test_file: Path,
    test_code: str,
    class_name: str,
    logger,
    session_dir: str | None = None,
    maven_test_cmd: str | None = None,
) -> str:
    """Run `mvn test -Dtest=<class>` and use LLM to fix runtime failures, retrying up to N times.

    Runs AFTER the test compiles cleanly. Only the test code is rewritten — the
    production class under test is never modified. Maven/Java specific; callers
    gate this on the java-spring plugin.
    """
    from src.lib.plugins.java_spring import _parse_maven_cmd

    base_cmd = None
    if maven_test_cmd:
        try:
            base_cmd = _parse_maven_cmd(maven_test_cmd)
        except ValueError as e:
            logger.warn(f"Invalid maven_test_cmd, using default: {e}")
            base_cmd = None
    if not base_cmd:
        base_cmd = [
            shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn",
            "test", "-q", "--no-transfer-progress",
        ]

    cmd = [*base_cmd, f"-Dtest={class_name}"]
    current_code = test_code

    for attempt in range(1, _MAX_TEST_FIX_ATTEMPTS + 1):
        try:
            result = subprocess.run(
                cmd, cwd=project_path, capture_output=True, text=True,
                timeout=_TEST_FIX_TIMEOUT_SECONDS,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warn(f"Test run skipped ({class_name}): {e}")
            return current_code

        if result.returncode == 0:
            if attempt == 1:
                logger.info(f"Tests passing: {class_name}")
            else:
                logger.info(f"Tests passing after {attempt - 1} runtime-fix(es): {class_name}")
            return current_code

        output = result.stdout + result.stderr
        # Keep only lines useful for diagnosis to avoid prompt bloat from Maven noise
        markers = ("FAIL", "ERROR", "Tests run:", "Caused by:", "at ", class_name)
        relevant_lines = [ln for ln in output.splitlines() if any(m in ln for m in markers)]
        if not relevant_lines:
            relevant_lines = output.splitlines()[-40:]
        relevant_errors = "\n".join(relevant_lines[:_TEST_FIX_OUTPUT_LINES])

        logger.info(
            f"Test failures in {class_name} "
            f"(attempt {attempt}/{_MAX_TEST_FIX_ATTEMPTS}):\n"
            + "\n".join(relevant_lines[:15])
        )

        if attempt == _MAX_TEST_FIX_ATTEMPTS:
            logger.info(f"Max runtime-fix attempts reached for {class_name} — leaving for manual correction")
            return current_code

        try:
            from src.lib.bridge import fix_test_runtime_errors
            fixed = await fix_test_runtime_errors(current_code, relevant_errors, class_name)
            if fixed == current_code:
                logger.info(f"LLM returned identical code for {class_name} — stopping runtime-fix retries")
                return current_code
            test_file.write_text(fixed, encoding="utf-8")
            current_code = fixed
            logger.info(f"Applied runtime-fix attempt {attempt} for {class_name}, re-running tests...")
        except Exception as e:
            logger.warn(f"Auto-fix (runtime) failed for {class_name}: {e}")
            return current_code

    return current_code
