# SPDX-License-Identifier: Apache-2.0
"""`testboost check`: judge the tests, whoever wrote them.

Measured, not declared: JaCoCo line coverage and PIT mutation score, on the
whole project or — with `--base <ref>` — on the lines changed since that ref.
No session, no LLM. Exit 0 when both thresholds are met, 1 when one is not,
2 when the measure itself failed (build error, no report, PIT not set up).

Writes `.testboost/check/report.md` (ready to post as an MR comment) and
`.testboost/check/check.json` (the data, read by `equivalent`).
"""

import argparse
import asyncio
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

CHECK_DIR = Path(".testboost") / "check"
REPORT_MARKER = "<!-- testboost:check -->"
EXIT_PASS, EXIT_BELOW, EXIT_ERROR = 0, 1, 2
DETECTED = ("KILLED", "TIMED_OUT")          # PIT's convention


def cmd_check(args: argparse.Namespace) -> int:
    return asyncio.run(_cmd_check_async(args))


def _error(message: str) -> int:
    print(f"Error: {message}", file=sys.stderr)
    return EXIT_ERROR


# --------------------------------------------------------------------------- coverage

_TOTALS = re.compile(r"^\[\w+\] Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: \d+\s*$", re.MULTILINE)


def failing_tests(maven_output: str) -> int:
    """Failures + errors from Surefire's module totals (JaCoCo ran with failure.ignore)."""
    return sum(int(f) + int(e) for _run, f, e in _TOTALS.findall(maven_output))


def coverage_summary(coverage: dict[str, dict], scope: dict[str, set[int]] | None) -> dict[str, Any]:
    """Line coverage of the whole report, or of the changed executable lines only.

    A partially covered line (missed branch) counts as covered — as in JaCoCo's
    line counter; it is listed so that a reviewer sees it.
    """
    files: dict[str, dict[str, Any]] = {}
    hit = total = 0
    for path, info in coverage.items():
        lines = info.get("lines", {})
        if scope is not None:
            if path not in scope:
                continue
            lines = {n: s for n, s in lines.items() if n in scope[path]}
        if not lines:
            continue
        covered = sum(1 for s in lines.values() if s != "missed")
        hit, total = hit + covered, total + len(lines)
        files[path] = {"covered": covered, "lines": len(lines),
                       "uncovered": sorted(n for n, s in lines.items() if s == "missed"),
                       "partial": sorted(n for n, s in lines.items() if s == "partial")}
    # A changed file absent from the report has no executable line (interface,
    # constants…): JaCoCo reports every compiled class, tested or not.
    pct = round(100.0 * hit / total, 1) if total else None
    return {"pct": pct, "covered": hit, "lines": total, "files": files}


# --------------------------------------------------------------------------- mutation

def mutation_summary(project_path: str, mutants: list[dict], scope: dict[str, set[int]] | None) -> dict:
    """Score of the mutants in scope, declared equivalents excluded (effective score)."""
    from src.java.diff import source_key
    from src.lib import equivalents

    if scope is not None:
        lines = {source_key(p): ls for p, ls in scope.items()}
        mutants = [m for m in mutants if m.get("line") in lines.get(m.get("source_file", ""), ())]
    undetected = [m for m in mutants if m["status"] not in DETECTED]
    real, equivalent = equivalents.split(project_path, undetected)
    total = len(mutants) - len(equivalent)
    detected = len(mutants) - len(undetected)
    return {
        "score": round(100.0 * detected / total, 1) if total else None,
        "total": len(mutants), "detected": detected, "equivalent": len(equivalent),
        "survivors": sorted(real, key=lambda m: (m.get("source_file", ""), m["line"])),
    }


# --------------------------------------------------------------------------- report

def _fmt(pct: float | None) -> str:
    return "n/a" if pct is None else f"{pct}%"


def _verdict(value: float | None, threshold: float) -> tuple[bool, str]:
    if value is None:
        return True, "— nothing to measure"
    return value >= threshold, ("✅" if value >= threshold else "❌") + f" (min {threshold}%)"


