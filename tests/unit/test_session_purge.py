"""Unit tests for session purge job."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.db.jobs.purge import SessionPurgeJob, run_purge_job
from src.db.jobs.scheduler import JobScheduler, create_default_scheduler


class TestSessionPurgeJob:
    """Tests for SessionPurgeJob class."""

    @pytest.mark.asyncio
    async def test_purge_deletes_old_sessions(self):
        """Test that purge job deletes sessions older than retention period."""
        old_session_id = uuid4()
        cutoff_date = datetime.utcnow() - timedelta(days=365)

        # Mock database session and queries
        with patch("src.db.jobs.purge.get_async_engine") as mock_engine:
            mock_async_session = AsyncMock()

            # Mock session query result - old completed session
            mock_sessions_result = MagicMock()
            mock_sessions_result.all.return_value = [(old_session_id,)]

            # Mock delete results
            mock_delete_result = MagicMock()
            mock_delete_result.rowcount = 1

            mock_async_session.execute = AsyncMock(
                side_effect=[
                    mock_sessions_result,  # SELECT sessions
                    mock_delete_result,     # DELETE artifacts
                    mock_delete_result,     # DELETE events
                    mock_delete_result,     # DELETE steps
                    mock_delete_result,     # DELETE sessions
                ]
            )
            mock_async_session.begin = MagicMock(return_value=AsyncMock())

            with patch("src.db.jobs.purge.AsyncSession", return_value=mock_async_session):
                mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
                mock_async_session.__aexit__ = AsyncMock(return_value=None)

                job = SessionPurgeJob(retention_days=365)
                result = await job.execute()

                assert result["sessions_purged"] == 1
                assert "cutoff_date" in result

    @pytest.mark.asyncio
    async def test_purge_preserves_recent_sessions(self):
        """Test that purge job does not delete recent sessions."""
        with patch("src.db.jobs.purge.get_async_engine") as mock_engine:
            mock_async_session = AsyncMock()

            # Mock empty session query result - no old sessions
            mock_sessions_result = MagicMock()
            mock_sessions_result.all.return_value = []

            mock_async_session.execute = AsyncMock(return_value=mock_sessions_result)
            mock_async_session.begin = MagicMock(return_value=AsyncMock())

            with patch("src.db.jobs.purge.AsyncSession", return_value=mock_async_session):
                mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
                mock_async_session.__aexit__ = AsyncMock(return_value=None)

                job = SessionPurgeJob(retention_days=365)
                result = await job.execute()

                assert result["sessions_purged"] == 0
                assert result["steps_purged"] == 0
                assert result["events_purged"] == 0
                assert result["artifacts_purged"] == 0

    @pytest.mark.asyncio
    async def test_purge_handles_empty_database(self):
        """Test that purge job handles empty database gracefully."""
        with patch("src.db.jobs.purge.get_async_engine") as mock_engine:
            mock_async_session = AsyncMock()

            # Mock empty result
            mock_sessions_result = MagicMock()
            mock_sessions_result.all.return_value = []

            mock_async_session.execute = AsyncMock(return_value=mock_sessions_result)
            mock_async_session.begin = MagicMock(return_value=AsyncMock())

            with patch("src.db.jobs.purge.AsyncSession", return_value=mock_async_session):
                mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
                mock_async_session.__aexit__ = AsyncMock(return_value=None)

                job = SessionPurgeJob(retention_days=365)
                result = await job.execute()

                assert result["sessions_purged"] == 0
                assert "cutoff_date" in result

    @pytest.mark.asyncio
    async def test_purge_logs_deletion_count(self):
        """Test that purge job logs the deletion count."""
        with patch("src.db.jobs.purge.get_async_engine") as mock_engine:
            with patch("src.db.jobs.purge.logger") as mock_logger:
                mock_async_session = AsyncMock()

                # Mock empty result
                mock_sessions_result = MagicMock()
                mock_sessions_result.all.return_value = []

                mock_async_session.execute = AsyncMock(return_value=mock_sessions_result)
                mock_async_session.begin = MagicMock(return_value=AsyncMock())

                with patch("src.db.jobs.purge.AsyncSession", return_value=mock_async_session):
                    mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
                    mock_async_session.__aexit__ = AsyncMock(return_value=None)

                    job = SessionPurgeJob(retention_days=365)
                    await job.execute()

                    # Verify logging was called
                    mock_logger.info.assert_called()
                    # Check for purge_job_completed log
                    log_calls = [str(c) for c in mock_logger.info.call_args_list]
                    assert any("purge_job" in str(c) for c in log_calls)

    @pytest.mark.asyncio
    async def test_purge_uses_configured_retention(self):
        """Test that purge job uses configured retention days."""
        with patch("src.db.jobs.purge.get_async_engine") as mock_engine:
            mock_async_session = AsyncMock()

            # Mock empty result
            mock_sessions_result = MagicMock()
            mock_sessions_result.all.return_value = []

            mock_async_session.execute = AsyncMock(return_value=mock_sessions_result)
            mock_async_session.begin = MagicMock(return_value=AsyncMock())

            with patch("src.db.jobs.purge.AsyncSession", return_value=mock_async_session):
                mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
                mock_async_session.__aexit__ = AsyncMock(return_value=None)

                # Use custom retention period
                job = SessionPurgeJob(retention_days=30)
                assert job.retention_days == 30

                result = await job.execute()
                assert "cutoff_date" in result


class TestRunPurgeJob:
    """Tests for run_purge_job convenience function."""

    @pytest.mark.asyncio
    async def test_run_purge_job_convenience(self):
        """Test run_purge_job convenience function."""
        with patch("src.db.jobs.purge.SessionPurgeJob") as MockJob:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = {"sessions_purged": 0}
            MockJob.return_value = mock_instance

            result = await run_purge_job()

            MockJob.assert_called_once_with(None)
            mock_instance.execute.assert_called_once()
            assert result == {"sessions_purged": 0}

    @pytest.mark.asyncio
    async def test_run_purge_job_with_custom_retention(self):
        """Test run_purge_job with custom retention days."""
        with patch("src.db.jobs.purge.SessionPurgeJob") as MockJob:
            mock_instance = AsyncMock()
            mock_instance.execute.return_value = {"sessions_purged": 5}
            MockJob.return_value = mock_instance

            result = await run_purge_job(retention_days=7)

            MockJob.assert_called_once_with(7)
            assert result == {"sessions_purged": 5}


class TestJobScheduler:
    """Tests for JobScheduler class."""

    def test_create_default_scheduler(self):
        """Test creating default scheduler with purge job registered."""
        scheduler = create_default_scheduler()

        assert isinstance(scheduler, JobScheduler)
        assert "session_purge" in scheduler._jobs

    def test_register_job_requires_schedule(self):
        """Test that register_job requires schedule_time or interval_hours."""
        scheduler = JobScheduler()

        with pytest.raises(ValueError) as exc_info:
            scheduler.register_job(
                name="test_job",
                job_func=AsyncMock(),
            )

        assert "schedule_time or interval_hours" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_run_job_now(self):
        """Test manual job execution."""
        scheduler = JobScheduler()
        mock_func = AsyncMock(return_value={"result": "success"})

        scheduler.register_job(
            name="test_job",
            job_func=mock_func,
            interval_hours=1,
        )

        result = await scheduler.run_job_now("test_job")

        mock_func.assert_called_once()
        assert result == {"result": "success"}

    @pytest.mark.asyncio
    async def test_run_job_now_not_found(self):
        """Test run_job_now raises KeyError for unknown job."""
        scheduler = JobScheduler()

        with pytest.raises(KeyError) as exc_info:
            await scheduler.run_job_now("nonexistent_job")

        assert "Job not found" in str(exc_info.value)


class TestDryRun:
    """Tests for dry run functionality."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_counts(self):
        """Test dry run returns counts without deleting."""
        with patch("src.db.jobs.purge.get_async_engine") as mock_engine:
            mock_async_session = AsyncMock()

            # Mock session query result
            mock_sessions_result = MagicMock()
            mock_sessions_result.all.return_value = [(uuid4(),), (uuid4(),)]

            # Mock related record counts
            mock_artifacts_result = MagicMock()
            mock_artifacts_result.all.return_value = [(uuid4(),)]

            mock_events_result = MagicMock()
            mock_events_result.all.return_value = [(uuid4(),), (uuid4(),), (uuid4(),)]

            mock_steps_result = MagicMock()
            mock_steps_result.all.return_value = [(uuid4(),), (uuid4(),)]

            mock_async_session.execute = AsyncMock(
                side_effect=[
                    mock_sessions_result,
                    mock_artifacts_result,
                    mock_events_result,
                    mock_steps_result,
                ]
            )

            with patch("src.db.jobs.purge.AsyncSession", return_value=mock_async_session):
                mock_async_session.__aenter__ = AsyncMock(return_value=mock_async_session)
                mock_async_session.__aexit__ = AsyncMock(return_value=None)

                job = SessionPurgeJob(retention_days=365)
                result = await job.dry_run()

                assert result["dry_run"] is True
                assert result["sessions_to_purge"] == 2
                assert result["artifacts_to_purge"] == 1
                assert result["events_to_purge"] == 3
                assert result["steps_to_purge"] == 2
