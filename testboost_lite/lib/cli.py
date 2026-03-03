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
import sys
from pathlib import Path
from typing import Any

# Add the TestBoost root to path so we can import existing modules
TESTBOOST_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(TESTBOOST_ROOT))


def cmd_init(args: argparse.Namespace) -> int:
    """Initialize .testboost/ in a project."""
    from testboost_lite.lib.session_tracker import init_project, create_session

    project_path = args.project_path

    if not Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    # Initialize directory structure
    result = init_project(project_path)
    print(f"[+] {result['message']}")

    # Create initial session
    session = create_session(
        project_path,
        name=args.name if hasattr(args, "name") and args.name else None,
        description=args.description if hasattr(args, "description") and args.description else "",
    )
    print(f"[+] {session['message']}")
    print(f"    Session directory: {session['session_dir']}")
    print(f"    Session ID: {session['session_id']}")

    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze project structure."""
    return asyncio.run(_cmd_analyze_async(args))


async def _cmd_analyze_async(args: argparse.Namespace) -> int:
    from testboost_lite.lib.session_tracker import (
        get_current_session,
        update_step_file,
        STATUS_IN_PROGRESS,
        STATUS_COMPLETED,
        STATUS_FAILED,
    )
    from testboost_lite.lib.md_logger import MdLogger

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
        # --- Reuse existing TestBoost analyze function ---
        from src.mcp_servers.test_generator.tools.analyze import analyze_project_context

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

        # --- Reuse existing TestBoost conventions detection ---
        from src.mcp_servers.test_generator.tools.conventions import detect_test_conventions

        conventions_json = await detect_test_conventions(project_path)
        conventions = json.loads(conventions_json)

        # --- Reuse existing TestBoost source file finder ---
        from src.workflows.test_generation_agent import _find_source_files

        source_files = _find_source_files(project_path)

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

        # Source files to test
        content += "## Source Files for Test Generation\n\n"
        content += f"Found **{len(source_files)}** testable source files:\n\n"
        for sf in source_files:
            content += f"- `{sf}`\n"
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

        logger.info(f"Analysis complete: {len(source_files)} source files, {src_struct.get('class_count', 0)} classes")

        # Write the step file
        update_step_file(
            session["session_dir"], "analysis", STATUS_COMPLETED, content,
            data={
                "project_context": result,
                "conventions": conventions,
                "source_files": source_files,
            },
        )

        # Print summary to stdout for the LLM
        logger.result("Analysis Complete", content)

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
    from testboost_lite.lib.session_tracker import (
        get_current_session,
        update_step_file,
        STATUS_IN_PROGRESS,
        STATUS_COMPLETED,
        STATUS_FAILED,
    )
    from testboost_lite.lib.md_logger import MdLogger

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
    from testboost_lite.lib.session_tracker import (
        get_current_session,
        update_step_file,
        STATUS_IN_PROGRESS,
        STATUS_COMPLETED,
        STATUS_FAILED,
    )
    from testboost_lite.lib.md_logger import MdLogger

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

        # Apply file filter if specified
        target_files = gaps
        if hasattr(args, "files") and args.files:
            target_files = [f for f in gaps if any(pattern in f for pattern in args.files)]
            if not target_files:
                logger.warn(f"No files matched filter: {args.files}")
                target_files = gaps

        logger.info(f"Generating tests for {len(target_files)} files...")

        # --- Reuse existing TestBoost test generation ---
        from src.workflows.test_generation_agent import _generate_tests_directly

        use_llm = not getattr(args, "no_llm", False)
        generated = await _generate_tests_directly(
            project_path=project_path,
            source_files=target_files,
            use_llm=use_llm,
        )

        # Build generation report
        content = "# Test Generation Results\n\n"
        content += f"**Target files**: {len(target_files)}\n"
        content += f"**Tests generated**: {len(generated)}\n"
        content += f"**LLM mode**: {'yes' if use_llm else 'template only'}\n\n"

        if generated:
            content += "## Generated Tests\n\n"
            content += "| # | Source File | Test File | Test Count |\n"
            content += "|---|------------|-----------|------------|\n"
            for i, test in enumerate(generated, 1):
                content += f"| {i} | `{test.get('source_file', '')}` | `{test.get('path', '')}` | {test.get('test_count', 0)} |\n"
            content += "\n"

            # Write the actual test files
            content += "## Generated Test Files\n\n"
            for test in generated:
                test_path = test.get("path", "")
                test_content = test.get("content", "")
                if test_path and test_content:
                    # Write the test file to the project
                    full_path = Path(project_path) / test_path
                    full_path.parent.mkdir(parents=True, exist_ok=True)
                    full_path.write_text(test_content, encoding="utf-8")
                    logger.info(f"Wrote test file: {test_path}")
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
        return 0

    except Exception as e:
        logger.error(f"Test generation failed: {e}")
        update_step_file(
            session_dir, "generation", STATUS_FAILED,
            f"# Test Generation - FAILED\n\n**Error**: {e}\n",
        )
        return 1


def cmd_validate(args: argparse.Namespace) -> int:
    """Compile and validate generated tests."""
    return asyncio.run(_cmd_validate_async(args))


async def _cmd_validate_async(args: argparse.Namespace) -> int:
    import subprocess
    import shutil

    from testboost_lite.lib.session_tracker import (
        get_current_session,
        update_step_file,
        STATUS_IN_PROGRESS,
        STATUS_COMPLETED,
        STATUS_FAILED,
    )
    from testboost_lite.lib.md_logger import MdLogger

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
        # Find Maven executable
        mvn = shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn"

        content = "# Validation Results\n\n"

        # Step 1: Compile tests
        logger.info("Compiling tests with Maven...")
        compile_result = subprocess.run(
            [mvn, "test-compile", "-q"],
            cwd=project_path,
            capture_output=True,
            text=True,
            timeout=120,
        )

        if compile_result.returncode != 0:
            # --- Reuse MavenErrorParser for structured error feedback ---
            from src.lib.maven_error_parser import MavenErrorParser

            parser = MavenErrorParser()
            errors = parser.parse(compile_result.stdout + compile_result.stderr)

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
        logger.info("Running tests with Maven...")
        test_timeout = 300  # 5 minutes
        test_result = subprocess.run(
            [mvn, "test", "-q"],
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
            import re
            test_count_match = re.search(r"Tests run: (\d+)", test_output)
            if test_count_match:
                content += f"**Tests run**: {test_count_match.group(1)}\n"

            logger.info("All tests passed")
            status = STATUS_COMPLETED
        else:
            content += "## Tests: FAILED\n\n"

            # Extract failure details
            failure_lines = [
                l for l in test_output.split("\n")
                if "FAIL" in l or "ERROR" in l or "Tests run:" in l
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


def cmd_status(args: argparse.Namespace) -> int:
    """Show current session status."""
    from testboost_lite.lib.session_tracker import get_session_status

    status = get_session_status(args.project_path)
    print(status)
    return 0


# --- Helpers ---

def _extract_json_field(markdown_content: str, field_name: str) -> Any:
    """Extract a field from a JSON block in a markdown file.

    Looks for ```json blocks in the markdown and extracts the named field.
    """
    import re
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
    p_gen.add_argument("--no-llm", action="store_true", help="Use template mode (no LLM)")
    p_gen.add_argument("--verbose", "-v", action="store_true")

    # validate
    p_val = subparsers.add_parser("validate", help="Compile and run tests")
    p_val.add_argument("project_path", help="Path to the Java project")
    p_val.add_argument("--verbose", "-v", action="store_true")

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
        "status": cmd_status,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