def render_report(data: dict[str, Any]) -> str:
    cov, mut = data["coverage"], data.get("mutation")
    parts = []
    if data.get("classes"):
        parts.append("classes " + ", ".join(f"`{c}`" for c in data["classes"]))
    if data.get("base"):
        parts.append(f"lines changed since `{data['base']}`")
    scope = "; ".join(parts) or "whole project"
    md = [f"## TestBoost check — {'PASSED' if data['passed'] else 'FAILED'}", "",
          f"Scope: {scope}. Measured by {'JaCoCo and PIT' if mut is not None else 'JaCoCo'}, not declared.", "",
          "| Measure | Value | Verdict |", "|---|---|---|",
          f"| Line coverage | {_fmt(cov['pct'])} ({cov['covered']}/{cov['lines']} lines) "
          f"| {_verdict(cov['pct'], data['min_coverage'])[1]} |"]
    if mut is not None:
        eq = f", {mut['equivalent']} declared equivalent" if mut["equivalent"] else ""
        md.append(f"| Mutation score | {_fmt(mut['score'])} ({mut['detected']}/{mut['total'] - mut['equivalent']} "
                  f"mutants detected{eq}) | {_verdict(mut['score'], data['min_mutation'])[1]} |")
    md.append("")

    uncovered = {p: f for p, f in cov["files"].items() if f["uncovered"]}
    if uncovered:
        md += ["### Uncovered lines", "", "| File | Lines |", "|---|---|"]
        for path, f in sorted(uncovered.items()):
            md.append(f"| `{path}` | {_ranges(f['uncovered'])} |")
        md.append("")

    if mut and mut["survivors"]:
        survived = [m for m in mut["survivors"] if m["status"] != "NO_COVERAGE"]
        not_run = len(mut["survivors"]) - len(survived)
        if survived:
            grouped: dict[str, list[dict]] = {}
            for m in survived:                     # identical mutants of one line share an id
                grouped.setdefault(m["id"], []).append(m)
            shown = list(grouped.values())[:30]
            md += ["### Surviving mutants", "",
                   "Each one is a change to the code that the tests ran but did not notice. Kill it with "
                   "a test, or — if no test can observe it — declare it equivalent (it then leaves the "
                   "score):", "",
                   "| Id | Location | Mutation |", "|---|---|---|"]
            for group in shown:
                m, n = group[0], len(group)
                md.append(f"| `{m['id']}` | `{m.get('source_file') or m['class']}:{m['line']}` "
                          f"({m['method']}) | {m['description']}{f' (×{n})' if n > 1 else ''} |")
            if len(grouped) > len(shown):
                md.append(f"| … | {len(grouped) - len(shown)} more in `.testboost/check/check.json` | |")
            md += ["", "```bash", f"testboost equivalent . {shown[0][0]['id']} --reason \"why no test can observe it\"",
                   "```", ""]
        if not_run:
            md += [f"{not_run} more mutant(s) are on lines no test runs (see *Uncovered lines*): "
                   "cover those lines first.", ""]
    md.append(REPORT_MARKER)
    return "\n".join(md) + "\n"


def _ranges(lines: list[int]) -> str:
    from src.java.coverage import _ranges as ranges
    return ranges(lines)


# --------------------------------------------------------------------------- command

