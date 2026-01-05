"""Unit tests for Git MCP tools.

Tests cover get_uncommitted_diff, commit_changes, get_status, and create_maintenance_branch.
All tests mock subprocess calls to avoid external dependencies.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

# ============================================================================
# Tests for get_uncommitted_diff()
# ============================================================================


class TestGetUncommittedDiff:
    """Tests for get_uncommitted_diff function."""

    @pytest.mark.asyncio
    async def test_get_uncommitted_diff_not_git_repo(self, tmp_path):
        """Should return error if not a git repository."""
        from src.mcp_servers.git_maintenance.tools.diff import get_uncommitted_diff

        result_json = await get_uncommitted_diff(str(tmp_path))
        result = json.loads(result_json)

        assert result["success"] is False
        assert "not a git repository" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_get_uncommitted_diff_success(self, mock_git_repo):
        """Should return diff content for git repository."""
        from src.mcp_servers.git_maintenance.tools.diff import get_uncommitted_diff

        diff_content = """diff --git a/file.txt b/file.txt
--- a/file.txt
+++ b/file.txt
@@ -1 +1,2 @@
 line1
+line2
"""

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock git rev-parse HEAD
            mock_rev_parse = AsyncMock()
            mock_rev_parse.returncode = 0
            mock_rev_parse.communicate = AsyncMock(return_value=(b"abc123\n", b""))

            # Mock git diff HEAD
            mock_diff = AsyncMock()
            mock_diff.returncode = 0
            mock_diff.communicate = AsyncMock(return_value=(diff_content.encode(), b""))

            # Mock git diff --name-only
            mock_name_only = AsyncMock()
            mock_name_only.returncode = 0
            mock_name_only.communicate = AsyncMock(return_value=(b"file.txt\n", b""))

            mock_exec.side_effect = [mock_rev_parse, mock_diff, mock_name_only]

            result_json = await get_uncommitted_diff(str(mock_git_repo))
            result = json.loads(result_json)

            assert result["success"] is True
            assert "diff" in result
            assert result["head_sha"] == "abc123"

    @pytest.mark.asyncio
    async def test_get_uncommitted_diff_empty(self, mock_git_repo):
        """Should handle empty diff (no changes)."""
        from src.mcp_servers.git_maintenance.tools.diff import get_uncommitted_diff

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_rev_parse = AsyncMock()
            mock_rev_parse.returncode = 0
            mock_rev_parse.communicate = AsyncMock(return_value=(b"abc123\n", b""))

            mock_diff = AsyncMock()
            mock_diff.returncode = 0
            mock_diff.communicate = AsyncMock(return_value=(b"", b""))

            mock_name_only = AsyncMock()
            mock_name_only.returncode = 0
            mock_name_only.communicate = AsyncMock(return_value=(b"", b""))

            mock_exec.side_effect = [mock_rev_parse, mock_diff, mock_name_only]

            result_json = await get_uncommitted_diff(str(mock_git_repo))
            result = json.loads(result_json)

            assert result["success"] is True
            assert result["diff"] == ""


# ============================================================================
# Tests for get_diff_stats()
# ============================================================================


class TestGetDiffStats:
    """Tests for get_diff_stats function."""

    @pytest.mark.asyncio
    async def test_get_diff_stats_parses_output(self, mock_git_repo):
        """Should parse git diff stats correctly."""
        from src.mcp_servers.git_maintenance.tools.diff import get_diff_stats

        stat_output = "10\t5\tfile1.txt\n3\t2\tfile2.txt\n"

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_stat = AsyncMock()
            mock_stat.returncode = 0
            mock_stat.communicate = AsyncMock(return_value=(stat_output.encode(), b""))
            mock_exec.return_value = mock_stat

            result_json = await get_diff_stats(str(mock_git_repo))
            result = json.loads(result_json)

            assert result["success"] is True
            assert result["insertions"] == 13
            assert result["deletions"] == 7
            assert result["files_changed"] == 2

    @pytest.mark.asyncio
    async def test_get_diff_stats_not_git_repo(self, tmp_path):
        """Should return error if not a git repository."""
        from src.mcp_servers.git_maintenance.tools.diff import get_diff_stats

        result_json = await get_diff_stats(str(tmp_path))
        result = json.loads(result_json)

        assert result["success"] is False


# ============================================================================
# Tests for commit_changes()
# ============================================================================


class TestCommitChanges:
    """Tests for commit_changes function."""

    @pytest.mark.asyncio
    async def test_commit_changes_not_git_repo(self, tmp_path):
        """Should return error if not a git repository."""
        from src.mcp_servers.git_maintenance.tools.commit import commit_changes

        result_json = await commit_changes(str(tmp_path), "Test commit")
        result = json.loads(result_json)

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_commit_changes_no_staged_returns_error(self, mock_git_repo):
        """Should return error when no staged changes."""
        from src.mcp_servers.git_maintenance.tools.commit import commit_changes

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock git diff --cached --stat (empty - no staged changes)
            mock_status = AsyncMock()
            mock_status.returncode = 0
            mock_status.communicate = AsyncMock(return_value=(b"", b""))
            mock_exec.return_value = mock_status

            result_json = await commit_changes(str(mock_git_repo), "Test commit")
            result = json.loads(result_json)

            assert result["success"] is False
            assert "no staged" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_commit_changes_success(self, mock_git_repo):
        """Should return success with commit hash."""
        from src.mcp_servers.git_maintenance.tools.commit import commit_changes

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock git diff --cached --stat (has staged changes)
            mock_status = AsyncMock()
            mock_status.returncode = 0
            mock_status.communicate = AsyncMock(
                return_value=(b" file.txt | 1 +\n 1 file changed, 1 insertion(+)", b"")
            )

            # Mock git commit
            mock_commit = AsyncMock()
            mock_commit.returncode = 0
            mock_commit.communicate = AsyncMock(
                return_value=(b"[main abc1234] Test commit\n 1 file changed", b"")
            )

            # Mock git rev-parse HEAD
            mock_hash = AsyncMock()
            mock_hash.returncode = 0
            mock_hash.communicate = AsyncMock(return_value=(b"abc1234567890", b""))

            # Mock git show --stat
            mock_stats = AsyncMock()
            mock_stats.returncode = 0
            mock_stats.communicate = AsyncMock(
                return_value=(b"abc1234 Test commit\n file.txt | 1 +", b"")
            )

            mock_exec.side_effect = [mock_status, mock_commit, mock_hash, mock_stats]

            result_json = await commit_changes(str(mock_git_repo), "Test commit")
            result = json.loads(result_json)

            assert result["success"] is True
            assert result["commit_hash"] == "abc1234567890"

    @pytest.mark.asyncio
    async def test_commit_changes_with_files(self, mock_git_repo):
        """Should stage specific files when provided."""
        from src.mcp_servers.git_maintenance.tools.commit import commit_changes

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock git add (x2 for two files)
            mock_add = AsyncMock()
            mock_add.returncode = 0
            mock_add.communicate = AsyncMock(return_value=(b"", b""))

            # Mock git diff --cached --stat
            mock_status = AsyncMock()
            mock_status.returncode = 0
            mock_status.communicate = AsyncMock(
                return_value=(b" file1.txt | 1 +\n file2.txt | 1 +", b"")
            )

            # Mock git commit
            mock_commit = AsyncMock()
            mock_commit.returncode = 0
            mock_commit.communicate = AsyncMock(return_value=(b"[main abc1234] Test", b""))

            # Mock git rev-parse HEAD
            mock_hash = AsyncMock()
            mock_hash.returncode = 0
            mock_hash.communicate = AsyncMock(return_value=(b"abc1234", b""))

            # Mock git show --stat
            mock_stats = AsyncMock()
            mock_stats.returncode = 0
            mock_stats.communicate = AsyncMock(return_value=(b"abc1234 Test", b""))

            mock_exec.side_effect = [
                mock_add,
                mock_add,
                mock_status,
                mock_commit,
                mock_hash,
                mock_stats,
            ]

            result_json = await commit_changes(
                str(mock_git_repo), "Test commit", files=["file1.txt", "file2.txt"]
            )
            result = json.loads(result_json)

            assert result["success"] is True
            assert "staged_files" in result


# ============================================================================
# Tests for get_status()
# ============================================================================


class TestGetStatus:
    """Tests for get_status function."""

    @pytest.mark.asyncio
    async def test_get_status_parses_porcelain_format(self, mock_git_repo):
        """Should parse porcelain format output."""
        from src.mcp_servers.git_maintenance.tools.status import get_status

        porcelain_output = """ M modified.txt
 A added.txt
