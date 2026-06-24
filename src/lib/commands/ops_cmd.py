# SPDX-License-Identifier: Apache-2.0
"""testboost status/verify/gitlab/cleanup/doctor — auxiliaries and operations."""

import argparse
import asyncio
import sys


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify an integrity token.

    Exits 0 and prints VERIFIED if the token is valid.
    Exits 1 and prints FAILED if the token is invalid or malformed.
    """
    from src.lib.integrity import verify_token

    project_path = args.project_path
    token_line = args.token.strip()

    if verify_token(project_path, token_line):
        print("[TESTBOOST_VERIFY:OK]")
        return 0
    else:
        print("[TESTBOOST_VERIFY:FAILED]")
        return 1
def cmd_gitlab(args: argparse.Namespace) -> int:
    """GitLab MR helpers for CI jobs (post-question / fetch-answer).

    These used to be shell scripts under scripts/gitlab/; as subcommands
    they ship with `pip install testboost`, which is all a consumer repo
    gets from `include:`-ing the CI template.
    """
    import httpx

    from src.lib.gitlab_mr import (
        GitLabConfigError,
        NoAnswerFoundError,
        fetch_answer,
        post_question,
    )

    sub = getattr(args, "gitlab_command", None)
    try:
        if sub == "post-question":
            result = post_question(args.project_path)
            print(
                f"Posted question {result['question_id']} "
                f"(note {result.get('note_id')})"
            )
            return 0
        if sub == "fetch-answer":
            out = fetch_answer(args.project_path, output=args.output)
            print(f"Signed answer written to {out}")
            return 0
        print(f"Error: unknown gitlab subcommand: {sub}", file=sys.stderr)
        return 1
    except GitLabConfigError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except NoAnswerFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except httpx.HTTPError as e:
        print(f"Error: GitLab API call failed: {e}", file=sys.stderr)
        return 1
def cmd_cleanup(args: argparse.Namespace) -> int:
    """Mark abandoned (awaiting_input + age > TTL) sessions.

    With --dry-run: list candidates and exit 0 without touching them.
    Otherwise: flip their spec.md status to 'abandoned' (audit-preserving).
    """
    from src.lib.session_tracker import find_abandoned_sessions, mark_abandoned

    project_path = args.project_path
    ttl_hours = getattr(args, "ttl_hours", 24)
    dry_run = bool(getattr(args, "dry_run", False))

    candidates = find_abandoned_sessions(project_path, ttl_hours=ttl_hours)
    if not candidates:
        print(f"No abandoned sessions found (TTL {ttl_hours}h).")
        return 0

    print(f"{'Would mark' if dry_run else 'Marking'} {len(candidates)} session(s) as abandoned:")
    for s in candidates:
        print(f"  - {s['session_id']:30}  age={s['age_hours']:.1f}h  step={s['step']}")
        if not dry_run:
            mark_abandoned(s["session_dir"])
    return 0
def cmd_doctor(args: argparse.Namespace) -> int:
    """Health-check: LLM, .tb_secret, write perms, Maven.

    Exit 0 if all green; 1 if any issue. Prints a per-check status line.
    """
    import os as _os
    import shutil as _sh

    from src.lib.integrity import SECRET_FILE
    from src.lib.session_tracker import get_testboost_dir

    project_path = args.project_path
    issues: list[str] = []
    checks: list[tuple[str, bool, str]] = []

    # 1. .testboost dir + .tb_secret
    tb_dir = get_testboost_dir(project_path)
    secret_path = tb_dir / SECRET_FILE
    secret_ok = secret_path.exists() and secret_path.read_text().strip() != ""
    checks.append((
        "tb_secret",
        secret_ok,
        f"{secret_path} {'present' if secret_ok else 'missing or empty'}",
    ))
    if not secret_ok:
        issues.append("tb_secret missing — run any TestBoost command on this project to create it")

    # 2. Write permissions on the project dir
    writable = _os.access(project_path, _os.W_OK)
    checks.append(("write_perms", writable, f"{project_path} {'writable' if writable else 'not writable'}"))
    if not writable:
        issues.append("project directory is not writable")

    # 3. Maven available
    mvn = _sh.which("mvn") or _sh.which("mvn.cmd")
    checks.append(("maven", mvn is not None, f"mvn {'found at ' + mvn if mvn else 'not on PATH'}"))
    if mvn is None:
        issues.append("Maven not on PATH (only blocks Java projects)")

    # 4. LLM reachable (best effort, async)
    llm_ok = True
    llm_msg = "LLM ping OK"
    try:
        from src.lib.startup_checks import check_llm_connection
        asyncio.run(check_llm_connection())
    except Exception as e:
        llm_ok = False
        llm_msg = f"LLM ping failed: {e}"
        issues.append(f"LLM unreachable: {e}")
    checks.append(("llm", llm_ok, llm_msg))

    # Render
    print("TestBoost doctor:")
    for name, ok, msg in checks:
        marker = "OK " if ok else "KO"
        print(f"  [{marker}] {name:14}  {msg}")
    if issues:
        print(f"\n{len(issues)} issue(s) detected.")
        return 1
    print("\nAll checks passed.")
    return 0
def cmd_status(args: argparse.Namespace) -> int:
    """Show current session status."""
    from pathlib import Path as _Path

    from src.lib.session_tracker import (
        get_current_session,
        get_session_status,
        get_session_technology,
    )

    status = get_session_status(args.project_path)

    # Prepend technology info to the status output
    session = get_current_session(args.project_path)
    if session:
        technology = get_session_technology(_Path(session["session_dir"]))
        print(f"**Technology**: {technology}")
        print()

    print(status)
    return 0