async def _cmd_check_async(args: argparse.Namespace) -> int:
    from src.java.coverage import read_reports, run_jacoco
    from src.java.diff import changed_lines, class_name
    from src.java.pit import setup_problem
    from src.lib import equivalents
    from src.lib.bridge import get_plugin_for_session, run_mutation_testing
    from src.lib.commands.analyze_cmd import maven_session_config
    from src.lib.session_tracker import get_current_session, load_project_config

    project_path = str(Path(args.project_path).resolve())
    if not (Path(project_path) / "pom.xml").exists():
        return _error("`check` measures Java/Maven projects (no pom.xml found).")
    with_mutation = not getattr(args, "no_mutation", False)
    if with_mutation and (problem := setup_problem(project_path)):
        return _error(problem)

    base = getattr(args, "base", None)
    scope = None
    if base:
        try:
            scope = changed_lines(project_path, base)
        except (ValueError, FileNotFoundError, subprocess.TimeoutExpired) as e:
            return _error(str(e))
        if not scope:
            print(f"No main Java source changed since {base}: nothing to check.")
            return EXIT_PASS
    classes = getattr(args, "classes", None)
    if classes:
        try:
            by_class = class_scope(project_path, classes)
        except ValueError as e:
            return _error(str(e))
        scope = by_class if scope is None else {p: ls for p, ls in scope.items() if p in by_class}
        if not scope:
            print("None of the given classes changed: nothing to check.")
            return EXIT_PASS

    session = get_current_session(project_path)
    config = maven_session_config(project_path, session["session_dir"] if session else None)
    plugin = get_plugin_for_session(project_path)
    timeout = load_project_config(project_path)["test_timeout_seconds"]
    test_cmd = plugin.test_run_command(Path(project_path), config)
    target_tests = getattr(args, "target_tests", None)
    if target_tests:                 # coverage of the same tests PIT runs: what THEY exercise
        test_cmd = [*test_cmd, f"-Dtest={','.join(target_tests)}", "-Dsurefire.failIfNoSpecifiedTests=false"]

    print("Measuring line coverage with JaCoCo (runs the test suite)...", file=sys.stderr)
    try:
        run = run_jacoco(project_path, test_cmd, timeout)
    except (ValueError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        return _error(f"JaCoCo run failed: {e}")
    output = run.stdout + run.stderr
    if failures := failing_tests(output):
        lines = [ln for ln in output.splitlines() if ln.startswith("[ERROR]")][:20]
        return _error(f"{failures} test(s) fail without any mutation: fix them first — coverage and "
                      "mutation score are only meaningful on a green suite.\n" + "\n".join(lines))
    coverage = read_reports(project_path)
    if not coverage:
        tail = "\n".join((run.stdout + run.stderr).splitlines()[-30:])
        return _error(f"no JaCoCo report produced (build failure?). Maven output:\n{tail}")
    data: dict[str, Any] = {
        "base": base, "classes": classes, "min_coverage": args.min_coverage, "min_mutation": args.min_mutation,
        "coverage": coverage_summary(coverage, scope),
    }

    if with_mutation:
        targets = sorted({c for p in scope for c in (class_name(p), class_name(p) + "$*")}) if scope else None
        print(f"Running PIT on {'the selected classes' if scope else 'the project'}...", file=sys.stderr)
        pit = json.loads(await run_mutation_testing(
            project_path, target_classes=targets, target_tests=target_tests))
        if not pit.get("success") or pit.get("error"):
            return _error(f"PIT failed: {pit.get('error', '')[-3000:]}")
        mutation = mutation_summary(project_path, pit.get("mutants", []), scope)
        mutation["survivors"] = equivalents.with_ids(mutation["survivors"])
        data["mutation"] = mutation

    cov_ok = _verdict(data["coverage"]["pct"], args.min_coverage)[0]
    mut_ok = _verdict(data["mutation"]["score"], args.min_mutation)[0] if with_mutation else True
    data["passed"] = cov_ok and mut_ok

    out_dir = Path(project_path) / CHECK_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    report = render_report(data)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "check.json").write_text(json.dumps(data, indent=2, default=sorted), encoding="utf-8")
    print(report)
    print(f"Report: {out_dir / 'report.md'}", file=sys.stderr)
    return EXIT_PASS if data["passed"] else EXIT_BELOW


def class_scope(project_path: str, classes: list[str]) -> dict[str, set[int]]:
    """`--classes a.b.C …` → every line of their source files (any module)."""
    from src.java.diff import MAIN_JAVA

    project = Path(project_path)
    scope: dict[str, set[int]] = {}
    for fqcn in classes:
        rel = fqcn.split("$")[0].replace(".", "/") + ".java"
        found = [p for p in project.glob(f"**/{MAIN_JAVA}{rel}") if "target" not in p.parts]
        if not found:
            raise ValueError(f"no source file for class {fqcn} (looked for */{MAIN_JAVA}{rel})")
        for path in found:
            n = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
            scope[path.relative_to(project).as_posix()] = set(range(1, n + 1))
    return scope


def last_check_survivors(project_path: str) -> list[dict]:
    """Survivors of the last `check` run (so `equivalent` can declare them)."""
    path = Path(project_path) / CHECK_DIR / "check.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return (data.get("mutation") or {}).get("survivors", [])
