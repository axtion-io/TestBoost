"""
Run tests tool for Maven projects.

Executes tests for a Maven project with various configuration options.
"""

import asyncio
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from src.mcp_servers.maven_maintenance.utils import get_mvn_command


async def run_tests(
    project_path: str,
    test_pattern: str = "**/Test*.java",
    profiles: list[str] | None = None,
    parallel: bool = False,
    fail_fast: bool = False,
) -> str:
    """
    Execute tests for a Maven project.

    Args:
        project_path: Path to the Maven project root directory
        test_pattern: Pattern to match test classes
        profiles: Maven profiles to activate
        parallel: Run tests in parallel
        fail_fast: Stop on first failure

    Returns:
        JSON string with test execution results
    """
    project_dir = Path(project_path)
    pom_file = project_dir / "pom.xml"

    if not pom_file.exists():
        return json.dumps({"success": False, "error": f"pom.xml not found at {project_path}"})

    # Build Maven command
    mvn = get_mvn_command()
    cmd = [mvn, "test", "-B"]

    # Add profiles if specified
    if profiles:
        cmd.append(f"-P{','.join(profiles)}")

    # Add test pattern
    if test_pattern != "**/Test*.java":
        cmd.append(f"-Dtest={test_pattern}")

    # Configure parallel execution
    if parallel:
        cmd.extend(["-DforkCount=1C", "-DreuseForks=true", "-Dparallel=methods", "-DthreadCount=4"])

    # Configure fail-fast behavior
    if fail_fast:
        cmd.append("-Dsurefire.skipAfterFailureCount=1")

    results: dict[str, Any] = {
        "success": False,
        "project_path": str(project_dir.absolute()),
        "command": " ".join(cmd),
        "summary": {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0},
        "failed_tests": [],
        "output": "",
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        output = stdout.decode("utf-8", errors="replace")
        error_output = stderr.decode("utf-8", errors="replace")

        results["output"] = output[-5000:] if len(output) > 5000 else output
        results["return_code"] = process.returncode

        # Parse test results from surefire reports
        test_summary = await _parse_surefire_reports(project_dir)
        results["summary"] = test_summary["summary"]
        results["failed_tests"] = test_summary["failed_tests"]

        # Also parse console output for quick summary
        console_summary = _parse_console_output(output)
        if not results["summary"]["total"] and console_summary["total"]:
            results["summary"] = console_summary

        if process.returncode == 0:
            results["success"] = True
            results["message"] = "All tests passed"
        else:
            results["success"] = False
            results["message"] = (
                f"Test failures: {results['summary']['failed']} failed, {results['summary']['errors']} errors"
            )
            if error_output:
                results["stderr"] = (
                    error_output[-1000:] if len(error_output) > 1000 else error_output
                )

    except FileNotFoundError:
        results["error"] = "Maven executable not found. Ensure Maven is installed and in PATH."
    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


async def _parse_surefire_reports(project_dir: Path) -> dict[str, Any]:
    """Parse Surefire XML reports for detailed test results."""
    summary: dict[str, int] = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}
    failed_tests: list[dict[str, Any]] = []
    result: dict[str, Any] = {
        "summary": summary,
        "failed_tests": failed_tests,
    }

    # Find surefire reports directory
    reports_dir = project_dir / "target" / "surefire-reports"
    if not reports_dir.exists():
        return result

    # Parse all XML reports
    for report_file in reports_dir.glob("TEST-*.xml"):
        try:
            tree = ET.parse(report_file)
            root = tree.getroot()

            # Get test suite statistics
            tests = int(root.get("tests", 0))
            failures = int(root.get("failures", 0))
            errors = int(root.get("errors", 0))
            skipped = int(root.get("skipped", 0))

            summary["total"] += tests
            summary["failed"] += failures
            summary["errors"] += errors
            summary["skipped"] += skipped
            summary["passed"] += tests - failures - errors - skipped

            # Get failed test details
            for testcase in root.findall(".//testcase"):
                failure = testcase.find("failure")
                error = testcase.find("error")

                if failure is not None or error is not None:
                    test_info = {
                        "class": testcase.get("classname", ""),
                        "method": testcase.get("name", ""),
                        "time": float(testcase.get("time", 0)),
                    }

                    if failure is not None:
                        test_info["type"] = "failure"
                        test_info["message"] = failure.get("message", "")[:500]
                    else:
                        test_info["type"] = "error"
                        test_info["message"] = (
                            error.get("message", "")[:500] if error is not None else ""
                        )

                    failed_tests.append(test_info)

        except Exception:
            continue

    return result


def _parse_console_output(output: str) -> dict[str, Any]:
    """Parse test summary from Maven console output."""
    summary = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errors": 0}

    # Look for the test summary line
    # Format: Tests run: X, Failures: Y, Errors: Z, Skipped: W
    for line in output.split("\n"):
        if "Tests run:" in line and "Failures:" in line:
            try:
                parts = line.split(",")
                for part in parts:
                    if "Tests run:" in part:
                        summary["total"] = int(part.split(":")[1].strip())
                    elif "Failures:" in part:
                        summary["failed"] = int(part.split(":")[1].strip())
                    elif "Errors:" in part:
                        summary["errors"] = int(part.split(":")[1].strip())
                    elif "Skipped:" in part:
                        summary["skipped"] = int(part.split(":")[1].strip())

                summary["passed"] = (
                    summary["total"] - summary["failed"] - summary["errors"] - summary["skipped"]
                )
                break
            except (ValueError, IndexError):
                continue

    return summary
