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
existing imports and test patches (`src.lib.cli.cmd_generate`, …) keep
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
from src.lib.commands.agent_cmd import cmd_context  # noqa: E402,F401
from src.lib.commands.analyze_cmd import (  # noqa: E402,F401
    _cmd_analyze_async,
    _cmd_gaps_async,
    cmd_analyze,
    cmd_gaps,
)
from src.lib.commands.check_cmd import cmd_check  # noqa: E402,F401
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
    cmd_equivalent,
    cmd_killer,
    cmd_mutate,
    cmd_pit_setup,
)
from src.lib.commands.ops_cmd import (  # noqa: E402,F401
    cmd_cleanup,
    cmd_doctor,
    cmd_github,
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
    p_gaps.add_argument(
        "--coverage", action="store_true",
        help="Java/Maven: measure line coverage with JaCoCo (runs the tests) instead of file-level gaps",
    )
    p_gaps.add_argument("--min-coverage", type=float, default=80.0,
                        help="(--coverage) classes below this line coverage are gaps (default 80)")
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
    p_gen.add_argument(
        "--agent",
        action="store_true",
        help="Agent mode: register and compile the tests written by the host agent (no LLM call); "
             "run `context` first",
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

    # context (agent mode)
    p_ctx = subparsers.add_parser(
        "context",
        help="Agent mode: write one generation prompt per gap (or per class with surviving mutants)",
    )
    p_ctx.add_argument("project_path", help="Path to the project")
    p_ctx.add_argument("--files", nargs="*", help="Filter specific files")
    p_ctx.add_argument("--killer", action="store_true", help="Prompts for the surviving mutants")
    p_ctx.add_argument("--max-tests", type=int, default=10, help="(--killer) maximum mutants targeted")
    p_ctx.add_argument("--verbose", "-v", action="store_true")

    # validate
    p_val = subparsers.add_parser("validate", help="Compile and run tests")
    p_val.add_argument("project_path", help="Path to the Java project")
    p_val.add_argument("--verbose", "-v", action="store_true")
    p_val.add_argument(
        "--full", action="store_true",
        help="Run the whole test suite (default: only the generated tests)",
    )
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
    p_mutate.add_argument(
        "--target-tests", nargs="*",
        help="Specific test classes to run (PIT checks they pass: `validate` is then optional)",
    )
    p_mutate.add_argument("--min-score", type=int, default=80, help="Minimum mutation score threshold")
    p_mutate.add_argument("--verbose", "-v", action="store_true")

    # killer
    p_killer = subparsers.add_parser("killer", help="Generate killer tests for surviving mutants")
    p_killer.add_argument("project_path", help="Path to the Java project")
    p_killer.add_argument("--max-tests", type=int, default=10, help="Maximum killer tests to generate")
    p_killer.add_argument(
        "--agent",
        action="store_true",
        help="Agent mode: register and compile the killer tests written by the host agent; "
             "run `context --killer` first",
    )
    p_killer.add_argument("--verbose", "-v", action="store_true")
    p_killer.add_argument(
        "--fail-on-uncertainty", action="store_true",
        help="Pause with exit 78 when no killer tests can be generated",
    )
    p_killer.add_argument(
        "--answer-file", type=str, default=None,
        help="Signed JSON answer file (killer_hints injected into LLM context)",
    )

    # equivalent
    p_eq = subparsers.add_parser(
        "equivalent",
        help="Declare surviving mutants equivalent (no test can observe them), list or withdraw declarations",
    )
    p_eq.add_argument("project_path", help="Path to the project")
    p_eq.add_argument("ids", nargs="*", help="Mutant ids from the last `mutate` report (none: list)")
    p_eq.add_argument("--reason", default="", help="Why no test can observe the mutation (required to declare)")
    p_eq.add_argument("--remove", action="store_true", help="Withdraw the given declarations")

    # check — the judge: measured coverage + mutation score, no session, no LLM
    p_check = subparsers.add_parser(
        "check",
        help="Measure line coverage (JaCoCo) and mutation score (PIT), optionally on the lines changed "
             "since a git ref; exit 0 pass, 1 below threshold, 2 measure failed",
    )
    p_check.add_argument("project_path", help="Path to the Maven project")
    p_check.add_argument("--base", help="Git ref (e.g. origin/main): judge only the lines changed since it")
    p_check.add_argument("--min-coverage", type=float, default=80.0, help="Minimum line coverage %% (default 80)")
    p_check.add_argument("--min-mutation", type=float, default=80.0,
                         help="Minimum mutation score %%, declared equivalents excluded (default 80)")
    p_check.add_argument("--no-mutation", action="store_true", help="Coverage only (skip PIT)")
    p_check.add_argument("--target-tests", nargs="*", help="Test classes PIT runs (default: all)")

    # pit-setup
    p_pit = subparsers.add_parser(
        "pit-setup", help="Declare PIT and its JUnit 5 plugin (pinned versions) in the root pom.xml")
    p_pit.add_argument("project_path", help="Path to the Maven project")

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

    # resume — display pending question or apply signed answer
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

    # sign-answer — utility to bind a raw answer to a question and HMAC-sign it
    p_sign = subparsers.add_parser(
        "sign-answer",
        help="Sign a raw answer payload against a pending question",
    )
    p_sign.add_argument("project_path", help="Path to the Java project")
    p_sign.add_argument("--question-file", required=True, help="Path to question.json")
    p_sign.add_argument("--answer-file", required=True, help="Path to raw answer JSON")
    p_sign.add_argument("--output", "-o", default=None, help="Write signed answer here (default: stdout)")

    # gitlab — MR helpers for CI jobs
    p_gitlab = subparsers.add_parser(
        "gitlab",
        help="GitLab MR helpers (post pending question / fetch signed answer)",
    )
    gitlab_sub = p_gitlab.add_subparsers(dest="gitlab_command", required=True)
    p_gl_post = gitlab_sub.add_parser(
        "post-question", help="Post the pending question.json as an MR note"
    )
    p_gl_post.add_argument("project_path", help="Path to the project")
    p_gl_report = gitlab_sub.add_parser(
        "post-report", help="Post (or update) the `check` report as a sticky MR note")
    p_gl_report.add_argument("project_path", help="Path to the project")
    p_gl_report.add_argument("--file", help="Report file (default: .testboost/check/report.md)")
    p_github = subparsers.add_parser("github", help="GitHub PR helpers for Actions")
    github_sub = p_github.add_subparsers(dest="github_command", required=True)
    p_gh_report = github_sub.add_parser(
        "post-report", help="Post (or update) the `check` report as a sticky PR comment")
    p_gh_report.add_argument("project_path", help="Path to the project")
    p_gh_report.add_argument("--file", help="Report file (default: .testboost/check/report.md)")
    p_gl_fetch = gitlab_sub.add_parser(
        "fetch-answer", help="Find the developer's answer note and write a signed answer file"
    )
    p_gl_fetch.add_argument("project_path", help="Path to the project")
    p_gl_fetch.add_argument(
        "--output", "-o", default="./answer.json",
        help="Where to write the signed answer (default ./answer.json)",
    )

    # cleanup — mark abandoned sessions past TTL
    p_cleanup = subparsers.add_parser(
        "cleanup",
        help="Mark sessions in awaiting_input past TTL as abandoned",
    )
    p_cleanup.add_argument("project_path", help="Path to the project")
    p_cleanup.add_argument("--ttl-hours", type=int, default=24, help="Abandon threshold (default 24)")
    p_cleanup.add_argument("--dry-run", action="store_true", help="Just list, don't modify")

    # doctor — health check
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
        "context": cmd_context,
        "validate": cmd_validate,
        "mutate": cmd_mutate,
        "killer": cmd_killer,
        "equivalent": cmd_equivalent,
        "check": cmd_check,
        "pit-setup": cmd_pit_setup,
        "verify": cmd_verify,
        "install": cmd_install,
        "status": cmd_status,
        "resume": cmd_resume,
        "sign-answer": cmd_sign_answer,
        "gitlab": cmd_gitlab,
        "github": cmd_github,
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
