#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""TestBoost CLI - Lightweight entry point.

This is the single CLI entry point that replaces the heavy FastAPI + Typer
stack. It is designed to be called from shell scripts, which are in turn
invoked by LLM CLI slash commands.

Usage:
    python -m src.lib.cli <command> <project_path> [options]

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
import shutil
import subprocess
import sys
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
    from pathlib import Path as _Path

    from src.lib.integrity import emit_token, get_or_create_secret
    from src.lib.plugins import get_registry
    from src.lib.session_tracker import create_session, init_project, set_session_technology

    project_path = args.project_path

    if not _Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    # --- Technology detection / selection (T016, T017, T018, T019) ---
    registry = get_registry()
    tech_arg = getattr(args, "tech", None)

    if tech_arg:
        # Explicit --tech override
        try:
            plugin = registry.get(tech_arg)
        except ValueError:
            available = [p["identifier"] for p in registry.list_plugins()]
            print(
                f"Error: Unknown technology '{tech_arg}'. "
                f"Available: {available}. "
                f"Run `testboost --list-plugins` to see all options.",
                file=sys.stderr,
            )
            return 1
        print(f"[+] Technology selected: {plugin.identifier}")
    else:
        # Auto-detect based on files present in project root
        plugin = registry.detect(_Path(project_path))
        if plugin is None:
            available = [p["identifier"] for p in registry.list_plugins()]
            print(
                "Error: Could not detect project technology. "
                f"No detection patterns matched. Available plugins: {available}. "
                "Use --tech <identifier> to specify explicitly.",
                file=sys.stderr,
            )
            return 1

        # Check if multiple plugins would match (T019)
        matched_plugins = [
            p for p in registry.list_plugins()
            if any((_Path(project_path) / pat).exists() for pat in p["detection_patterns"])
        ]
        if len(matched_plugins) > 1:
            others = [p["identifier"] for p in matched_plugins if p["identifier"] != plugin.identifier]
            print(
                f"[!] Multiple technology indicators found. Using: {plugin.identifier}. "
                f"Others: {others}. Override with --tech if needed."
            )
        else:
            matched_file = next(
                (pat for pat in plugin.detection_patterns if (_Path(project_path) / pat).exists()),
                plugin.detection_patterns[0],
            )
            print(f"[+] Technology detected: {plugin.identifier} (matched: {matched_file})")

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

    # Write technology to session metadata (T018)
    set_session_technology(_Path(session["session_dir"]), plugin.identifier)
    print(f"    Technology: {plugin.identifier}")

    emit_token(project_path, "init", session["session_id"])
    return 0


def cmd_analyze(args: argparse.Namespace) -> int:
    """Analyze project structure."""
    return asyncio.run(_cmd_analyze_async(args))


