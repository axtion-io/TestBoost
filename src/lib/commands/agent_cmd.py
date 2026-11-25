# SPDX-License-Identifier: Apache-2.0
"""Agent mode: the host agent (Claude Code, OpenCode…) writes the tests.

Inside an LLM CLI, TestBoost calling its own LLM duplicates the agent and
needs a second API key. In agent mode TestBoost keeps the deterministic
steps and hands the generation to the agent:

    testboost context <project>            # one prompt file per gap + expected test path
    (the agent writes each test at its expected path)
    testboost generate <project> --agent   # registers + compiles them, no LLM call
    testboost validate / mutate            # unchanged
    testboost context <project> --killer   # one prompt per class with surviving mutants
    testboost killer <project> --agent     # registers + compiles the killer tests

No command in this module ever calls an LLM.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from src.lib.commands._shared import (
    _extract_json_field,
    _read_step_status,
    _warn_maven_config_issue,
    filter_target_files,
)
from src.lib.prompt_utils import count_tests

AGENT_DIR = "agent"

def _session_or_exit(project_path: str):
    from src.lib.session_tracker import get_current_session

    session = get_current_session(project_path)
    if not session:
        print("Error: No active session. Run `init` first.", file=sys.stderr)
    return session


def killer_brief(class_name: str, source: str, test_path: str, mutants: list[dict]) -> str:
    """Short brief for the surviving mutants of one class (agent mode): the agent reads the source."""
    rows = "\n".join(f"| `{m['id']}` | `{m['method']}` | {m['line']} | {m['description']} |" for m in mutants)
    return (
        f"# Killer tests to write: `{test_path}`\n\n"
        f"- **Class under test**: `{source}` — read it (`{class_name}`)\n"
        f"- **Surviving mutants** (the current tests pass on each mutated version):\n\n"
        "| Id | Method | Line | Mutation |\n|---|---|---|---|\n" + rows + "\n\n"
        "## Rules\n\n"
        "- One focused test per mutant: it must FAIL on the mutated code and PASS on the original. "
        "Derive the exact expected value from the source (or an independent tool), never guess.\n"
        "- **Equivalent mutant** (no input the class can receive makes it behave differently): write no "
        "test; declare it: `testboost equivalent <project> <id> --reason \"why no test can observe it\"`. "
        "If every mutant here is equivalent, write no file.\n"
        f"- Write only `{test_path}`, then run `testboost killer <project> --agent`.\n"
    )


def _compile_errors(project_path: str, plugin, maven_compile_cmd: str | None,
                    test_paths: list[str], session_dir: str, logger) -> dict[str, str]:
    """Compile the written tests once; return {test_path: errors} for those that fail.

    Java/Maven compiles the whole project in one `test-compile` and errors are
    attributed by file name; technologies with a `{test_file}` placeholder are
    checked file by file. A compile check that cannot run (no Maven) reports
    nothing — `validate` will.
    """
    session_config = {"maven_compile_cmd": maven_compile_cmd} if maven_compile_cmd else {}
    try:
        template = plugin.validation_command(Path(project_path), session_config)
    except ValueError as e:  # analysis.md is user-editable: non-Maven binaries are refused
        logger.warn(f"Invalid maven_compile_cmd, using default: {e}")
        template = plugin.validation_command(Path(project_path), {})

    def run(cmd: list[str]) -> subprocess.CompletedProcess | None:
        try:
            return subprocess.run(cmd, cwd=project_path, capture_output=True, text=True, timeout=300)
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warn(f"Compile check skipped: {e}")
            return None

    errors: dict[str, str] = {}
    if any("{test_file}" in part for part in template):
        for tp in test_paths:
            result = run([part.replace("{test_file}", tp) for part in template])
            if result is not None and result.returncode != 0:
                errors[tp] = (result.stdout + result.stderr)[-3000:]
        return errors

    result = run(template)
    if result is None or result.returncode == 0:
        return errors
    output = result.stdout + result.stderr
    for tp in test_paths:
        name = Path(tp).name
        lines = [ln for ln in output.splitlines() if name in ln]
        if lines:
            errors[tp] = "\n".join(lines[:40])
    if not errors:
        _warn_maven_config_issue(output, session_dir, project_path, logger)
        errors["<build>"] = "\n".join(output.splitlines()[-30:])
    return errors


def _maven_compile_cmd(project_path: str, session_dir: str) -> str | None:
    from src.lib.session_tracker import read_project_analysis_data

    cmd = (read_project_analysis_data(project_path) or {}).get("maven_compile_cmd")
    analysis = Path(session_dir) / "analysis.md"
    if analysis.exists():
        cmd = _extract_json_field(analysis.read_text(encoding="utf-8"), "maven_compile_cmd") or cmd
    return cmd


# ---------------------------------------------------------------------------
# context
# ---------------------------------------------------------------------------

def cmd_context(args: argparse.Namespace) -> int:
    """Write one prompt per class to cover (or per class with surviving mutants)."""
    if getattr(args, "killer", False):
        return _context_killer(args)
    return _context_generation(args)


def _context_generation(args: argparse.Namespace) -> int:
    from src.lib.bridge import get_plugin_for_session
    from src.lib.md_logger import MdLogger
    from src.lib.session_tracker import read_project_analysis_data
    from src.test_generation.generate_unit import build_agent_brief, build_generation_context

    project_path = args.project_path
    session = _session_or_exit(project_path)
    if not session:
        return 1
    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "agent-context", verbose=getattr(args, "verbose", False))

    gaps_file = Path(session_dir) / "coverage-gaps.md"
    if not gaps_file.exists():
        logger.error("Coverage gaps step not completed. Run `gaps` first.")
        return 1
    gaps_md = gaps_file.read_text(encoding="utf-8")
    gaps = _extract_json_field(gaps_md, "gaps") or []
    coverage = _extract_json_field(gaps_md, "coverage") or {}     # gaps --coverage (JaCoCo)
    targets = filter_target_files(gaps, getattr(args, "files", None), logger)

    data = read_project_analysis_data(project_path) or {}
    conventions = data.get("conventions")
    analysis = Path(session_dir) / "analysis.md"
    if analysis.exists():
        conventions = _extract_json_field(analysis.read_text(encoding="utf-8"), "conventions") or conventions

    plugin = get_plugin_for_session(project_path)
    agent_dir = Path(session_dir) / AGENT_DIR
    manifest: list[dict[str, Any]] = []
    for source_file in targets:
        context, source_or_error = build_generation_context(
            project_path, source_file, conventions=conventions,
            class_index=data.get("class_index"), test_examples=data.get("test_examples"),
        )
        if context is None:
            logger.warn(f"Skipped {source_file}: {source_or_error}")
            continue
        test_path = plugin.test_file_name(source_file)
        brief = build_agent_brief(context, source_file, test_path, technology=plugin.identifier,
                                  coverage=coverage.get(source_file))
        name = context["class_name"] or Path(source_file).stem
        prompt_file = agent_dir / f"{name}.md"
        agent_dir.mkdir(parents=True, exist_ok=True)
        prompt_file.write_text(brief, encoding="utf-8")
        manifest.append({"source_file": source_file, "class_name": name,
                         "test_path": test_path, "prompt_file": str(prompt_file)})

    (agent_dir).mkdir(parents=True, exist_ok=True)
    (agent_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Agent mode: {len(manifest)} test(s) to write. For each one, read its brief and the class, "
          "write the test at the given path, then run `testboost generate <project> --agent`.\n")
    print("| # | Source file | Test to write | Brief |")
    print("|---|---|---|---|")
    for i, m in enumerate(manifest, 1):
        print(f"| {i} | `{m['source_file']}` | `{m['test_path']}` | `{m['prompt_file']}` |")
    return 0


def _context_killer(args: argparse.Namespace) -> int:
    from src.lib.md_logger import MdLogger
    from src.test_generation.killer_tests import (
        _JAVA_CLASS_NAME,
        _find_source_file,
        _get_killer_test_path,
    )

    project_path = args.project_path
    session = _session_or_exit(project_path)
    if not session:
        return 1
    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "agent-context", verbose=getattr(args, "verbose", False))

    mutation_file = Path(session_dir) / "mutation.md"
    if not mutation_file.exists() or _read_step_status(mutation_file) != "completed":
        logger.error("Mutation testing step not completed. Run `mutate` first.")
        return 1
    survivors = _extract_json_field(mutation_file.read_text(encoding="utf-8"), "surviving_mutants") or []
    from src.lib import equivalents
    survivors, _declared = equivalents.split(project_path, survivors)

    project_dir = Path(project_path)
    by_class: dict[str, list[dict]] = {}
    for mutant in survivors[: getattr(args, "max_tests", 10)]:
        by_class.setdefault(mutant.get("class", ""), []).append(mutant)

    agent_dir = Path(session_dir) / AGENT_DIR / "killer"
    manifest: list[dict[str, Any]] = []
    for class_name, mutants in by_class.items():
        if not _JAVA_CLASS_NAME.match(class_name):
            logger.warn(f"Skipped invalid class name: {class_name!r}")
            continue
        source = _find_source_file(project_dir, class_name)
        if source is None:
            logger.warn(f"Skipped {class_name}: source file not found")
            continue
        test_path = str(_get_killer_test_path(project_dir, class_name, source).relative_to(project_dir))
        agent_dir.mkdir(parents=True, exist_ok=True)
        prompt_file = agent_dir / f"{class_name.rsplit('.', 1)[-1]}.md"
        prompt_file.write_text(killer_brief(class_name, source.relative_to(project_dir).as_posix(),
                                            test_path, mutants), encoding="utf-8")
        manifest.append({"class": class_name, "test_path": test_path, "mutants_targeted": len(mutants),
                         "mutant_ids": [m["id"] for m in mutants], "prompt_file": str(prompt_file)})

    agent_dir.mkdir(parents=True, exist_ok=True)
    (agent_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Agent mode: {len(manifest)} killer test class(es) to write, then run "
          "`testboost killer <project> --agent`.\n")
    print("| # | Class | Mutants | Test to write | Brief |")
    print("|---|---|---|---|---|")
    for i, m in enumerate(manifest, 1):
        print(f"| {i} | `{m['class']}` | {m['mutants_targeted']} | `{m['test_path']}` | `{m['prompt_file']}` |")
    return 0


# ---------------------------------------------------------------------------
# generate --agent / killer --agent
# ---------------------------------------------------------------------------

def _load_manifest(session_dir: str, *parts: str) -> list[dict] | None:
    path = Path(session_dir, AGENT_DIR, *parts, "manifest.json")
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _register(project_path: str, session_dir: str, logger, entries: list[dict],
              label: str) -> tuple[list[dict], list[dict], dict[str, str]]:
    """Split manifest entries into written/missing and compile the written ones."""
    from src.lib.bridge import get_plugin_for_session
    from src.lib.commands.generate_cmd import _safe_test_target

    written, missing = [], []
    for entry in entries:
        full = _safe_test_target(project_path, entry["test_path"], entry.get("source_file"))
        (written if full.exists() else missing).append(entry)
    errors: dict[str, str] = {}
    if written:
        logger.info(f"Compiling {len(written)} {label} written by the agent...")
        errors = _compile_errors(project_path, get_plugin_for_session(project_path),
                                 _maven_compile_cmd(project_path, session_dir),
                                 [e["test_path"] for e in written], session_dir, logger)
    return written, missing, errors


def _report(written: list[dict], missing: list[dict], errors: dict[str, str],
            project_path: str, title: str) -> str:
    content = f"# {title}\n\n**Mode**: agent (tests written by the host agent, no TestBoost LLM call)\n\n"
    content += "| # | Test file | Status | Test count |\n|---|---|---|---|\n"
    for i, e in enumerate(written + missing, 1):
        tp = e["test_path"]
        if e in missing:
            status, count = "missing — write it", "-"
        else:
            code = (Path(project_path) / tp).read_text(encoding="utf-8", errors="replace")
            status = "compile errors" if tp in errors else "compiles"
            count = str(count_tests(code))
        content += f"| {i} | `{tp}` | {status} | {count} |\n"
    for tp, err in errors.items():
        content += f"\n### Compilation errors: `{tp}`\n\n```\n{err}\n```\n"
    if missing or errors:
        content += ("\n**Next**: write the missing tests / fix the compilation errors, then run the "
                    "same `--agent` command again.\n")
    return content


def cmd_generate_agent(args: argparse.Namespace) -> int:
    from src.lib.integrity import emit_token
    from src.lib.md_logger import MdLogger
    from src.lib.session_tracker import (
        STATUS_COMPLETED,
        STATUS_FAILED,
        clear_generation_cursor,
        update_step_file,
    )

    project_path = args.project_path
    session = _session_or_exit(project_path)
    if not session:
        return 1
    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "generation", verbose=getattr(args, "verbose", False))

    manifest = _load_manifest(session_dir)
    if manifest is None:
        logger.error("No agent context found. Run `context` first, write the tests, then `generate --agent`.")
        return 1
    files = getattr(args, "files", None)
    if files:
        manifest = [e for e in manifest
                    if e["source_file"] in filter_target_files([m["source_file"] for m in manifest], files, logger)]

    written, missing, errors = _register(project_path, session_dir, logger, manifest, "test file(s)")
    content = _report(written, missing, errors, project_path, "Test Generation Results")
    ok = [e for e in written if e["test_path"] not in errors]
    generated = []
    for e in ok:
        code = (Path(project_path) / e["test_path"]).read_text(encoding="utf-8", errors="replace")
        generated.append({"path": e["test_path"], "class_name": e["class_name"],
                          "source_file": e["source_file"],
                          "test_count": count_tests(code)})
    done = not missing and not errors and bool(generated)
    update_step_file(session_dir, "generation", STATUS_COMPLETED if done else STATUS_FAILED, content,
                     data={"mode": "agent", "generated": generated,
                           "missing": [e["test_path"] for e in missing],
                           "compile_errors": sorted(errors)})
    logger.result("Test Generation (agent mode)", content)
    if not done:
        return 1
    clear_generation_cursor(session_dir)
    emit_token(project_path, "generation", session["session_id"])
    return 0


def cmd_killer_agent(args: argparse.Namespace) -> int:
    from src.lib.integrity import emit_token
    from src.lib.md_logger import MdLogger
    from src.lib.session_tracker import STATUS_COMPLETED, STATUS_FAILED, update_step_file

    project_path = args.project_path
    session = _session_or_exit(project_path)
    if not session:
        return 1
    session_dir = session["session_dir"]
    logger = MdLogger(session_dir, "killer-tests", verbose=getattr(args, "verbose", False))

    manifest = _load_manifest(session_dir, "killer")
    if manifest is None:
        logger.error("No killer context found. Run `context --killer` first, write the tests, "
                     "then `killer --agent`.")
        return 1

    from src.lib import equivalents
    declared = equivalents.load(project_path)
    remaining = []
    for entry in manifest:
        targets = [i for i in entry.get("mutant_ids", []) if i not in declared]
        if entry.get("mutant_ids") and not targets:
            logger.info(f"{entry['class']}: every mutant declared equivalent — no killer test needed")
            continue
        remaining.append({**entry, "mutants_targeted": len(targets) if entry.get("mutant_ids") else
                          entry["mutants_targeted"]})
    manifest = remaining
    if not manifest:
        logger.info("Every targeted mutant was declared equivalent: nothing to register.")

    written, missing, errors = _register(project_path, session_dir, logger, manifest, "killer test(s)")
    content = _report(written, missing, errors, project_path, "Killer Test Generation Results")
    ok = [e for e in written if e["test_path"] not in errors]
    done = not missing and not errors
    update_step_file(session_dir, "killer-tests", STATUS_COMPLETED if done else STATUS_FAILED, content,
                     data={"mode": "agent",
                           "generated_tests": [{"class": e["class"], "test_file": e["test_path"],
                                                "mutants_targeted": e["mutants_targeted"]} for e in ok],
                           "total_mutants_targeted": sum(e["mutants_targeted"] for e in manifest)})
    logger.result("Killer Tests (agent mode)", content)
    if not done:
        return 1
    emit_token(project_path, "killer-tests", session["session_id"])
    return 0
