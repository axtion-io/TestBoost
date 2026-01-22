"""LangChain BaseTool wrappers for Git Maintenance MCP tools."""

from langchain_core.tools import BaseTool, tool

from src.lib.logging import get_logger

# Import existing MCP tool implementations
from src.mcp_servers.git_maintenance.tools.branch import create_maintenance_branch
from src.mcp_servers.git_maintenance.tools.commit import commit_changes
from src.mcp_servers.git_maintenance.tools.diff import get_uncommitted_diff
from src.mcp_servers.git_maintenance.tools.status import get_status

logger = get_logger(__name__)


@tool
async def git_create_maintenance_branch(
    repo_path: str, branch_name: str, base_branch: str = "main"
) -> str:
    """
    Create a new branch for maintenance work.

    Use this tool to:
    - Create a new branch for dependency updates or fixes
    - Isolate maintenance changes from main branch
    - Prepare for pull request creation
    - Enable rollback if changes fail

    Args:
        repo_path: Path to the git repository root directory
        branch_name: Name for the new maintenance branch (e.g., "deps/update-spring-boot")
        base_branch: Base branch to create from (default: "main")

    Returns:
        Success message with branch name and current HEAD
    """
    logger.info(
        "mcp_tool_called",
        tool="git_create_maintenance_branch",
        repo_path=repo_path,
        branch_name=branch_name,
        base_branch=base_branch,
    )

    result = await create_maintenance_branch(
        repo_path=repo_path, branch_name=branch_name, base_branch=base_branch
    )

    logger.info(
        "mcp_tool_completed", tool="git_create_maintenance_branch", result_length=len(result)
    )

    return result


@tool
async def git_commit_changes(repo_path: str, message: str, files: list[str] | None = None) -> str:
    """
    Commit staged changes with a descriptive message.

    Use this tool to:
    - Commit dependency updates to pom.xml
    - Commit generated test files
    - Commit Docker configuration files
    - Create atomic commits for rollback capability

    Args:
        repo_path: Path to the git repository root directory
        message: Commit message describing the changes
        files: Specific files to commit (if empty, commits all staged files)

    Returns:
        Commit hash and summary of committed files
    """
    logger.info(
        "mcp_tool_called",
        tool="git_commit_changes",
        repo_path=repo_path,
        message=message,
        files=files,
    )

    result = await commit_changes(repo_path=repo_path, message=message, files=files or [])

    logger.info("mcp_tool_completed", tool="git_commit_changes", result_length=len(result))

    return result


@tool
async def git_get_uncommitted_diff(
    repo_path: str,
    context_lines: int = 3,
) -> str:
    """
    Get the git diff of all uncommitted changes (staged + unstaged vs HEAD).

    Use this tool to:
    - Analyze what code has changed before test generation
    - Identify files that need impact analysis
    - Get the raw diff for categorization

    Args:
        repo_path: Path to the git repository root directory
        context_lines: Number of context lines in unified diff (default: 3)

    Returns:
        JSON with diff content, files changed, and total lines
    """
    logger.info(
        "mcp_tool_called",
        tool="git_get_uncommitted_diff",
        repo_path=repo_path,
        context_lines=context_lines,
    )

    result = await get_uncommitted_diff(
        repo_path=repo_path,
        context_lines=context_lines,
    )

    logger.info(
        "mcp_tool_completed",
        tool="git_get_uncommitted_diff",
        result_length=len(result),
    )

    return result


@tool
async def git_get_status(repo_path: str, include_untracked: bool = True) -> str:
    """
    Get the current git status of the repository.

    Use this tool to:
    - Check for uncommitted changes before starting maintenance
    - Verify changes after dependency updates
    - List modified files for commit
    - Detect untracked files from code generation

    Args:
        repo_path: Path to the git repository root directory
        include_untracked: Include untracked files in status (default: True)

    Returns:
        Git status with staged, unstaged, and untracked files
    """
    logger.info(
        "mcp_tool_called",
        tool="git_get_status",
        repo_path=repo_path,
        include_untracked=include_untracked,
    )

    result = await get_status(repo_path=repo_path, include_untracked=include_untracked)

    logger.info("mcp_tool_completed", tool="git_get_status", result_length=len(result))

    return result


def get_git_tools() -> list[BaseTool]:
    """
    Get all Git maintenance tools as BaseTool instances.

    Returns:
        List of 4 Git maintenance tools:
        - git_create_maintenance_branch: Create a new branch
        - git_commit_changes: Commit changes
        - git_get_uncommitted_diff: Get diff of uncommitted changes
        - git_get_status: Get repository status
    """
    return [
        git_create_maintenance_branch,
        git_commit_changes,
        git_get_uncommitted_diff,
        git_get_status,
    ]


__all__ = [
    "get_git_tools",
    "git_create_maintenance_branch",
    "git_commit_changes",
    "git_get_uncommitted_diff",
    "git_get_status",
]
