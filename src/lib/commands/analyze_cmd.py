# SPDX-License-Identifier: Apache-2.0
"""testboost analyze + gaps — project analysis and coverage gaps."""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from src.lib.commands._shared import _extract_json_field


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
            get_plugin_for_session,
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
        existing_tests = find_existing_tests(
            project_path, get_plugin_for_session(project_path), source_files
        )
        file_details = []
        for sf in source_files:
            category = classify_file(sf, project_path)
            test_file = existing_tests.get(sf)
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
# Directories never scanned for tests (build output, VCS, virtualenvs).
_NON_PROJECT_DIRS = {".git", ".testboost", "target", "build", "node_modules", ".venv", "venv"}


def _tested_stems(project_dir: Path, patterns: list[str], source_files: set[str]) -> dict[str, str]:
    """Map each source stem that already has a test to that test's relative path.

    Derived from the plugin's test globs.

    Each glob's file name is read as prefix*suffix: `**/*Test.java` names
    `FooTest.java` after `Foo`, `**/test_*.py` names `test_foo.py` after
    `foo`. Only the affix is stripped (`TestDataBuilderTest` -> `TestDataBuilder`),
    and files that are themselves sources (e.g. `TestUtils.java` under
    src/main matched by `Test*.java`) are not tests.
    """
    stems: dict[str, str] = {}
    for pattern in patterns:
        stem_pattern = pattern.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        prefix, star, suffix = stem_pattern.partition("*")
        if not star:
            continue
        for test_file in sorted(project_dir.glob(pattern)):
            rel = test_file.relative_to(project_dir)
            if _NON_PROJECT_DIRS.intersection(rel.parts) or rel.as_posix() in source_files:
                continue
            stem = test_file.stem
            if len(stem) > len(prefix) + len(suffix) and stem.startswith(prefix) and stem.endswith(suffix):
                stems.setdefault(stem[len(prefix):len(stem) - len(suffix)], rel.as_posix())
    return stems


def find_existing_tests(project_path: str, plugin, source_files: list[str]) -> dict[str, str]:
    """Map each source file that already has a test to that test's path.

    Shared by `analyze` (Has Test column) and `gaps` (what to generate), so
    the two steps can never disagree. A source is tested when the test the
    plugin would generate exists, or when a test matching the plugin's globs
    is named after it.
    """
    project_dir = Path(project_path)
    by_stem = _tested_stems(project_dir, plugin.test_file_pattern(), set(source_files))
    found: dict[str, str] = {}
    for source_file in source_files:
        expected = plugin.test_file_name(source_file)
        if (project_dir / expected).exists():
            found[source_file] = expected
        elif Path(source_file).stem in by_stem:
            found[source_file] = by_stem[Path(source_file).stem]
    return found


def _file_level_gaps(project_path: str, plugin, source_files: list[str]) -> tuple[str, dict]:
    """A source is covered when the test the plugin would generate exists, or a test matching
    the plugin's globs is named after it (`find_existing_tests`)."""
    tested = find_existing_tests(project_path, plugin, source_files)
    covered = [sf for sf in source_files if sf in tested]
    gaps = [sf for sf in source_files if sf not in tested]
    total = len(source_files)
    pct = ((total - len(gaps)) / total * 100) if total else 0

    content = "# Coverage Gap Analysis\n\n"
    content += f"**Total testable files**: {total}\n"
    content += f"**Files with tests**: {len(covered)}\n"
    content += f"**Files WITHOUT tests**: {len(gaps)}\n"
    content += (f"**Files with a test**: {pct:.0f}% (file-level, not line coverage — "
                "`gaps --coverage` measures it with JaCoCo)\n\n")
    if gaps:
        content += "## Files Needing Tests\n\n| # | Source File | Priority |\n|---|------------|----------|\n"
        for i, gap in enumerate(gaps, 1):
            priority = "high" if "service" in gap.lower() or "controller" in gap.lower() else "medium"
            content += f"| {i} | `{gap}` | {priority} |\n"
        content += "\n"
    if covered:
        content += "## Files Already Covered\n\n" + "".join(f"- `{c}`\n" for c in covered) + "\n"
    return content, {"mode": "file", "gaps": gaps, "covered": covered, "coverage_pct": pct}


