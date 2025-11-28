"""
Commit changes tool for Git.

Commits staged changes with a descriptive message.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def commit_changes(repo_path: str, message: str, files: list[str] | None = None) -> str:
    """
    Commit staged changes with a descriptive message.

    Args:
        repo_path: Path to the git repository
        message: Commit message
        files: Specific files to commit (empty for all staged)

    Returns:
        JSON string with commit results
    """
    repo_dir = Path(repo_path)

    if not (repo_dir / ".git").exists():
        return json.dumps({"success": False, "error": f"Not a git repository: {repo_path}"})

    results: dict[str, Any] = {
        "success": False,
        "repo_path": str(repo_dir.absolute()),
        "message": message,
    }

    try:
        # Stage files if specified
        if files:
            for file in files:
                add_cmd = ["git", "add", file]
                add_process = await asyncio.create_subprocess_exec(
                    *add_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                _, add_err = await add_process.communicate()

                if add_process.returncode != 0:
                    results["error"] = f"Failed to stage file '{file}': {add_err.decode().strip()}"
                    return json.dumps(results, indent=2)

            results["staged_files"] = files

        # Check if there are staged changes
        status_cmd = ["git", "diff", "--cached", "--stat"]
        status_process = await asyncio.create_subprocess_exec(
            *status_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        status_out, _ = await status_process.communicate()

        if not status_out.decode().strip():
            results["error"] = "No staged changes to commit"
            return json.dumps(results, indent=2)

        # Perform the commit
        commit_cmd = ["git", "commit", "-m", message]
        commit_process = await asyncio.create_subprocess_exec(
            *commit_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = await commit_process.communicate()

        if commit_process.returncode == 0:
            results["success"] = True
            results["output"] = stdout.decode().strip()

            # Get commit hash
            hash_cmd = ["git", "rev-parse", "HEAD"]
            hash_process = await asyncio.create_subprocess_exec(
                *hash_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            hash_out, _ = await hash_process.communicate()
            results["commit_hash"] = hash_out.decode().strip()

            # Get commit stats
            stats_cmd = ["git", "show", "--stat", "--oneline", "HEAD"]
            stats_process = await asyncio.create_subprocess_exec(
                *stats_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            stats_out, _ = await stats_process.communicate()
            results["stats"] = stats_out.decode().strip()

        else:
            results["error"] = stderr.decode().strip()

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)
