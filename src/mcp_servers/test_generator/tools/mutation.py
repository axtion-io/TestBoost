"""
Run mutation testing tool using PIT.

Executes mutation testing to measure test effectiveness by introducing
small changes (mutants) and checking if tests can detect them.
"""

import asyncio
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


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

    # Build PIT command
    cmd = [
        "mvn",
        "org.pitest:pitest-maven:mutationCoverage",
        f"-DtimeoutFactor={timeout_factor}",
        "-DoutputFormats=XML,HTML",
    ]

    if target_classes:
        cmd.append(f"-DtargetClasses={','.join(target_classes)}")

    if target_tests:
        cmd.append(f"-DtargetTests={','.join(target_tests)}")

    if mutators:
        cmd.append(f"-Dmutators={','.join(mutators)}")

    # Run PIT
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
    results = await _parse_pit_results(project_dir)

    return json.dumps(results, indent=2)


async def _parse_pit_results(project_dir: Path) -> dict[str, Any]:
    """Parse PIT mutation testing results."""
    results = {
        "success": True,
        "mutation_score": 0,
        "mutations": {"total": 0, "killed": 0, "survived": 0, "no_coverage": 0, "timed_out": 0},
        "by_class": [],
        "surviving_mutants": [],
        "report_path": "",
    }

    # Find PIT report
    pit_reports = list(project_dir.rglob("pit-reports/**/mutations.xml"))
    if not pit_reports:
        results["error"] = "PIT report not found"
        return results

    report_file = pit_reports[0]
    results["report_path"] = str(report_file.parent)

    # Parse XML report
    try:
        tree = ET.parse(report_file)
        root = tree.getroot()

        by_class = {}

        for mutation in root.findall(".//mutation"):
            status = mutation.get("status", "UNKNOWN")
            class_name = mutation.findtext("mutatedClass", "")
            method = mutation.findtext("mutatedMethod", "")
            line = mutation.findtext("lineNumber", "0")
            mutator = mutation.findtext("mutator", "")
            description = mutation.findtext("description", "")

            results["mutations"]["total"] += 1

            if status == "KILLED":
                results["mutations"]["killed"] += 1
            elif status == "SURVIVED":
                results["mutations"]["survived"] += 1
                results["surviving_mutants"].append(
                    {
                        "class": class_name,
                        "method": method,
                        "line": int(line),
                        "mutator": mutator,
                        "description": description,
                    }
                )
            elif status == "NO_COVERAGE":
                results["mutations"]["no_coverage"] += 1
            elif status == "TIMED_OUT":
                results["mutations"]["timed_out"] += 1

            # Track by class
            if class_name not in by_class:
                by_class[class_name] = {"killed": 0, "total": 0}
            by_class[class_name]["total"] += 1
            if status == "KILLED":
                by_class[class_name]["killed"] += 1

        # Calculate scores
        if results["mutations"]["total"] > 0:
            results["mutation_score"] = round(
                (results["mutations"]["killed"] / results["mutations"]["total"]) * 100, 1
            )

        # Format by-class results
        for class_name, counts in by_class.items():
            score = (
                round((counts["killed"] / counts["total"]) * 100, 1) if counts["total"] > 0 else 0
            )
            results["by_class"].append(
                {
                    "class": class_name,
                    "killed": counts["killed"],
                    "total": counts["total"],
                    "score": score,
                }
            )

        # Sort by score (lowest first - these need attention)
        results["by_class"].sort(key=lambda x: x["score"])

    except ET.ParseError as e:
        results["parse_error"] = str(e)

    return results