async def _cmd_analyze_async(args: argparse.Namespace) -> int:
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

    logger = MdLogger(session["session_dir"], "analysis", verbose=getattr(args, "verbose", False))

    # Mark step as in progress
    update_step_file(session["session_dir"], "analysis", STATUS_IN_PROGRESS, "# Analysis\n\nRunning...")

    logger.info("Starting project analysis...")

    try:
        # --- Reuse existing TestBoost functions via bridge ---
        from src.lib.bridge import (
            analyze_project_context,
            build_class_index,
            classify_file,
            detect_test_conventions,
            extract_test_examples,
            find_source_files,
            find_test_for_source,
        )
        from src.lib.session_tracker import (
            get_project_analysis_path,
            write_project_analysis,
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
            category = classify_file(sf, project_path)
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

        # Detect build configuration via plugin
        from src.lib.bridge import get_plugin_for_session
        from pathlib import Path as _Path
        analysis_plugin = get_plugin_for_session(project_path)
        compile_cmd_list = analysis_plugin.validation_command(_Path(project_path), {})
        test_cmd_list = analysis_plugin.test_run_command(_Path(project_path), {})
        compile_cmd_str = " ".join(compile_cmd_list)
        test_cmd_str = " ".join(test_cmd_list)

        # For Java: also detect Maven profiles and .mvn/maven.config
        maven_config_notes: list[str] = []
        if analysis_plugin.identifier == "java-spring":
            from src.lib.plugins.java_spring import _detect_maven_build_config
            maven_config = _detect_maven_build_config(project_path)
            compile_cmd_str = maven_config["compile_cmd"]
            test_cmd_str = maven_config["test_cmd"]
            maven_config_notes = maven_config["notes"]

        content += "## Build Configuration\n\n"
        content += f"- **Compile command**: `{compile_cmd_str}`\n"
        content += f"- **Test command**: `{test_cmd_str}`\n"
        for note in maven_config_notes:
            content += f"- {note}\n"
        content += "\n"

        # --- Build class index (project-level, persisted across sessions) ---
        logger.info(f"Building class index for {len(source_files)} source files...")
        class_index = build_class_index(project_path, source_files)
        logger.info(f"Class index built: {len(class_index)} classes analyzed")

        # Class index summary table
        content += "## Class Index\n\n"
        content += "| Class | Package | Category | Extends | Has Test |\n"
        content += "|-------|---------|----------|---------|----------|\n"
        tested_classes = {Path(fd["path"]).stem for fd in file_details if fd["has_test"]}
        for cls_name, entry in sorted(class_index.items()):
            pkg = entry.get("package", "")
            cat = entry.get("category", "")
            ext = entry.get("extends") or "-"
            has_test_cls = "Yes" if cls_name in tested_classes else "No"
            content += f"| `{cls_name}` | `{pkg}` | {cat} | {ext} | {has_test_cls} |\n"
        content += "\n"

        # --- Extract test examples (for LLM style reference) ---
        test_examples = extract_test_examples(project_path, max_examples=3, max_lines=150)
        if test_examples:
            content += "## Test Pattern Examples\n\n"
            for i, ex in enumerate(test_examples, 1):
                content += f"### Example {i}: `{ex['path']}`\n\n"
                content += f"```java\n{ex['content']}\n```\n\n"

        logger.info(f"Analysis complete: {len(source_files)} source files, {len(class_index)} classes indexed, {len(test_examples)} test examples")

        # --- Write project-level analysis.md (.testboost/analysis.md) ---
        project_analysis_data = {
            "project_context": result,
            "conventions": conventions,
            "source_files": source_files,
            "source_file_details": file_details,
            "maven_compile_cmd": compile_cmd_str,
            "maven_test_cmd": test_cmd_str,
            "class_index": class_index,
            "test_examples": test_examples,
        }
        project_analysis_path = write_project_analysis(project_path, content, project_analysis_data)
        logger.info(f"Project-level analysis written to: {project_analysis_path}")

        # --- Write session-level analysis.md (lightweight reference) ---
        session_content = (
            "# Session Analysis\n\n"
            f"This session uses the project-level analysis at "
            f"`{get_project_analysis_path(project_path)}`.\n\n"
            "## Build Command Overrides\n\n"
            "> Edit `maven_compile_cmd` / `maven_test_cmd` in the JSON block below\n"
            "> to customize build commands for this session only.\n\n"
        )
        update_step_file(
            session["session_dir"], "analysis", STATUS_COMPLETED, session_content,
            data={
                "maven_compile_cmd": compile_cmd_str,
                "maven_test_cmd": test_cmd_str,
                "project_analysis_path": str(project_analysis_path),
            },
        )

        # Print summary to stdout for the LLM
        logger.result("Analysis Complete", content)

        from src.lib.integrity import emit_token
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
    logger = MdLogger(session_dir, "coverage-gaps", verbose=getattr(args, "verbose", False))

    # Check that analysis was done
    analysis_file = Path(session_dir) / "analysis.md"
    if not analysis_file.exists():
        logger.error("Analysis step not completed. Run `analyze` first.")
        return 1

    update_step_file(session_dir, "coverage-gaps", STATUS_IN_PROGRESS, "# Coverage Gaps\n\nIdentifying...")

    logger.info("Identifying test coverage gaps...")

    try:
        # Read source_files: project-level analysis first, session fallback for backward compat
        from src.lib.session_tracker import read_project_analysis_data
        source_files = None
        project_data = read_project_analysis_data(project_path)
        if project_data:
            source_files = project_data.get("source_files")

        if not source_files:
            analysis_content = analysis_file.read_text(encoding="utf-8")
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

        from src.lib.integrity import emit_token
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

        # Load analysis data: project-level for class_index/test_examples/conventions,
        # session-level for maven command overrides (allows per-session customization).
        from src.lib.session_tracker import read_project_analysis_data
        class_index = None
        test_examples = None
        conventions = None
        maven_compile_cmd = None

        project_data = read_project_analysis_data(project_path)
        if project_data:
            class_index = project_data.get("class_index")
            test_examples = project_data.get("test_examples")
            conventions = project_data.get("conventions")
            maven_compile_cmd = project_data.get("maven_compile_cmd")
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
            if session_conventions:
                conventions = session_conventions
            if session_compile_cmd:
                maven_compile_cmd = session_compile_cmd

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

        generated = []
        for source_file in target_files:
            logger.info(f"Generating tests for: {source_file}")
            try:
                # --- Edge case analysis (enriches test generation) ---
                edge_cases: list[dict] = []
                try:
                    source_path = Path(source_file)
                    if not source_path.exists():
                        source_path = Path(project_path) / source_file
                    if source_path.exists():
                        source_code = source_path.read_text(encoding="utf-8", errors="replace")
                        class_name = source_path.stem
                        # Determine class type from class_index or heuristic
                        class_type = "service"
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
                            logger.info(f"Edge case analysis: {len(edge_cases)} scenarios for {class_name}")
                except Exception as ec_err:
                    logger.warn(f"Edge case analysis skipped for {source_file}: {ec_err}")

                result_json = await generate_adaptive_tests(
                    project_path=project_path,
                    source_file=source_file,
                    conventions=conventions,
                    class_index=class_index,
                    test_examples=test_examples,
                    test_requirements=edge_cases if edge_cases else None,
                    prompt_template_dir=prompt_template_dir,
                )
                result = json.loads(result_json)
                test_code = result.get("test_code", "")
                # Technology-aware validation: Java uses @Test, Python uses def test_
                has_tests = "@Test" in test_code or "def test_" in test_code
                if result.get("success") and test_code and has_tests:
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

        from src.lib.integrity import emit_token
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
    from src.lib.plugins.java_spring import _parse_maven_cmd as _java_parse_maven_cmd
    try:
        cmd = _java_parse_maven_cmd(maven_compile_cmd) if maven_compile_cmd else None
    except ValueError as e:
        logger.warn(f"Invalid maven_compile_cmd, using default: {e}")
        cmd = None
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
            from src.lib.bridge import fix_compilation_errors
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
    logger = MdLogger(session_dir, "validation", verbose=getattr(args, "verbose", False))

    # Check prerequisites
    gen_file = Path(session_dir) / "generation.md"
    if not gen_file.exists():
        logger.error("Generation step not completed. Run `generate` first.")
        return 1

    update_step_file(session_dir, "validation", STATUS_IN_PROGRESS, "# Validation\n\nCompiling and testing...")

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

        compile_cmd = plugin.validation_command(_Path(project_path), session_config)
        test_run_cmd = plugin.test_run_command(_Path(project_path), session_config)

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
            from src.lib.integrity import emit_token
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
    logger = MdLogger(session_dir, "killer-tests", verbose=getattr(args, "verbose", False))

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

        result_json = await generate_killer_tests(
            project_path, surviving_mutants, max_tests=max_tests,
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
                fixed = await _attempt_compile_fix(
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

        from src.lib.integrity import emit_token
        emit_token(project_path, "killer-tests", session["session_id"])
        return 0

    except Exception as e:
        logger.error(f"Killer test generation failed: {e}")
        update_step_file(
            session_dir, "killer-tests", STATUS_FAILED,
            f"# Killer Tests - FAILED\n\n**Error**: {e}\n",
        )
        return 1


def _prompt_shell_type() -> str:
    """Prompt the user to choose between bash and powershell scripts."""
    print("Which shell type do you want for wrapper scripts?")
    print("  1) bash       (Linux / macOS / Git Bash)")
    print("  2) powershell (Windows PowerShell)")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            return "bash"
        if choice == "2":
            return "powershell"
        print("Invalid choice. Please enter 1 or 2.")


def cmd_install(args: argparse.Namespace) -> int:
    """Install TestBoost commands into a target project.

    Copies slash-command markdown files and shell scripts to the target
    project, with paths resolved to the current TestBoost installation.
    This ensures the LLM CLI always calls the real TestBoost CLI.
    """
    from src.lib.installer import install_commands

    project_path = args.project_path
    if not Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    shell_type = args.shell_type
    if shell_type is None:
        shell_type = _prompt_shell_type()

    result = install_commands(
        project_path=project_path,
        testboost_root=str(TESTBOOST_ROOT),
        shell_type=shell_type,
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
    from src.lib.integrity import verify_token

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
    from pathlib import Path as _Path

    from src.lib.session_tracker import (
        get_current_session,
        get_session_status,
        get_session_technology,
    )

    status = get_session_status(args.project_path)

    # Prepend technology info to the status output
    session = get_current_session(args.project_path)
    if session:
        technology = get_session_technology(_Path(session["session_dir"]))
        print(f"**Technology**: {technology}")
        print()

    print(status)
    return 0


# --- Helpers ---


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


def _read_step_status(step_file: Path) -> str:
    """Read the status from a step markdown file's YAML frontmatter.

    Returns the status string (e.g. "completed", "failed", "in_progress")
    or "unknown" if the file cannot be parsed.
    """
    try:
        content = step_file.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        if match:
            for line in match.group(1).split("\n"):
                if line.startswith("status:"):
                    return line.partition(":")[2].strip()
    except OSError:
        pass
    return "unknown"


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
        prog="testboost",
        description="TestBoost - Lightweight markdown-driven test generation",
    )
    parser.add_argument(
        "--list-plugins",
        action="store_true",
        help="List all available technology plugins and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    p_init = subparsers.add_parser("init", help="Initialize .testboost/ in a project")
    p_init.add_argument("project_path", help="Path to the project")
    p_init.add_argument("--name", help="Session name", default=None)
    p_init.add_argument("--description", help="What to test and why", default="")
    p_init.add_argument("--tech", help="Technology plugin identifier (e.g. java-spring, python-pytest)", default=None)

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

    # mutate
    p_mutate = subparsers.add_parser("mutate", help="Run mutation testing with PIT")
    p_mutate.add_argument("project_path", help="Path to the Java project")
    p_mutate.add_argument("--target-classes", nargs="*", help="Class patterns to mutate")
    p_mutate.add_argument("--target-tests", nargs="*", help="Test patterns to run")
    p_mutate.add_argument("--min-score", type=float, default=80, help="Minimum mutation score threshold")
    p_mutate.add_argument("--verbose", "-v", action="store_true")

    # killer
    p_killer = subparsers.add_parser("killer", help="Generate killer tests for surviving mutants")
    p_killer.add_argument("project_path", help="Path to the Java project")
    p_killer.add_argument("--max-tests", type=int, default=10, help="Maximum killer tests to generate")
    p_killer.add_argument("--verbose", "-v", action="store_true")

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify an integrity token")
    p_verify.add_argument("project_path", help="Path to the Java project")
    p_verify.add_argument("token", help="The full integrity token string to verify")

    # install
    p_install = subparsers.add_parser("install", help="Install TestBoost commands into a project")
    p_install.add_argument("project_path", help="Path to the Java project")
    p_install.add_argument(
        "--shell-type",
        choices=["bash", "powershell"],
        default=None,
        help="Shell type for wrapper scripts (prompted if not specified)",
    )

    # status
    p_status = subparsers.add_parser("status", help="Show session status")
    p_status.add_argument("project_path", help="Path to the Java project")

    args = parser.parse_args()

    # T020: --list-plugins exits before any subcommand is required
    if args.list_plugins:
        from src.lib.plugins import get_registry
        for plugin_info in get_registry().list_plugins():
            print(f"  {plugin_info['identifier']}")
            print(f"    Description : {plugin_info['description']}")
            print(f"    Detects     : {', '.join(plugin_info['detection_patterns'])}")
            print()
        return 0

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "analyze": cmd_analyze,
        "gaps": cmd_gaps,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "mutate": cmd_mutate,
        "killer": cmd_killer,
        "verify": cmd_verify,
        "install": cmd_install,
        "status": cmd_status,
    }

    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
