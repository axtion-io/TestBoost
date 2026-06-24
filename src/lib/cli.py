#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""TestBoost CLI - Lightweight entry point.

This is the single CLI entry point, designed to be called from shell
scripts, which are in turn invoked by LLM CLI slash commands.

Usage:
    python -m testboost <command> <project_path> [options]
    python -m src.lib.cli <command> <project_path> [options]

This module is the stable facade: it owns the argument parser and
re-exports every command implementation from `src.lib.commands.*` so
existing imports and test patches (`src.lib.cli.cmd_generate`, â€¦) keep
working. The implementations live one module per command group.
"""

import argparse
import json
import sys
from pathlib import Path

# Add the TestBoost root to path so we can import existing modules
TESTBOOST_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(TESTBOOST_ROOT))

# Load .env into os.environ BEFORE any LLM/httpx imports so that NO_PROXY,
# SSL_CERT_FILE, REQUESTS_CA_BUNDLE etc. are visible to httpx at client creation.
try:
    from dotenv import load_dotenv
    load_dotenv(TESTBOOST_ROOT / ".env", override=False)
except ImportError:
    pass

# Re-export the command implementations and the helpers that tests and
# other modules historically imported from this facade.
from src.lib.commands._shared import (  # noqa: E402,F401
    _extract_json_field,
    _read_step_status,
    _warn_maven_config_issue,
)
from src.lib.commands.analyze_cmd import (  # noqa: E402,F401
    _cmd_analyze_async,
    _cmd_gaps_async,
    cmd_analyze,
    cmd_gaps,
)
from src.lib.commands.generate_cmd import (  # noqa: E402,F401
    _MAX_COMPILE_FIX_ATTEMPTS,
    _attempt_compile_fix,
    _attempt_test_runtime_fix,
    _cmd_generate_async,
    _compile_fix_item,
    _merge_answer_schemas,
    cmd_generate,
)
from src.lib.commands.hitl_cmd import cmd_resume, cmd_sign_answer  # noqa: E402,F401
from src.lib.commands.init_cmd import cmd_init  # noqa: E402,F401
from src.lib.commands.install_cmd import _prompt_shell_type, cmd_install  # noqa: E402,F401
from src.lib.commands.mutation_cmd import (  # noqa: E402,F401
    _cmd_killer_async,
    _cmd_mutate_async,
    cmd_killer,
    cmd_mutate,
)
from src.lib.commands.ops_cmd import (  # noqa: E402,F401
    cmd_cleanup,
    cmd_doctor,
    cmd_gitlab,
    cmd_status,
    cmd_verify,
)
from src.lib.commands.validate_cmd import (  # noqa: E402,F401
    _cmd_validate_async,
    _guess_failing_class,
    cmd_validate,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="testboost",
        description="TestBoost - Lightweight markdown-driven test generation",
    )
    parser.add_argument(
        "--list-plugins",
        action="store_true",
        help="List available technology plugins and exit",
    )
    subparsers = parser.add_subparsers(dest="command")

    # init
    p_init = subparsers.add_parser("init", help="Initialize .testboost/ in a project")
    p_init.add_argument("project_path", help="Path to the project")
    p_init.add_argument("--name", help="Session name")
    p_init.add_argument("--description", help="What to test and why")
    p_init.add_argument(
        "--tech",
        help="Technology plugin identifier (e.g. java-spring, python-pytest). Auto-detected if omitted.",
    )

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Analyze project structure")
    p_analyze.add_argument("project_path", help="Path to the project")
    p_analyze.add_argument("--verbose", "-v", action="store_true")

    # gaps
    p_gaps = subparsers.add_parser("gaps", help="Identify test coverage gaps")
    p_gaps.add_argument("project_path", help="Path to the Java project")
    p_gaps.add_argument("--verbose", "-v", action="store_true")

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate tests")
    p_gen.add_argument("project_path", help="Path to the Java project")
    p_gen.add_argument("--files", nargs="*", help="Filter specific files")
    p_gen.add_argument(
        "--no-runtime-fix",
        action="store_true",
        help="Skip the per-test `mvn test` auto-fix loop (compile-fix only)",
    )
    p_gen.add_argument("--verbose", "-v", action="store_true")
    p_gen.add_argument(
        "--fail-on-uncertainty",
        action="store_true",
        help="Pause with exit code 78 and emit question.json when extra context is needed",
    )
    p_gen.add_argument(
        "--answer-file",
        type=str,
        default=None,
        help="JSON file with answers/context to inject as test_requirements (for resume)",
    )

    # validate
    p_val = subparsers.add_parser("validate", help="Compile and run tests")
    p_val.add_argument("project_path", help="Path to the Java project")
    p_val.add_argument("--verbose", "-v", action="store_true")
    p_val.add_argument(
        "--fail-on-uncertainty", action="store_true",
        help="Pause with exit 78 and emit question.json when tests fail at runtime",
    )
    p_val.add_argument(
        "--answer-file", type=str, default=None,
        help="Signed JSON answer file (validate_fixes are applied before re-running)",
    )

    # mutate
    p_mutate = subparsers.add_parser("mutate", help="Run mutation testing with PIT")
    p_mutate.add_argument("project_path", help="Path to the Java project")
    p_mutate.add_argument("--target-classes", nargs="*", help="Specific classes to mutate")
    p_mutate.add_argument("--target-tests", nargs="*", help="Specific test classes to run")
    p_mutate.add_argument("--min-score", type=int, default=80, help="Minimum mutation score threshold")
    p_mutate.add_argument("--verbose", "-v", action="store_true")

    # killer
    p_killer = subparsers.add_parser("killer", help="Generate killer tests for surviving mutants")
    p_killer.add_argument("project_path", help="Path to the Java project")
    p_killer.add_argument("--max-tests", type=int, default=10, help="Maximum killer tests to generate")
    p_killer.add_argument("--verbose", "-v", action="store_true")
    p_killer.add_argument(
        "--fail-on-uncertainty", action="store_true",
        help="Pause with exit 78 when no killer tests can be generated",
    )
    p_killer.add_argument(
        "--answer-file", type=str, default=None,
        help="Signed JSON answer file (killer_hints injected into LLM context)",
    )

    # verify
    p_verify = subparsers.add_parser("verify", help="Verify an integrity token")
    p_verify.add_argument("project_path", help="Path to the Java project")
    p_verify.add_argument("token", help="The integrity token line to verify")

    # install
    p_install = subparsers.add_parser("install", help="Install TestBoost commands into a project")
    p_install.add_argument("project_path", help="Path to the target project")
    p_install.add_argument(
        "--shell-type",
        choices=["bash", "powershell"],
        default=None,
        help="Wrapper script type to install (prompted interactively if omitted)",
    )

    # status
    p_status = subparsers.add_parser("status", help="Show session status")
    p_status.add_argument("project_path", help="Path to the Java project")

    # resume â€” display pending question or apply signed answer
    p_resume = subparsers.add_parser(
        "resume",
        help="Show the pending question, or resume a paused session with --answer-file",
    )
    p_resume.add_argument("project_path", help="Path to the Java project")
    p_resume.add_argument(
        "--answer-file", default=None,
        help="Signed JSON answer file (run sign-answer first to produce one)",
    )
    p_resume.add_argument("--verbose", "-v", action="store_true")

    # sign-answer â€” utility to bind a raw answer to a question and HMAC-sign it
    p_sign = subparsers.add_parser(
        "sign-answer",
        help="Sign a raw answer payload against a pending question",
    )
    p_sign.add_argument("project_path", help="Path to the Java project")
    p_sign.add_argument("--question-file", required=True, help="Path to question.json")
    p_sign.add_argument("--answer-file", required=True, help="Path to raw answer JSON")
    p_sign.add_argument("--output", "-o", default=None, help="Write signed answer here (default: stdout)")

    # gitlab â€” MR helpers for CI jobs
    p_gitlab = subparsers.add_parser(
        "gitlab",
        help="GitLab MR helpers (post pending question / fetch signed answer)",
    )
    gitlab_sub = p_gitlab.add_subparsers(dest="gitlab_command", required=True)
    p_gl_post = gitlab_sub.add_parser(
        "post-question", help="Post the pending question.json as an MR note"
    )
    p_gl_post.add_argument("project_path", help="Path to the project")
    p_gl_fetch = gitlab_sub.add_parser(
        "fetch-answer", help="Find the developer's answer note and write a signed answer file"
    )
    p_gl_fetch.add_argument("project_path", help="Path to the project")
    p_gl_fetch.add_argument(
        "--output", "-o", default="./answer.json",
        help="Where to write the signed answer (default ./answer.json)",
    )

    # cleanup â€” mark abandoned sessions past TTL
    p_cleanup = subparsers.add_parser(
        "cleanup",
        help="Mark sessions in awaiting_input past TTL as abandoned",
    )
    p_cleanup.add_argument("project_path", help="Path to the project")
    p_cleanup.add_argument("--ttl-hours", type=int, default=24, help="Abandon threshold (default 24)")
    p_cleanup.add_argument("--dry-run", action="store_true", help="Just list, don't modify")

    # doctor â€” health check
    p_doctor = subparsers.add_parser(
        "doctor",
        help="Run health checks (LLM, .tb_secret, write perms, Maven)",
    )
    p_doctor.add_argument("project_path", help="Path to the project")

    args = parser.parse_args()

    # T020: --list-plugins exits before any subcommand is required
    if args.list_plugins:
        from src.lib.plugins import get_registry
        registry = get_registry()
        print("Available technology plugins:\n")
        for info in registry.list_plugins():
            patterns = ", ".join(info["detection_patterns"])
            print(f"  {info['identifier']:<16} {info['description']}")
            print(f"  {'':<16} detects: {patterns}\n")
        return 0

    if not args.command:
        parser.print_help()
        return 1

    commands = {
        "init": cmd_init,
        "analyze": cmd_analyze,
        "gaps": cmd_gaps,
        "generate": cmd_generate,
        "validate": cmd_validate,
        "mutate": cmd_mutate,
        "killer": cmd_killer,
        "verify": cmd_verify,
        "install": cmd_install,
        "status": cmd_status,
        "resume": cmd_resume,
        "sign-answer": cmd_sign_answer,
        "gitlab": cmd_gitlab,
        "cleanup": cmd_cleanup,
        "doctor": cmd_doctor,
    }

    # --- Run with metrics ---
    import time
    start = time.monotonic()
    exit_code = commands[args.command](args)
    duration_ms = int((time.monotonic() - start) * 1000)
    metrics = {
        "command": args.command,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "project_path": getattr(args, "project_path", None),
    }
    # stderr, so stdout consumers (sign-answer JSON, resume markdown) stay clean
    print(f"[TESTBOOST_METRICS:{json.dumps(metrics, separators=(',', ':'))}]", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
