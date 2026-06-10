# SPDX-License-Identifier: Apache-2.0
"""testboost install — deploy slash commands into a project."""

import argparse
import sys
from pathlib import Path

from src.lib.commands._shared import TESTBOOST_ROOT


def _prompt_shell_type() -> str:
    """Prompt the user to choose between bash and powershell scripts."""
    print("Which shell type do you want for wrapper scripts?")
    print("  1) bash       (Linux / macOS / Git Bash)")
    print("  2) powershell (Windows PowerShell)")
    while True:
        choice = input("Enter 1 or 2: ").strip()
        if choice == "1":
            return "bash"
        if choice == "2":
            return "powershell"
        print("Invalid choice. Please enter 1 or 2.")
def cmd_install(args: argparse.Namespace) -> int:
    """Install TestBoost commands into a target project.

    Copies slash-command markdown files and shell scripts to the target
    project, with paths resolved to the current TestBoost installation.
    This ensures the LLM CLI always calls the real TestBoost CLI.
    """
    from src.lib.installer import install_commands

    project_path = args.project_path
    if not Path(project_path).exists():
        print(f"Error: Project path does not exist: {project_path}", file=sys.stderr)
        return 1

    shell_type = args.shell_type
    if shell_type is None:
        shell_type = _prompt_shell_type()

    result = install_commands(
        project_path=project_path,
        testboost_root=str(TESTBOOST_ROOT),
        shell_type=shell_type,
    )

    if result["success"]:
        print(f"[+] {result['message']}")
        for detail in result.get("details", []):
            print(f"    {detail}")
        return 0
    else:
        print(f"[X] {result['message']}", file=sys.stderr)
        return 1
