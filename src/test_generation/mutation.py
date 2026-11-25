"""
Run mutation testing tool using PIT.

Executes mutation testing to measure test effectiveness by introducing
small changes (mutants) and checking if tests can detect them.
"""

import asyncio
import json
import shutil
import subprocess
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _get_mvn_command() -> str:
    """Resolve the Maven executable path."""
    return shutil.which("mvn") or shutil.which("mvn.cmd") or "mvn"


async def run_mutation_testing(
    project_path: str,
    target_classes: list[str] | None = None,
    target_tests: list[str] | None = None,
    mutators: list[str] | None = None,
    timeout_factor: float = 1.5,
) -> str:
    """
    Run mutation testing using PIT.

    Args:
        project_path: Path to the Java project root directory
        target_classes: Classes to mutate (glob patterns)
        target_tests: Tests to run against mutants (glob patterns)
        mutators: Mutation operators to use
        timeout_factor: Factor to multiply normal test timeout

    Returns:
        JSON string with mutation testing results
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    pom_file = project_dir / "pom.xml"
    if not pom_file.exists():
        return json.dumps({"success": False, "error": "pom.xml not found - PIT requires Maven"})

    from src.java.pit import pit_goal, setup_problem

    problem = setup_problem(project_path)
    if problem:
        return json.dumps({"success": False, "error": problem})

    # Build PIT command: tests compiled first (PIT does not compile), the pom's PIT
    # version or TestBoost's pinned one, one fixed report directory per module.
    mvn = _get_mvn_command()
    cmd = [
        mvn,
        "test-compile",
        pit_goal(project_path),
        f"-DtimeoutFactor={timeout_factor}",
        "-DoutputFormats=XML,HTML",
        "-DtimestampedReports=false",
    ]

    if target_classes:
        cmd.append(f"-DtargetClasses={','.join(target_classes)}")

    if target_tests:
        cmd.append(f"-DtargetTests={','.join(target_tests)}")

    if mutators:
        cmd.append(f"-Dmutators={','.join(mutators)}")

    started = time.time()
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = await process.communicate()
        output = stdout.decode("utf-8", errors="replace")

        if process.returncode != 0:
            return json.dumps(
                {
                    "success": False,
                    "error": f"PIT execution failed: {stderr.decode('utf-8', errors='replace')}",
                    "output": output,
                }
            )

    except Exception as e:
        return json.dumps({"success": False, "error": f"Failed to run PIT: {e}"})

    # Parse results
    results = await _parse_pit_results(project_dir, since=started)

    return json.dumps(results, indent=2)


async def _parse_pit_results(project_dir: Path, since: float | None = None) -> dict[str, Any]:
    """Parse PIT results of every module (reports written since `since`: no stale report)."""
    mutations: dict[str, int] = {"total": 0, "killed": 0, "survived": 0, "no_coverage": 0, "timed_out": 0}
    by_class_list: list[dict[str, Any]] = []
    surviving_mutants: list[dict[str, Any]] = []

    results: dict[str, Any] = {
        "success": True,
        "mutation_score": 0,
        "mutations": mutations,
        "by_class": by_class_list,
        "surviving_mutants": surviving_mutants,
        "mutants": [],          # every mutant, with its status (`check --base` filters them by line)
        "report_path": "",
    }

    reports = [r for r in project_dir.rglob("pit-reports/**/mutations.xml")
               if since is None or r.stat().st_mtime >= since - 1]
    if not reports:
        results["error"] = "PIT report not found"
        return results
    results["report_path"] = str(reports[0].parent)
    results["report_paths"] = [str(r.parent) for r in sorted(reports)]

    try:
        by_class: dict[str, dict[str, int]] = {}
        all_mutations = [m for r in sorted(reports) for m in ET.parse(r).getroot().findall(".//mutation")]

        for mutation in all_mutations:
            status = mutation.get("status", "UNKNOWN")
            class_name = mutation.findtext("mutatedClass", "")
            method = mutation.findtext("mutatedMethod", "")
            line = mutation.findtext("lineNumber", "0")
            mutator = mutation.findtext("mutator", "")
            description = mutation.findtext("description", "")
            package = class_name.rsplit(".", 1)[0].replace(".", "/") if "." in class_name else ""
            source_file = f"{package}/{mutation.findtext('sourceFile', '')}".lstrip("/")
            results["mutants"].append({"class": class_name, "method": method, "line": int(line),
                                       "mutator": mutator, "description": description,
                                       "status": status, "source_file": source_file})

            mutations["total"] += 1

            if status == "KILLED":
                mutations["killed"] += 1
            elif status == "SURVIVED":
                mutations["survived"] += 1
                surviving_mutants.append(
                    {
                        "class": class_name,
                        "method": method,
                        "line": int(line),
                        "mutator": mutator,
                        "description": description,
                        "source_file": source_file,
                    }
                )
            elif status == "NO_COVERAGE":
                mutations["no_coverage"] += 1
            elif status == "TIMED_OUT":
                mutations["timed_out"] += 1

            # Track by class
            if class_name not in by_class:
                by_class[class_name] = {"killed": 0, "total": 0}
            by_class[class_name]["total"] += 1
            if status in ("KILLED", "TIMED_OUT"):  # detected, as in PIT
                by_class[class_name]["killed"] += 1

        # Calculate scores
        if mutations["total"] > 0:
            # PIT's convention: a mutant that times out was detected.
            results["mutation_score"] = round(
                ((mutations["killed"] + mutations["timed_out"]) / mutations["total"]) * 100, 1
            )

        # Format by-class results
        for class_name, counts in by_class.items():
            score = (
                round((counts["killed"] / counts["total"]) * 100, 1) if counts["total"] > 0 else 0
            )
            by_class_list.append(
                {
                    "class": class_name,
                    "killed": counts["killed"],
                    "total": counts["total"],
                    "score": score,
                }
            )

        # Sort by score (lowest first - these need attention)
        by_class_list.sort(key=lambda x: x["score"])

    except ET.ParseError as e:
        results["parse_error"] = str(e)

    return results
