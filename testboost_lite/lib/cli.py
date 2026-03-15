#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""TestBoost Lite CLI - Lightweight entry point.

This is the single CLI entry point that replaces the heavy FastAPI + Typer
stack. It is designed to be called from shell scripts, which are in turn
invoked by LLM CLI slash commands.

Usage:
    python -m testboost_lite.lib.cli <command> <project_path> [options]

Commands:
    init      - Initialize .testboost/ in a project
    analyze   - Analyze project structure and test context
    gaps      - Identify test coverage gaps
    generate  - Generate tests for identified gaps
    validate  - Compile and run generated tests
    status    - Show current session status
"""

import argparse
import asyncio
import json
import re
import shlex
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

# Add the TestBoost root to path so we can import existing modules
TESTBOOST_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(TESTBOOST_ROOT))

# Load .env into os.environ BEFORE any LLM/httpx imports so that NO_PROXY,
# SSL_CERT_FILE, REQUESTS_CA_BUNDLE etc. are visible to httpx at client creation.
try:
    from dotenv import load_dotenv
    load_dotenv(TESTBOOST_ROOT / ".env", override=False)
except ImportError:
    pass


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .testboost/ in a project."""
    from testboost_lite.lib.integrity import emit_token, get_or_create_secret
    from testboost_lite.lib.session_tracker import create_session, init_project

    project_path = args.project_path

    if not Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    # Initialize directory structure
    result = init_project(project_path)
    print(f"[+] {result['message']}")

    # Ensure integrity secret exists
    get_or_create_secret(project_path)

    # Create initial session
    session = create_session(
        project_path,
        name=args.name if hasattr(args, "name") and args.name else None,
        description=args.description if hasattr(args, "description") and args.description else "",
    )
    print(f"[+] {session['message']}")
    print(f"    Session directory: {session['session_dir']}")
    print(f"    Session ID: {session['session_id']}")

    emit_token(project_path, "init", session["session_id"])
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze project structure."""
    return asyncio.run(_cmd_analyze_async(args))


async def _cmd_analyze_async(args: argparse.Namespace) -> int:
    from testboost_lite.lib.md_logger import MdLogger
    from testboost_lite.lib.session_tracker import (
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

    logger = MdLogger(session["session_dir"], "analysis", verbose=getattr(args, "verbose", False))

    # Mark step as in progress
    update_step_file(session["session_dir"], "analysis", STATUS_IN_PROGRESS, "# Analysis\n\nRunning...")

    logger.info("Starting project analysis...")

    try:
        # --- Reuse existing TestBoost functions via bridge ---
        from testboost_lite.lib.testboost_bridge import (
            analyze_project_context,
            classify_file,
            detect_test_conventions,
            find_source_files,
            find_test_for_source,
        )

        result_json = await analyze_project_context(project_path)
        result = json.loads(result_json)

        if not result.get("success"):
            error_msg = result.get("error", "Unknown analysis error")
            logger.error(f"Analysis failed: {error_msg}")
            update_step_file(
                session["session_dir"], "analysis", STATUS_FAILED,
                f"# Analysis - FAILED\n\n**Error**: {error_msg}\n",
            )
            return 1

        conventions_json = await detect_test_conventions(project_path)
        conventions = json.loads(conventions_json)

        source_files = find_source_files(project_path)

        # Build the analysis report
        content = "# Project Analysis\n\n"
        content += f"**Project type**: {result.get('project_type', 'unknown')}\n"
        content += f"**Build system**: {result.get('build_system', 'unknown')}\n"
        content += f"**Java version**: {result.get('java_version', 'unknown')}\n\n"

        # Frameworks
        frameworks = result.get("frameworks", [])
        test_frameworks = result.get("test_frameworks", [])
        content += "## Frameworks\n\n"
        content += f"- **Application**: {', '.join(frameworks) if frameworks else 'none detected'}\n"
        content += f"- **Testing**: {', '.join(test_frameworks) if test_frameworks else 'none detected'}\n\n"

        # Source structure
        src_struct = result.get("source_structure", {})
        test_struct = result.get("test_structure", {})
        content += "## Structure\n\n"
        content += f"- **Source classes**: {src_struct.get('class_count', 0)}\n"
        content += f"- **Existing tests**: {test_struct.get('test_count', 0)}\n"
        content += f"- **Packages**: {len(src_struct.get('packages', []))}\n\n"

        # Classify source files and check for existing tests
        file_details = []
        for sf in source_files:
            category = classify_file(sf)
            test_file = find_test_for_source(project_path, sf)
            file_details.append({
                "path": sf,
                "category": category,
                "has_test": test_file is not None,
                "test_file": test_file,
            })

        tested_count = sum(1 for f in file_details if f["has_test"])

        # Source files table
        content += "## Source Files for Test Generation\n\n"
        content += f"Found **{len(source_files)}** source files"
        content += f" ({tested_count} with existing tests, {len(source_files) - tested_count} without):\n\n"
        content += "| # | Source File | Category | Has Test | Test File |\n"
        content += "|---|-----------|----------|----------|----------|\n"
        for i, fd in enumerate(file_details, 1):
            src_name = Path(fd["path"]).name
            has_test = "Yes" if fd["has_test"] else "No"
            test_name = Path(fd["test_file"]).name if fd["test_file"] else "-"
            content += f"| {i} | `{src_name}` | {fd['category']} | {has_test} | {test_name} |\n"
        content += "\n"

        # Conventions summary
        if conventions.get("success"):
            content += "## Detected Test Conventions\n\n"
            naming = conventions.get("naming", {})
            assertions = conventions.get("assertions", {})
            mocking = conventions.get("mocking", {})
            content += f"- **Naming pattern**: {naming.get('dominant_pattern', 'unknown')}\n"
            content += f"- **Assertion style**: {assertions.get('dominant_style', 'unknown')}\n"
            content += f"- **Uses Mockito**: {'yes' if mocking.get('uses_mockito') else 'no'}\n"
            content += f"- **Uses Spring MockBean**: {'yes' if mocking.get('uses_spring_mock_bean') else 'no'}\n\n"

        # Detect Maven build configuration
        maven_config = _detect_maven_build_config(project_path)
        content += "## Maven Build Configuration\n\n"
        content += f"- **Compile command**: `{maven_config['compile_cmd']}`\n"
        content += f"- **Test command**: `{maven_config['test_cmd']}`\n"
        for note in maven_config["notes"]:
            content += f"- {note}\n"
        content += "\n> **Customize**: edit `maven_compile_cmd` / `maven_test_cmd` in the JSON block below "
        content += "(e.g. add `-P corp` for profiles, `-Dskip.integration=true` for properties).\n\n"

        logger.info(f"Analysis complete: {len(source_files)} source files, {src_struct.get('class_count', 0)} classes")

        # Write the step file
        update_step_file(
            session["session_dir"], "analysis", STATUS_COMPLETED, content,
            data={
                "project_context": result,
                "conventions": conventions,
                "source_files": source_files,
                "source_file_details": file_details,
                "maven_compile_cmd": maven_config["compile_cmd"],
                "maven_test_cmd": maven_config["test_cmd"],
            },
        )

        # Print summary to stdout for the LLM
        logger.result("Analysis Complete", content)

        from testboost_lite.lib.integrity import emit_token
        emit_token(project_path, "analysis", session["session_id"])
        return 0

    except Exception as e:
        logger.error(f"Analysis failed with exception: {e}")
        update_step_file(
            session["session_dir"], "analysis", STATUS_FAILED,
            f"# Analysis - FAILED\n\n**Error**: {e}\n",
        )
        return 1


def cmd_gaps(args: argparse.Namespace) -> int:
    """Identify test coverage gaps."""
    return asyncio.run(_cmd_gaps_async(args))


async def _cmd_gaps_async(args: argparse.Namespace) -> int:
    from testboost_lite.lib.md_logger import MdLogger
    from testboost_lite.lib.session_tracker import (
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
    logger = MdLogger(session_dir, "coverage-gaps", verbose=getattr(args, "verbose", False))

    # Check that analysis was done
    analysis_file = Path(session_dir) / "analysis.md"
    if not analysis_file.exists():
        logger.error("Analysis step not completed. Run `analyze` first.")
        return 1

    update_step_file(session_dir, "coverage-gaps", STATUS_IN_PROGRESS, "# Coverage Gaps\n\nIdentifying...")

    logger.info("Identifying test coverage gaps...")

    try:
        # Read analysis data
        analysis_content = analysis_file.read_text(encoding="utf-8")

        # Extract source files from the JSON block in analysis.md
        source_files = _extract_json_field(analysis_content, "source_files")
        if not source_files:
            logger.error("No source files found in analysis. Re-run analyze.")
            return 1

        # Find existing test files
        project_dir = Path(project_path)
        existing_tests = set()

        test_dirs = list(project_dir.glob("**/src/test/java"))
        for test_dir in test_dirs:
            for test_file in test_dir.rglob("*Test.java"):
                # Extract class name from test file name
                class_name = test_file.stem.replace("Test", "")
                existing_tests.add(class_name)
            for test_file in test_dir.rglob("*Tests.java"):
                class_name = test_file.stem.replace("Tests", "")
                existing_tests.add(class_name)

        # Identify gaps: source files without corresponding tests
        gaps = []
        covered = []
        for source_file in source_files:
            source_name = Path(source_file).stem
            if source_name in existing_tests:
                covered.append(source_file)
            else:
                gaps.append(source_file)

        # Build the gaps report
        total = len(source_files)
        gap_count = len(gaps)
        coverage_pct = ((total - gap_count) / total * 100) if total > 0 else 0

        content = "# Coverage Gap Analysis\n\n"
        content += f"**Total testable files**: {total}\n"
        content += f"**Files with tests**: {len(covered)}\n"
        content += f"**Files WITHOUT tests**: {gap_count}\n"
        content += f"**Estimated coverage**: {coverage_pct:.0f}%\n\n"

        if gaps:
            content += "## Files Needing Tests\n\n"
            content += "| # | Source File | Priority |\n"
            content += "|---|------------|----------|\n"
            for i, gap in enumerate(gaps, 1):
                # Simple priority heuristic based on path
                priority = "high" if "service" in gap.lower() or "controller" in gap.lower() else "medium"
                content += f"| {i} | `{gap}` | {priority} |\n"
            content += "\n"

        if covered:
            content += "## Files Already Covered\n\n"
            for c in covered:
                content += f"- `{c}`\n"
            content += "\n"

        logger.info(f"Found {gap_count} files without tests out of {total} total")

        update_step_file(
            session_dir, "coverage-gaps", STATUS_COMPLETED, content,
            data={"gaps": gaps, "covered": covered, "coverage_pct": coverage_pct},
        )

        logger.result("Coverage Gaps Identified", content)

        from testboost_lite.lib.integrity import emit_token
        emit_token(project_path, "coverage-gaps", session["session_id"])
        return 0

    except Exception as e:
        logger.error(f"Gap analysis failed: {e}")
        update_step_file(
            session_dir, "coverage-gaps", STATUS_FAILED,
            f"# Coverage Gaps - FAILED\n\n**Error**: {e}\n",
        )
        return 1


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate tests for identified gaps."""
    return asyncio.run(_cmd_generate_async(args))