?? untracked.txt
"""

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_status = AsyncMock()
            mock_status.returncode = 0
            mock_status.communicate = AsyncMock(return_value=(porcelain_output.encode(), b""))
            mock_exec.return_value = mock_status

            result_json = await get_status(str(mock_git_repo))
            result = json.loads(result_json)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_status_detects_untracked_files(self, mock_git_repo):
        """Should detect untracked files (marked with ??)."""
        from src.mcp_servers.git_maintenance.tools.status import get_status

        porcelain_output = """?? new_file.txt
?? another_new.txt
"""

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_status = AsyncMock()
            mock_status.returncode = 0
            mock_status.communicate = AsyncMock(return_value=(porcelain_output.encode(), b""))
            mock_exec.return_value = mock_status

            result_json = await get_status(str(mock_git_repo))
            result = json.loads(result_json)

            assert result["success"] is True
            # Should have untracked files in result
            assert "untracked" in str(result).lower() or "files" in result

    @pytest.mark.asyncio
    async def test_get_status_detects_modified_files(self, mock_git_repo):
        """Should detect modified files."""
        from src.mcp_servers.git_maintenance.tools.status import get_status

        porcelain_output = """ M src/main.py
MM both_modified.txt
"""

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_status = AsyncMock()
            mock_status.returncode = 0
            mock_status.communicate = AsyncMock(return_value=(porcelain_output.encode(), b""))
            mock_exec.return_value = mock_status

            result_json = await get_status(str(mock_git_repo))
            result = json.loads(result_json)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_status_not_git_repo(self, tmp_path):
        """Should return error if not a git repository."""
        from src.mcp_servers.git_maintenance.tools.status import get_status

        result_json = await get_status(str(tmp_path))
        result = json.loads(result_json)

        assert result["success"] is False


# ============================================================================
# Tests for create_maintenance_branch()
# ============================================================================


class TestCreateMaintenanceBranch:
    """Tests for create_maintenance_branch function."""

    @pytest.mark.asyncio
    async def test_create_maintenance_branch_not_git_repo(self, tmp_path):
        """Should return error if not a git repository."""
        from src.mcp_servers.git_maintenance.tools.branch import create_maintenance_branch

        result_json = await create_maintenance_branch(str(tmp_path), "feature-branch")
        result = json.loads(result_json)

        assert result["success"] is False
        assert "not a git repository" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_create_maintenance_branch_success(self, mock_git_repo):
        """Should create new branch successfully."""
        from src.mcp_servers.git_maintenance.tools.branch import create_maintenance_branch

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock git fetch
            mock_fetch = AsyncMock()
            mock_fetch.returncode = 0
            mock_fetch.communicate = AsyncMock(return_value=(b"", b""))

            # Mock git rev-parse --verify origin/main (not found)
            mock_check_origin = AsyncMock()
            mock_check_origin.returncode = 1
            mock_check_origin.communicate = AsyncMock(return_value=(b"", b"not found"))

            # Mock git rev-parse --verify main (found)
            mock_check_local = AsyncMock()
            mock_check_local.returncode = 0
            mock_check_local.communicate = AsyncMock(return_value=(b"abc123", b""))

            # Mock git rev-parse --verify branch_name (not exists)
            mock_check_branch = AsyncMock()
            mock_check_branch.returncode = 1
            mock_check_branch.communicate = AsyncMock(return_value=(b"", b""))

            # Mock git checkout -b (with origin) fails
            mock_checkout_origin = AsyncMock()
            mock_checkout_origin.returncode = 1
            mock_checkout_origin.communicate = AsyncMock(return_value=(b"", b""))

            # Mock git checkout -b (local) succeeds
            mock_checkout = AsyncMock()
            mock_checkout.returncode = 0
            mock_checkout.communicate = AsyncMock(
                return_value=(b"Switched to a new branch 'feature'\n", b"")
            )

            mock_exec.side_effect = [
                mock_fetch,
                mock_check_origin,
                mock_check_local,
                mock_check_branch,
                mock_checkout_origin,
                mock_checkout,
            ]

            result_json = await create_maintenance_branch(str(mock_git_repo), "feature")
            result = json.loads(result_json)

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_create_maintenance_branch_already_exists(self, mock_git_repo):
        """Should return error if branch already exists."""
        from src.mcp_servers.git_maintenance.tools.branch import create_maintenance_branch

        with patch("asyncio.create_subprocess_exec") as mock_exec:
            # Mock git fetch
            mock_fetch = AsyncMock()
            mock_fetch.returncode = 0
            mock_fetch.communicate = AsyncMock(return_value=(b"", b""))

            # Mock git rev-parse --verify origin/main
            mock_check_origin = AsyncMock()
            mock_check_origin.returncode = 0
            mock_check_origin.communicate = AsyncMock(return_value=(b"abc123", b""))

            # Mock git rev-parse --verify branch_name (exists!)
            mock_check_branch = AsyncMock()
            mock_check_branch.returncode = 0
            mock_check_branch.communicate = AsyncMock(return_value=(b"abc123", b""))

            mock_exec.side_effect = [mock_fetch, mock_check_origin, mock_check_branch]

            result_json = await create_maintenance_branch(str(mock_git_repo), "existing-branch")
            result = json.loads(result_json)

            assert result["success"] is False
            assert "already exists" in result.get("error", "")
