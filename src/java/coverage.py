# SPDX-License-Identifier: Apache-2.0
"""Line coverage of a Maven project with JaCoCo (no pom change needed).

`gaps --coverage` uses it to find what is really untested — a class can
have no `FooTest` and be fully covered by feature tests, or have one and
leave whole branches unexecuted.
"""

import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

JACOCO = "org.jacoco:jacoco-maven-plugin:0.8.13"
REPORT = Path("target") / "site" / "jacoco" / "jacoco.xml"


def jacoco_command(test_cmd: list[str]) -> list[str]:
    """The project's `mvn test …` command with JaCoCo around the test goal.

    Keeps the project's flags (profiles, -D properties); failing tests do not
    abort the run, coverage is what is measured here.
    """
    if "test" not in test_cmd:
        raise ValueError(f"not a Maven test command: {' '.join(test_cmd)}")
    i = test_cmd.index("test")
    return [*test_cmd[:i], f"{JACOCO}:prepare-agent", "test", f"{JACOCO}:report",
            "-Dmaven.test.failure.ignore=true", *test_cmd[i + 1:]]


def run_jacoco(project_path: str, test_cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
    return subprocess.run(jacoco_command(test_cmd), cwd=project_path, capture_output=True, text=True,
                          timeout=timeout)


def _ranges(lines: list[int]) -> str:
    """[3, 4, 5, 9] → '3-5, 9'."""
    out: list[str] = []
    for n in sorted(lines):
        if out and out[-1].split("-")[-1] == str(n - 1):
            out[-1] = f"{out[-1].split('-')[0]}-{n}"
        else:
            out.append(str(n))
    return ", ".join(out)


def read_reports(project_path: str) -> dict[str, dict[str, Any]]:
    """Coverage by source file (path relative to the project, as `find_source_files` gives it).

    {path: {"line_pct": float, "missed": int, "covered": int, "uncovered": "12-14, 40",
            "partial": "22"}} — `partial`: lines with missed branches.
    Reads every module's `target/site/jacoco/jacoco.xml`.
    """
    project = Path(project_path)
    result: dict[str, dict[str, Any]] = {}
    for report in sorted(project.glob(f"**/{REPORT.as_posix()}")):
        module = report.parents[3]                       # <module>/target/site/jacoco/jacoco.xml
        prefix = module.relative_to(project).as_posix()
        prefix = "" if prefix == "." else prefix + "/"
        root = ET.parse(report).getroot()
        for package in root.iter("package"):
            for source in package.iter("sourcefile"):
                rel = f"{prefix}src/main/java/{package.get('name')}/{source.get('name')}"
                missed = [int(ln.get("nr")) for ln in source.iter("line")
                          if int(ln.get("mi", 0)) > 0 and int(ln.get("ci", 0)) == 0]
                partial = [int(ln.get("nr")) for ln in source.iter("line")
                           if int(ln.get("mb", 0)) > 0 and int(ln.get("ci", 0)) > 0]
                counter = next((c for c in source.findall("counter") if c.get("type") == "LINE"), None)
                m = int(counter.get("missed")) if counter is not None else len(missed)
                c = int(counter.get("covered")) if counter is not None else 0
                result[rel] = {
                    "line_pct": round(100.0 * c / (m + c), 1) if m + c else 100.0,
                    "missed": m, "covered": c,
                    "uncovered": _ranges(missed), "partial": _ranges(partial),
                }
    return result