async def _cmd_generate_async(args: argparse.Namespace) -> int:
    from testboost_lite.lib.md_logger import MdLogger
    from testboost_lite.lib.session_tracker import (
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
    logger = MdLogger(session_dir, "generation", verbose=getattr(args, "verbose", False))

    # Check prerequisites
    gaps_file = Path(session_dir) / "coverage-gaps.md"
    if not gaps_file.exists():
        logger.error("Coverage gaps step not completed. Run `gaps` first.")
        return 1

    update_step_file(session_dir, "generation", STATUS_IN_PROGRESS, "# Test Generation\n\nGenerating...")

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

        # Extract conventions and Maven config from the analysis step
        analysis_file = Path(session_dir) / "analysis.md"
        conventions = None
        maven_compile_cmd = None
        if analysis_file.exists():
            analysis_content = analysis_file.read_text(encoding="utf-8")
            conventions = _extract_json_field(analysis_content, "conventions")
            maven_compile_cmd = _extract_json_field(analysis_content, "maven_compile_cmd")

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

        # --- Reuse existing TestBoost test generation via bridge ---
        # Verify LLM connectivity before generating tests
        from src.lib.startup_checks import check_llm_connection
        from testboost_lite.lib.testboost_bridge import generate_adaptive_tests
        try:
            await check_llm_connection()
        except Exception as e:
            logger.error(f"LLM connection failed: {e}")
            print(f"\nERROR: Cannot connect to LLM provider. {e}")
            print("Set the appropriate API key (ANTHROPIC_API_KEY, GOOGLE_API_KEY, or OPENAI_API_KEY).")
            return 1

        generated = []
        for source_file in target_files:
            logger.info(f"Generating tests for: {source_file}")
            try:
                result_json = await generate_adaptive_tests(
                    project_path=project_path,
                    source_file=source_file,
                    conventions=conventions,
                )
                result = json.loads(result_json)
                if result.get("success") and result.get("test_code") and "@Test" in result.get("test_code", ""):
                    generated.append({
                        "path": result.get("test_file", ""),
                        "content": result.get("test_code", ""),
                        "class_name": result.get("context", {}).get("class_name", ""),
                        "package": result.get("context", {}).get("package", ""),
                        "source_file": source_file,
                        "test_count": result.get("test_count", 0),
                    })
                else:
                    logger.warn(f"No tests generated for {source_file}")
            except Exception as file_err:
                logger.error(f"Failed to generate tests for {source_file}: {file_err}")
                raise  # Re-raise to propagate LLM errors

        # Compile-and-fix: run after ALL files are written to avoid inter-file dependency issues
        # (done below, after the file-writing loop)

        # Build generation report
        content = "# Test Generation Results\n\n"
        content += f"**Target files**: {len(target_files)}\n"
        content += f"**Tests generated**: {len(generated)}\n"
        content += "\n"

        if generated:
            content += "## Generated Tests\n\n"
            content += "| # | Source File | Test File | Test Count |\n"
            content += "|---|------------|-----------|------------|\n"
            for i, test in enumerate(generated, 1):
                content += f"| {i} | `{test.get('source_file', '')}` | `{test.get('path', '')}` | {test.get('test_count', 0)} |\n"
            content += "\n"

            # Write all test files first, then compile-and-fix in one pass
            written_files = []
            content += "## Generated Test Files\n\n"
            for test in generated:
                test_path = test.get("path", "")
                test_content = test.get("content", "")
                if test_path and test_content:
                    full_path = Path(project_path) / test_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(test_content, encoding="utf-8")
                    logger.info(f"Wrote test file: {test_path}")
                    written_files.append((full_path, test))

            # Compile-and-fix: one mvn test-compile for all files, fix per-file errors
            for full_path, test in written_files:
                class_name = test.get("class_name", full_path.stem)
                fixed = await _attempt_compile_fix(
                    project_path, full_path, test.get("content", ""),
                    class_name, logger, session_dir, maven_compile_cmd,
                )
                if fixed != test.get("content", ""):
                    test["content"] = fixed

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

        logger.result("Test Generation Complete", content)

        from testboost_lite.lib.integrity import emit_token
        emit_token(project_path, "generation", session["session_id"])
        return 0

    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        update_step_file(
            session_dir, "generation", STATUS_FAILED,
            f"# Test Generation - FAILED\n\n**Error**: {e}\n",
        )
        return 1


_MAX_COMPILE_FIX_ATTEMPTS = 3


async def _attempt_compile_fix(
    project_path: str,
    test_file: Path,
    test_code: str,
    class_name: str,
    logger,
    session_dir: str | None = None,
    maven_compile_cmd: str | None = None,
) -> str:
    """Run mvn test-compile and use LLM to fix compilation errors, retrying up to N times.

    Uses maven_compile_cmd from analysis.md if available, so profiles and
    custom properties set there are respected.
    """
    cmd = _parse_maven_cmd(maven_compile_cmd) if maven_compile_cmd else None
    if not cmd:
        cmd = [shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn", "test-compile", "-q", "--no-transfer-progress"]

    current_code = test_code

    for attempt in range(1, _MAX_COMPILE_FIX_ATTEMPTS + 1):
        # --- compile ---
        try:
            result = subprocess.run(cmd, cwd=project_path, capture_output=True, text=True, timeout=120)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warn(f"Compile check skipped ({class_name}): {e}")
            return current_code

        if result.returncode == 0:
            if attempt == 1:
                logger.info(f"Compilation OK: {class_name}")
            else:
                logger.info(f"Compilation OK after {attempt - 1} fix(es): {class_name}")
            return current_code

        # --- parse errors for our file ---
        all_errors = result.stdout + result.stderr
        file_name = test_file.name
        file_error_lines = [ln for ln in all_errors.splitlines() if file_name in ln]

        if not file_error_lines:
            _warn_maven_config_issue(all_errors, session_dir, project_path, logger)
            return current_code

        relevant_lines = [ln for ln in all_errors.splitlines() if file_name in ln or "[ERROR]" in ln]
        relevant_errors = "\n".join(relevant_lines[:80])

        # Log compilation errors at INFO so they appear in generation.md
        logger.info(
            f"Compilation errors in {class_name} "
            f"(attempt {attempt}/{_MAX_COMPILE_FIX_ATTEMPTS}):\n"
            + "\n".join(file_error_lines[:15])
        )

        if attempt == _MAX_COMPILE_FIX_ATTEMPTS:
            logger.info(f"Max fix attempts reached for {class_name} — leaving for manual correction")
            return current_code

        # --- ask LLM to fix ---
        try:
            from testboost_lite.lib.testboost_bridge import fix_compilation_errors
            fixed = await fix_compilation_errors(current_code, relevant_errors, class_name)
            if fixed == current_code:
                logger.info(f"LLM returned identical code for {class_name} — stopping retries")
                return current_code
            test_file.write_text(fixed, encoding="utf-8")
            current_code = fixed
            logger.info(f"Applied fix attempt {attempt} for {class_name}, recompiling...")
        except Exception as e:
            logger.warn(f"Auto-fix failed for {class_name}: {e}")
            return current_code

    return current_code


def cmd_validate(args: argparse.Namespace) -> int:
    """Compile and validate generated tests."""
    return asyncio.run(_cmd_validate_async(args))


async def _cmd_validate_async(args: argparse.Namespace) -> int:
    from testboost_lite.lib.md_logger import MdLogger
    from testboost_lite.lib.session_tracker import (
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
    logger = MdLogger(session_dir, "validation", verbose=getattr(args, "verbose", False))

    # Check prerequisites
    gen_file = Path(session_dir) / "generation.md"
    if not gen_file.exists():
        logger.error("Generation step not completed. Run `generate` first.")
        return 1

    update_step_file(session_dir, "validation", STATUS_IN_PROGRESS, "# Validation\n\nCompiling and testing...")

    try:
        # Read Maven commands from analysis.md (allows profile/property customization)
        analysis_file = Path(session_dir) / "analysis.md"
        maven_compile_cmd = None
        maven_test_cmd = None
        if analysis_file.exists():
            analysis_content = analysis_file.read_text(encoding="utf-8")
            maven_compile_cmd = _extract_json_field(analysis_content, "maven_compile_cmd")
            maven_test_cmd = _extract_json_field(analysis_content, "maven_test_cmd")

        mvn = shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn"
        compile_cmd = _parse_maven_cmd(maven_compile_cmd) if maven_compile_cmd else [mvn, "test-compile", "-q", "--no-transfer-progress"]
        test_run_cmd = _parse_maven_cmd(maven_test_cmd) if maven_test_cmd else [mvn, "test", "-q", "--no-transfer-progress"]

        content = "# Validation Results\n\n"
        content += f"- **Compile**: `{' '.join(compile_cmd)}`\n"
        content += f"- **Test**: `{' '.join(test_run_cmd)}`\n\n"

        # Step 1: Compile tests
        logger.info(f"Compiling tests: {' '.join(compile_cmd)}")
        compile_result = subprocess.run(
            compile_cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if compile_result.returncode != 0:
            # --- Reuse MavenErrorParser via bridge ---
            from testboost_lite.lib.testboost_bridge import parse_maven_errors

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

            update_step_file(
                session_dir, "validation", STATUS_FAILED, content,
                data={"compilation": "failed", "error_count": len(errors)},
            )

            logger.result("Validation: Compilation Failed", content)
            return 1

        logger.info("Compilation successful")
        content += "## Compilation: PASSED\n\n"

        # Step 2: Run tests
        logger.info(f"Running tests: {' '.join(test_run_cmd)}")
        test_timeout = 300  # 5 minutes
        test_result = subprocess.run(
            test_run_cmd,
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=test_timeout,
        )

        test_output = test_result.stdout + test_result.stderr

        if test_result.returncode == 0:
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
            status = STATUS_FAILED

        update_step_file(
            session_dir, "validation", status, content,
            data={
                "compilation": "passed",
                "tests": "passed" if test_result.returncode == 0 else "failed",
                "return_code": test_result.returncode,
            },
        )

        logger.result("Validation Results", content)

        if test_result.returncode == 0:
            from testboost_lite.lib.integrity import emit_token
            emit_token(project_path, "validation", session["session_id"])
        return 0 if test_result.returncode == 0 else 1

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


def cmd_install(args: argparse.Namespace) -> int:
    """Install TestBoost commands into a target project.

    Copies slash-command markdown files and shell scripts to the target
    project, with paths resolved to the current TestBoost installation.
    This ensures the LLM CLI always calls the real TestBoost CLI.
    """
    from testboost_lite.lib.installer import install_commands

    project_path = args.project_path
    if not Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    result = install_commands(
        project_path=project_path,
        testboost_root=str(TESTBOOST_ROOT),
    )

    if result["success"]:
        print(f"[+] {result['message']}")
        for detail in result.get("details", []):
            print(f"    {detail}")
        return 0
    else:
        print(f"[X] {result['message']}", file=sys.stderr)
        return 1


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify an integrity token.

    Exits 0 and prints VERIFIED if the token is valid.
    Exits 1 and prints FAILED if the token is invalid or malformed.
    """
    from testboost_lite.lib.integrity import verify_token

    project_path = args.project_path
    token_line = args.token.strip()

    if verify_token(project_path, token_line):
        print("[TESTBOOST_VERIFY:OK]")
        return 0
    else:
        print("[TESTBOOST_VERIFY:FAILED]")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show current session status."""
    from testboost_lite.lib.session_tracker import get_session_status

    status = get_session_status(args.project_path)
    print(status)
    return 0


# --- Helpers ---

def _detect_maven_build_config(project_path: str) -> dict:
    """Detect Maven build configuration from pom.xml and .mvn/maven.config.

    Returns a dict with:
      - compile_cmd: str  (e.g. "mvn test-compile -q --no-transfer-progress")
      - test_cmd:    str  (e.g. "mvn test -q --no-transfer-progress")
      - notes:       list[str]  (human-readable config notes)
    """
    project_dir = Path(project_path)
    notes: list[str] = []
    extra_flags = ""

    # Check for .mvn/maven.config (flags applied to every Maven invocation)
    maven_config_file = project_dir / ".mvn" / "maven.config"
    if maven_config_file.exists():
        try:
            config_content = maven_config_file.read_text(encoding="utf-8").strip()
            if config_content:
                extra_flags = " " + config_content.replace("\n", " ")
                notes.append(f"`.mvn/maven.config` adds flags: `{config_content.replace(chr(10), ' ')}`")
        except OSError:
            pass

    # Check for activeByDefault profiles in pom.xml
    pom_file = project_dir / "pom.xml"
    active_profiles: list[str] = []
    if pom_file.exists():
        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

            profiles = root.findall(".//maven:profile", ns) or root.findall(".//profile")
            for profile in profiles:
                activation = (
                    profile.find("maven:activation", ns)
                    or profile.find("activation")
                )
                if activation is not None:
                    active_by_default = (
                        activation.find("maven:activeByDefault", ns)
                        or activation.find("activeByDefault")
                    )
                    if active_by_default is not None and active_by_default.text == "true":
                        profile_id = profile.find("maven:id", ns) or profile.find("id")
                        if profile_id is not None:
                            active_profiles.append(profile_id.text)
        except ET.ParseError:
            pass

    if active_profiles:
        profile_flags = " -P " + ",".join(active_profiles)
        extra_flags += profile_flags
        notes.append(
            f"Detected active-by-default profiles: `{', '.join(active_profiles)}` "
            f"— added `-P {','.join(active_profiles)}`"
        )

    if not notes:
        notes.append("No special profiles or Maven config detected — using default flags")

    return {
        "compile_cmd": f"mvn test-compile -q --no-transfer-progress{extra_flags}",
        "test_cmd": f"mvn test -q --no-transfer-progress{extra_flags}",
        "notes": notes,
    }


def _parse_maven_cmd(cmd_str: str) -> list[str]:
    """Parse a Maven command string into a list, resolving the mvn binary.

    Example: "mvn test-compile -q -P corp" -> ["/usr/bin/mvn", "test-compile", "-q", "-P", "corp"]
    """
    try:
        parts = shlex.split(cmd_str)
    except ValueError:
        parts = cmd_str.split()

    if not parts:
        return []

    binary = parts[0]
    if binary in ("mvn", "mvn.cmd"):
        resolved = shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn"
        return [resolved] + parts[1:]

    # Local wrapper (./mvnw, mvnw) — keep as-is; subprocess.run resolves relative to cwd
    return parts


def _warn_maven_config_issue(
    maven_output: str,
    session_dir: str | None,
    project_path: str,
    logger,
) -> None:
    """Log an explicit user hint when Maven fails for non-test-file reasons.

    Called when mvn test-compile exits non-zero but none of the errors reference
    the generated test files — meaning the failure is likely a project config issue
    (missing profile, corporate repo, custom flags).
    """
    lines = [
        "",
        "WARNING: Maven compile failed, but errors don't reference any generated test file.",
        "  This usually means Maven needs additional flags (e.g. a -P profile, -D property,",
        "  or corporate Maven settings).",
        "",
        "  To fix:",
        "  1. Open the analysis.md for this session:",
    ]
    analysis_path = str(Path(session_dir) / "analysis.md") if session_dir else "<session_dir>/analysis.md"
    lines.append(f"       {analysis_path}")
    lines += [
        '  2. Find the JSON block and edit "maven_compile_cmd" / "maven_test_cmd".',
        '     Example: "mvn test-compile -q --no-transfer-progress -P my-profile"',
        "  3. Re-run: testboost generate && testboost validate",
        "",
        "  Maven output (last 30 lines):",
        "\n".join(maven_output.splitlines()[-30:]),
    ]
    for line in lines:
        logger.warn(line)


def _extract_json_field(markdown_content: str, field_name: str) -> Any:
    """Extract a field from a JSON block in a markdown file.

    Looks for ```json blocks in the markdown and extracts the named field.
    """
    json_blocks = re.findall(r"```json\n(.*?)```", markdown_content, re.DOTALL)
    for block in json_blocks:
        try:
            data = json.loads(block)
            if field_name in data:
                return data[field_name]
        except json.JSONDecodeError:
            continue
    return None


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="testboost-lite",
        description="TestBoost Lite - Lightweight markdown-driven test generation",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Initialize .testboost/ in a project")
    p_init.add_argument("project_path", help="Path to the Java project")
    p_init.add_argument("--name", help="Session name", default=None)
    p_init.add_argument("--description", help="What to test and why", default="")

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze project structure")
    p_analyze.add_argument("project_path", help="Path to the Java project")
    p_analyze.add_argument("--verbose", "-v", action="store_true")

    # gaps
    p_gaps = subparsers.add_parser("gaps", help="Identify test coverage gaps")
    p_gaps.add_argument("project_path", help="Path to the Java project")
    p_gaps.add_argument("--verbose", "-v", action="store_true")

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate tests")
    p_gen.add_argument("project_path", help="Path to the Java project")
    p_gen.add_argument("--files", nargs="*", help="Filter specific files")
    p_gen.add_argument("--verbose", "-v", action="store_true")

    # validate
    p_val = subparsers.add_parser("validate", help="Compile and run tests")
    p_val.add_argument("project_path", help="Path to the Java project")
    p_val.add_argument("--verbose", "-v", action="store_true")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify an integrity token")
    p_verify.add_argument("project_path", help="Path to the Java project")
    p_verify.add_argument("token", help="The full integrity token string to verify")

    # install
    p_install = subparsers.add_parser("install", help="Install TestBoost commands into a project")
    p_install.add_argument("project_path", help="Path to the Java project")

    # status
    p_status = subparsers.add_parser("status", help="Show session status")
    p_status.add_argument("project_path", help="Path to the Java project")

    args = parser.parse_args()

    commands = {
        "init": cmd_init,
        "analyze": cmd_analyze,
        "gaps": cmd_gaps,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "verify": cmd_verify,
        "install": cmd_install,
        "status": cmd_status,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
