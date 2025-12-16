"""
Compile tests tool for Maven projects.

Compiles test sources for a Maven project.
"""

import asyncio
import contextlib
import json
import subprocess
from pathlib import Path
from typing import Any

from src.mcp_servers.maven_maintenance.utils import get_mvn_command


async def compile_tests(
    project_path: str, profiles: list[str] | None = None, skip_main: bool = False
) -> str:
    """
    Compile test sources for a Maven project.

    Args:
        project_path: Path to the Maven project root directory
        profiles: Maven profiles to activate
        skip_main: Skip main source compilation

    Returns:
        JSON string with compilation results
    """
    project_dir = Path(project_path)
    pom_file = project_dir / "pom.xml"

    if not pom_file.exists():
        return json.dumps({"success": False, "error": f"pom.xml not found at {project_path}"})

    # Build Maven command
    mvn = get_mvn_command()
    cmd = [mvn]

    # Add profiles if specified
    if profiles:
        cmd.append(f"-P{','.join(profiles)}")

    # Set compilation goal
    if skip_main:
        cmd.append("test-compile")
    else:
        cmd.append("test-compile")

    # Add common flags
    cmd.extend(
        [
            "-B",  # Batch mode
            "-q",  # Quiet mode (less output)
            "--fail-at-end",  # Continue on errors
        ]
    )

    results: dict[str, Any] = {
        "success": False,
        "project_path": str(project_dir.absolute()),
        "command": " ".join(cmd),
        "output": "",
        "errors": [],
        "warnings": [],
    }

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        output = stdout.decode("utf-8", errors="replace")
        error_output = stderr.decode("utf-8", errors="replace")

        results["output"] = output
        results["return_code"] = process.returncode

        # Parse output for errors and warnings
        errors, warnings = _parse_compilation_output(output + error_output)
        results["errors"] = errors
        results["warnings"] = warnings

        if process.returncode == 0:
            results["success"] = True
            results["message"] = "Test compilation successful"
        else:
            results["success"] = False
            results["message"] = "Test compilation failed"
            if error_output:
                results["stderr"] = error_output

    except FileNotFoundError:
        results["error"] = "Maven executable not found. Ensure Maven is installed and in PATH."
    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


def _parse_compilation_output(output: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Parse Maven compilation output for errors and warnings."""
    errors = []
    warnings = []

    lines = output.split("\n")

    for i, line in enumerate(lines):
        if "[ERROR]" in line:
            error_info = _extract_error_info(
                line, lines[i + 1 : i + 5] if i + 1 < len(lines) else []
            )
            if error_info:
                errors.append(error_info)
        elif "[WARNING]" in line:
            warning_info = _extract_warning_info(line)
            if warning_info:
                warnings.append(warning_info)

    return errors, warnings


def _extract_error_info(line: str, context_lines: list[str]) -> dict[str, Any] | None:
    """Extract error information from a Maven error line."""
    # Remove [ERROR] prefix
    message = line.replace("[ERROR]", "").strip()

    if not message:
        return None

    error_info: dict[str, Any] = {"message": message}

    # Try to extract file and line number
    # Format: /path/to/file.java:[line,col] error: message
    if ".java:" in message:
        parts = message.split(".java:")
        if len(parts) >= 2:
            file_path = parts[0] + ".java"
            rest = parts[1]

            # Extract line number
            if "[" in rest:
                line_part = rest.split("[")[1].split("]")[0]
                if "," in line_part:
                    line_num = line_part.split(",")[0]
                else:
                    line_num = line_part

                with contextlib.suppress(ValueError):
                    error_info["line"] = int(line_num)

            error_info["file"] = file_path

    # Add context if available
    context = []
    for ctx_line in context_lines:
        if ctx_line.strip() and not ctx_line.strip().startswith("["):
            context.append(ctx_line.strip())
        else:
            break

    if context:
        error_info["context"] = context

    return error_info


def _extract_warning_info(line: str) -> dict[str, Any] | None:
    """Extract warning information from a Maven warning line."""
    message = line.replace("[WARNING]", "").strip()

    if not message:
        return None

    return {"message": message}
