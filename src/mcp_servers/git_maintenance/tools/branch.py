"""
Create maintenance branch tool for Git.

Creates a new branch for maintenance work.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def create_maintenance_branch(
    repo_path: str, branch_name: str, base_branch: str = "main"
) -> str:
    """
    Create a new branch for maintenance work.

    Args:
        repo_path: Path to the git repository
        branch_name: Name for the new maintenance branch
        base_branch: Base branch to create from

    Returns:
        JSON string with creation results
    """
    repo_dir = Path(repo_path)

    if not (repo_dir / ".git").exists():
        return json.dumps({"success": False, "error": f"Not a git repository: {repo_path}"})

    results: dict[str, Any] = {
        "success": False,
        "repo_path": str(repo_dir.absolute()),
        "branch_name": branch_name,
        "base_branch": base_branch,
    }

    try:
        # Fetch latest from remote
        fetch_cmd = ["git", "fetch", "origin"]
        fetch_process = await asyncio.create_subprocess_exec(
            *fetch_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await fetch_process.communicate()

        # Check if base branch exists
        check_cmd = ["git", "rev-parse", "--verify", f"origin/{base_branch}"]
        check_process = await asyncio.create_subprocess_exec(
            *check_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, check_err = await check_process.communicate()

        if check_process.returncode != 0:
            # Try local base branch
            check_cmd = ["git", "rev-parse", "--verify", base_branch]
            check_process = await asyncio.create_subprocess_exec(
                *check_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            _, check_err = await check_process.communicate()

            if check_process.returncode != 0:
                results["error"] = f"Base branch '{base_branch}' not found"
                return json.dumps(results, indent=2)

        # Check if branch already exists
        check_existing_cmd = ["git", "rev-parse", "--verify", branch_name]
        check_existing = await asyncio.create_subprocess_exec(
            *check_existing_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await check_existing.communicate()

        if check_existing.returncode == 0:
            results["error"] = f"Branch '{branch_name}' already exists"
            return json.dumps(results, indent=2)

        # Create and checkout new branch
        create_cmd = ["git", "checkout", "-b", branch_name, f"origin/{base_branch}"]
        create_process = await asyncio.create_subprocess_exec(
            *create_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        stdout, stderr = await create_process.communicate()

        if create_process.returncode == 0:
            results["success"] = True
            results["message"] = f"Created and switched to branch '{branch_name}'"

            # Get current commit
            commit_cmd = ["git", "rev-parse", "HEAD"]
            commit_process = await asyncio.create_subprocess_exec(
                *commit_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            commit_out, _ = await commit_process.communicate()
            results["commit"] = commit_out.decode().strip()
        else:
            # Try without origin/ prefix
            create_cmd = ["git", "checkout", "-b", branch_name, base_branch]
            create_process = await asyncio.create_subprocess_exec(
                *create_cmd, cwd=repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            stdout, stderr = await create_process.communicate()

            if create_process.returncode == 0:
                results["success"] = True
                results["message"] = f"Created and switched to branch '{branch_name}'"
            else:
                results["error"] = stderr.decode().strip()

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)
