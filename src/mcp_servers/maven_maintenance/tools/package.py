"""
Package tool for Maven projects.

Packages a Maven project into its distributable format.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def package_project(
    project_path: str, skip_tests: bool = False, profiles: list[str] | None = None
) -> str:
    """
    Package a Maven project.

    Args:
        project_path: Path to the Maven project root directory
        skip_tests: Skip test execution during packaging
        profiles: Maven profiles to activate

    Returns:
        JSON string with packaging results
    """
    project_dir = Path(project_path)
    pom_file = project_dir / "pom.xml"

    if not pom_file.exists():
        return json.dumps({"success": False, "error": f"pom.xml not found at {project_path}"})

    # Build Maven command
    cmd = ["mvn", "package", "-B"]

    # Add profiles if specified
    if profiles:
        cmd.append(f"-P{','.join(profiles)}")

    # Skip tests if requested
    if skip_tests:
        cmd.append("-DskipTests")

    results: dict[str, Any] = {
        "success": False,
        "project_path": str(project_dir.absolute()),
        "command": " ".join(cmd),
        "artifacts": [],
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

        if process.returncode == 0:
            results["success"] = True
            results["message"] = "Package build successful"

            # Find generated artifacts
            artifacts = await _find_artifacts(project_dir)
            results["artifacts"] = artifacts
        else:
            results["success"] = False
            results["message"] = "Package build failed"

            # Extract error information
            errors = _extract_build_errors(output + error_output)
            results["errors"] = errors

            if error_output:
                results["stderr"] = (
                    error_output[-1000:] if len(error_output) > 1000 else error_output
                )

    except FileNotFoundError:
        results["error"] = "Maven executable not found. Ensure Maven is installed and in PATH."
    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


async def _find_artifacts(project_dir: Path) -> list[dict[str, Any]]:
    """Find generated artifacts in the target directory."""
    artifacts = []
    target_dir = project_dir / "target"

    if not target_dir.exists():
        return artifacts

    # Common artifact extensions
    artifact_extensions = [".jar", ".war", ".ear", ".zip", ".tar.gz"]

    for ext in artifact_extensions:
        for artifact_file in target_dir.glob(f"*{ext}"):
            # Skip sources and javadoc jars
            name = artifact_file.name
            if "-sources" in name or "-javadoc" in name or "-tests" in name:
                continue

            # Skip original (unshaded) jars
            if name.startswith("original-"):
                continue

            stat = artifact_file.stat()
            artifacts.append(
                {
                    "name": name,
                    "path": str(artifact_file.absolute()),
                    "size": stat.st_size,
                    "size_human": _format_size(stat.st_size),
                }
            )

    return artifacts


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _extract_build_errors(output: str) -> list[dict[str, Any]]:
    """Extract build errors from Maven output."""
    errors = []

    lines = output.split("\n")
    in_error_block = False
    current_error: dict[str, Any] = {}

    for line in lines:
        if "[ERROR]" in line:
            if in_error_block and current_error:
                errors.append(current_error)

            message = line.replace("[ERROR]", "").strip()
            if message:
                current_error = {"message": message}
                in_error_block = True

                # Try to extract file location
                if ".java:" in message or ".xml:" in message:
                    parts = message.split(":")
                    if len(parts) >= 2:
                        current_error["file"] = parts[0]
                        try:
                            current_error["line"] = int(parts[1])
                        except ValueError:
                            pass
        elif in_error_block and line.strip() and not line.strip().startswith("["):
            # Continuation of error message
            if "context" not in current_error:
                current_error["context"] = []
            current_error["context"].append(line.strip())
        elif "[INFO]" in line or "[WARNING]" in line:
            if in_error_block and current_error:
                errors.append(current_error)
            in_error_block = False
            current_error = {}

    # Don't forget the last error
    if in_error_block and current_error:
        errors.append(current_error)

    return errors