def maven_session_config(project_path: str, session_dir: str | None) -> dict:
    """The Maven commands detected by `analyze` (profiles, -D flags), session first."""
    from src.lib.session_tracker import read_project_analysis_data

    data = read_project_analysis_data(project_path) or {}
    config = {k: data[k] for k in ("maven_compile_cmd", "maven_test_cmd") if data.get(k)}
    analysis = Path(session_dir) / "analysis.md" if session_dir else None
    if analysis and analysis.exists():
        text = analysis.read_text(encoding="utf-8")
        for k in ("maven_compile_cmd", "maven_test_cmd"):
            config[k] = _extract_json_field(text, k) or config.get(k)
    return {k: v for k, v in config.items() if v}


def _coverage_gaps(project_path: str, session_dir: str, plugin, source_files: list[str],
                   min_coverage: float, logger) -> tuple[str, dict] | None:
    """Gaps = source files whose JaCoCo line coverage is below `min_coverage`, most missed lines first."""
    import subprocess

    from src.java.coverage import read_reports, run_jacoco
    from src.lib.session_tracker import load_project_config

    if plugin.identifier != "java-spring":
        logger.error(f"`gaps --coverage` measures JaCoCo coverage: Java/Maven only (not {plugin.identifier}).")
        return None
    session_config = maven_session_config(project_path, session_dir)
    timeout = load_project_config(project_path)["test_timeout_seconds"]
    logger.info("Measuring line coverage with JaCoCo (runs the test suite)...")
    try:
        result = run_jacoco(project_path, plugin.test_run_command(Path(project_path), session_config), timeout)
    except (ValueError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.error(f"JaCoCo run failed: {e}")
        return None
    coverage = read_reports(project_path)
    if not coverage:
        logger.error("No JaCoCo report produced. Maven output (last 30 lines):\n"
                     + "\n".join((result.stdout + result.stderr).splitlines()[-30:]))
        return None

    absent = {"line_pct": 0.0, "missed": None, "covered": 0, "uncovered": "all", "partial": ""}
    per_file = {sf: coverage.get(sf, absent) for sf in source_files}
    gaps = sorted((sf for sf in source_files if per_file[sf]["line_pct"] < min_coverage),
                  key=lambda sf: (-(per_file[sf]["missed"] or 10**6), sf))
    covered = [sf for sf in source_files if sf not in gaps]
    missed = sum(v["missed"] or 0 for v in coverage.values())
    hit = sum(v["covered"] for v in coverage.values())
    total_pct = round(100.0 * hit / (hit + missed), 1) if hit + missed else 0.0

    content = "# Coverage Gap Analysis (JaCoCo line coverage)\n\n"
    content += f"**Line coverage**: {total_pct}% ({hit} of {hit + missed} lines)\n"
    content += f"**Threshold**: {min_coverage}% per class\n"
    content += f"**Classes below the threshold**: {len(gaps)} of {len(source_files)}\n\n"
    if gaps:
        content += ("## Files Needing Tests\n\n| # | Source File | Line coverage | Uncovered lines |"
                    "\n|---|---|---|---|\n")
        for i, sf in enumerate(gaps, 1):
            info = per_file[sf]
            content += f"| {i} | `{sf}` | {info['line_pct']}% | {info['uncovered'] or '-'} |\n"
        content += "\n"
    return content, {"mode": "coverage", "min_coverage": min_coverage, "gaps": gaps, "covered": covered,
                     "coverage_pct": total_pct, "coverage": {sf: {k: v for k, v in per_file[sf].items() if k != "lines"} for sf in gaps}}


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

        from src.lib.bridge import get_plugin_for_session
        plugin = get_plugin_for_session(project_path)
        if getattr(args, "coverage", False):
            measured = _coverage_gaps(project_path, session_dir, plugin, source_files,
                                      getattr(args, "min_coverage", 80.0), logger)
            if measured is None:
                update_step_file(session_dir, "coverage-gaps", STATUS_FAILED,
                                 "# Coverage Gaps - FAILED\n\n**Error**: line coverage could not be measured "
                                 "(see the log); run `gaps` without `--coverage` for file-level gaps.\n")
                return 1
            content, data = measured
        else:
            content, data = _file_level_gaps(project_path, plugin, source_files)
        logger.info(f"Found {len(data['gaps'])} gap(s) out of {len(source_files)} source files")
        update_step_file(session_dir, "coverage-gaps", STATUS_COMPLETED, content, data=data)

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
