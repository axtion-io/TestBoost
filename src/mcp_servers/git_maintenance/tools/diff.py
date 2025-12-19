"""Git diff extraction tool (T007).

Extracts uncommitted changes from a git repository per FR-001.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def get_uncommitted_diff(
    repo_path: str,
    context_lines: int = 3,
) -> str:
    """
    Get the git diff of uncommitted changes (working directory vs HEAD).

    Per FR-001, this captures all uncommitted changes (staged + unstaged).

    Args:
        repo_path: Path to the git repository
        context_lines: Number of context lines in unified diff (default: 3)

    Returns:
        JSON string with diff content and metadata
    """
    repo_dir = Path(repo_path)

    if not (repo_dir / ".git").exists():
        return json.dumps({"success": False, "error": f"Not a git repository: {repo_path}"})

    results: dict[str, Any] = {
        "success": False,
        "repo_path": str(repo_dir.absolute()),
        "diff": "",
        "files_changed": [],
        "total_lines": 0,
        "head_sha": "",
    }

    try:
        # Get HEAD commit SHA
        head_cmd = ["git", "rev-parse", "HEAD"]
        head_process = await asyncio.create_subprocess_exec(
            *head_cmd,
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        head_out, _ = await head_process.communicate()
        results["head_sha"] = head_out.decode().strip()

        # Get diff of uncommitted changes (staged + unstaged vs HEAD)
        diff_cmd = [
            "git",
            "diff",
            "HEAD",
            f"-U{context_lines}",
            "--no-color",
        ]
        diff_process = await asyncio.create_subprocess_exec(
            *diff_cmd,
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        diff_out, diff_err = await diff_process.communicate()

        if diff_process.returncode != 0:
            error_msg = diff_err.decode().strip()
            return json.dumps({"success": False, "error": f"Git diff failed: {error_msg}"})

        diff_content = diff_out.decode()
        results["diff"] = diff_content

        # Count lines in diff
        if diff_content:
            results["total_lines"] = len(diff_content.splitlines())

        # Get list of changed files
        stat_cmd = ["git", "diff", "HEAD", "--name-only"]
        stat_process = await asyncio.create_subprocess_exec(
            *stat_cmd,
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stat_out, _ = await stat_process.communicate()
        files = [f for f in stat_out.decode().strip().split("\n") if f]
        results["files_changed"] = files

        results["success"] = True

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


async def get_diff_stats(repo_path: str) -> str:
    """
    Get statistics about uncommitted changes.

    Args:
        repo_path: Path to the git repository

    Returns:
        JSON string with diff statistics
    """
    repo_dir = Path(repo_path)

    if not (repo_dir / ".git").exists():
        return json.dumps({"success": False, "error": f"Not a git repository: {repo_path}"})

    results: dict[str, Any] = {
        "success": False,
        "repo_path": str(repo_dir.absolute()),
        "insertions": 0,
        "deletions": 0,
        "files_changed": 0,
    }

    try:
        # Get diff stats
        stat_cmd = ["git", "diff", "HEAD", "--stat", "--numstat"]
        stat_process = await asyncio.create_subprocess_exec(
            *stat_cmd,
            cwd=repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stat_out, _ = await stat_process.communicate()

        lines = stat_out.decode().strip().split("\n")
        for line in lines:
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                try:
                    insertions = int(parts[0]) if parts[0] != "-" else 0
                    deletions = int(parts[1]) if parts[1] != "-" else 0
                    results["insertions"] += insertions
                    results["deletions"] += deletions
                    results["files_changed"] += 1
                except ValueError:
                    continue

        results["success"] = True

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)
