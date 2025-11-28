"""
Analyze dependencies tool for Maven projects.

Analyzes Maven project dependencies for available updates, security vulnerabilities,
and compatibility issues.
"""

import asyncio
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


async def analyze_dependencies(
    project_path: str, include_snapshots: bool = False, check_vulnerabilities: bool = True
) -> str:
    """
    Analyze Maven project dependencies.

    Args:
        project_path: Path to the Maven project root directory
        include_snapshots: Include SNAPSHOT versions in analysis
        check_vulnerabilities: Check for known security vulnerabilities

    Returns:
        JSON string with analysis results
    """
    project_dir = Path(project_path)
    pom_file = project_dir / "pom.xml"

    if not pom_file.exists():
        return json.dumps({"success": False, "error": f"pom.xml not found at {project_path}"})

    results = {
        "success": True,
        "project_path": str(project_dir.absolute()),
        "current_dependencies": [],
        "available_updates": [],
        "vulnerabilities": [],
        "compatibility_issues": [],
    }

    # Parse current dependencies from pom.xml
    try:
        current_deps = await _parse_pom_dependencies(pom_file)
        results["current_dependencies"] = current_deps
    except Exception as e:
        results["parse_error"] = str(e)

    # Check for available updates using versions-maven-plugin
    try:
        updates = await _check_dependency_updates(project_dir, include_snapshots)
        results["available_updates"] = updates
    except Exception as e:
        results["update_check_error"] = str(e)

    # Check for vulnerabilities using dependency-check-maven
    if check_vulnerabilities:
        try:
            vulns = await _check_vulnerabilities(project_dir)
            results["vulnerabilities"] = vulns
        except Exception as e:
            results["vulnerability_check_error"] = str(e)

    # Check for compatibility issues
    try:
        issues = await _check_compatibility(project_dir)
        results["compatibility_issues"] = issues
    except Exception as e:
        results["compatibility_check_error"] = str(e)

    return json.dumps(results, indent=2)


async def _parse_pom_dependencies(pom_file: Path) -> list[dict[str, Any]]:
    """Parse dependencies from pom.xml file."""
    tree = ET.parse(pom_file)
    root = tree.getroot()

    # Handle Maven namespace
    ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

    dependencies = []

    # Find all dependency elements
    for dep in root.findall(".//maven:dependency", ns):
        group_id = dep.find("maven:groupId", ns)
        artifact_id = dep.find("maven:artifactId", ns)
        version = dep.find("maven:version", ns)
        scope = dep.find("maven:scope", ns)

        if group_id is not None and artifact_id is not None:
            dep_info = {
                "groupId": group_id.text,
                "artifactId": artifact_id.text,
                "version": version.text if version is not None else "managed",
                "scope": scope.text if scope is not None else "compile",
            }
            dependencies.append(dep_info)

    # Also check without namespace (some pom files don't use it)
    if not dependencies:
        for dep in root.findall(".//dependency"):
            group_id = dep.find("groupId")
            artifact_id = dep.find("artifactId")
            version = dep.find("version")
            scope = dep.find("scope")

            if group_id is not None and artifact_id is not None:
                dep_info = {
                    "groupId": group_id.text,
                    "artifactId": artifact_id.text,
                    "version": version.text if version is not None else "managed",
                    "scope": scope.text if scope is not None else "compile",
                }
                dependencies.append(dep_info)

    return dependencies


async def _check_dependency_updates(
    project_dir: Path, include_snapshots: bool
) -> list[dict[str, Any]]:
    """Check for available dependency updates."""
    cmd = [
        "mvn",
        "versions:display-dependency-updates",
        "-DprocessAllModules=true",
        "-DoutputEncoding=UTF-8",
        f"-DallowSnapshots={str(include_snapshots).lower()}",
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    stdout, stderr = await process.communicate()
    output = stdout.decode("utf-8", errors="replace")

    updates = []

    # Parse the output for update information
    lines = output.split("\n")
    for line in lines:
        if " -> " in line:
            # Extract dependency update info
            parts = line.strip().split()
            for i, part in enumerate(parts):
                if "->" in parts[i : i + 1] or (i > 0 and parts[i - 1 : i] == ["->"]):
                    continue
                if ":" in part and " -> " in line:
                    coords = part.split(":")
                    if len(coords) >= 2:
                        # Find version transition
                        arrow_idx = line.find(" -> ")
                        if arrow_idx > -1:
                            before = line[:arrow_idx].split()[-1]
                            after = line[arrow_idx + 4 :].split()[0]
                            updates.append(
                                {
                                    "groupId": coords[0] if len(coords) > 0 else "",
                                    "artifactId": coords[1] if len(coords) > 1 else "",
                                    "currentVersion": before,
                                    "availableVersion": after,
                                }
                            )
                    break

    return updates


async def _check_vulnerabilities(project_dir: Path) -> list[dict[str, Any]]:
    """Check for security vulnerabilities using OWASP dependency-check."""
    cmd = [
        "mvn",
        "org.owasp:dependency-check-maven:check",
        "-DfailBuildOnCVSS=11",  # Don't fail, just report
        "-Dformat=JSON",
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        await process.communicate()

        # Parse the generated report
        report_file = project_dir / "target" / "dependency-check-report.json"
        if report_file.exists():
            with open(report_file) as f:
                report = json.load(f)

            vulnerabilities = []
            for dep in report.get("dependencies", []):
                for vuln in dep.get("vulnerabilities", []):
                    vulnerabilities.append(
                        {
                            "dependency": dep.get("fileName", ""),
                            "cve": vuln.get("name", ""),
                            "severity": vuln.get("severity", ""),
                            "description": vuln.get("description", "")[:200],
                        }
                    )

            return vulnerabilities
    except Exception:
        pass

    return []


async def _check_compatibility(project_dir: Path) -> list[dict[str, Any]]:
    """Check for dependency compatibility issues."""
    cmd = ["mvn", "dependency:analyze", "-DignoreNonCompile=true"]

    process = await asyncio.create_subprocess_exec(
        *cmd, cwd=project_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )

    stdout, stderr = await process.communicate()
    output = stdout.decode("utf-8", errors="replace")

    issues = []

    # Parse for unused and undeclared dependencies
    in_unused = False
    in_undeclared = False

    for line in output.split("\n"):
        if "Unused declared dependencies" in line:
            in_unused = True
            in_undeclared = False
        elif "Used undeclared dependencies" in line:
            in_undeclared = True
            in_unused = False
        elif line.strip().startswith("[INFO]") and ":" in line:
            dep_part = line.split("[INFO]")[-1].strip()
            if in_unused:
                issues.append(
                    {"type": "unused", "dependency": dep_part, "message": "Declared but not used"}
                )
            elif in_undeclared:
                issues.append(
                    {
                        "type": "undeclared",
                        "dependency": dep_part,
                        "message": "Used but not declared",
                    }
                )
        elif not line.strip() or "[WARNING]" in line or "[ERROR]" in line:
            in_unused = False
            in_undeclared = False

    return issues
