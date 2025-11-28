"""
Get status tool for Git.

Gets the current git status of the repository.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def get_status(repo_path: str, include_untracked: bool = True) -> str:
    """
    Get the current git status of the repository.

    Args:
        repo_path: Path to the git repository
        include_untracked: Include untracked files in status

    Returns:
        JSON string with status results
    """
    repo_dir = Path(repo_path)

    if not (repo_dir / ".git").exists():
        return json.dumps({"success": False, "error": f"Not a git repository: {repo_path}"})

    results: dict[str, Any] = {
        "success": False,
        "repo_path": str(repo_dir.absolute()),
        "branch": "",
        "staged": [],
        "modified": [],
        "untracked": [],
        "ahead": 0,
        "behind": 0,
    }

    try:
        # Get current branch
        branch_cmd = ["git", "branch", "--show-current"]
        branch_process = await asyncio.create_subprocess_exec(
            *branch_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        branch_out, _ = await branch_process.communicate()
        results["branch"] = branch_out.decode().strip()

        # Get status with porcelain format for parsing
        status_cmd = ["git", "status", "--porcelain", "-b"]
        if not include_untracked:
            status_cmd.append("-uno")

        status_process = await asyncio.create_subprocess_exec(
            *status_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        status_out, _ = await status_process.communicate()

        # Parse porcelain output
        lines = status_out.decode().strip().split("\n")

        for line in lines:
            if not line:
                continue

            if line.startswith("##"):
                # Branch line with tracking info
                if "ahead" in line:
                    ahead_part = line.split("ahead ")[1].split("]")[0].split(",")[0]
                    results["ahead"] = int(ahead_part)
                if "behind" in line:
                    behind_part = line.split("behind ")[1].split("]")[0].split(",")[0]
                    results["behind"] = int(behind_part)
            else:
                # File status
                if len(line) >= 3:
                    index_status = line[0]
                    worktree_status = line[1]
                    filename = line[3:]

                    if index_status in "MADRC":
                        results["staged"].append(
                            {"file": filename, "status": _status_code_to_name(index_status)}
                        )

                    if worktree_status in "MD":
                        results["modified"].append(
                            {"file": filename, "status": _status_code_to_name(worktree_status)}
                        )

                    if index_status == "?" and worktree_status == "?":
                        results["untracked"].append(filename)

        # Get last commit info
        log_cmd = ["git", "log", "-1", "--format=%H|%s|%an|%ar"]
        log_process = await asyncio.create_subprocess_exec(
            *log_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        log_out, _ = await log_process.communicate()

        if log_out:
            parts = log_out.decode().strip().split("|")
            if len(parts) >= 4:
                results["last_commit"] = {
                    "hash": parts[0],
                    "message": parts[1],
                    "author": parts[2],
                    "relative_time": parts[3],
                }

        results["success"] = True
        results["is_clean"] = (
            len(results["staged"]) == 0
            and len(results["modified"]) == 0
            and len(results["untracked"]) == 0
        )

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


def _status_code_to_name(code: str) -> str:
    """Convert git status code to human-readable name."""
    status_map = {
        "M": "modified",
        "A": "added",
        "D": "deleted",
        "R": "renamed",
        "C": "copied",
        "?": "untracked",
    }
    return status_map.get(code, "unknown")
