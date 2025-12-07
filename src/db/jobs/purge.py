"""Session purge job for data retention compliance."""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import CursorResult, and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_async_engine
from src.db.models import Artifact, Event, Session, Step
from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class SessionPurgeJob:
    """
    Job to purge old sessions based on retention policy.

    Implements 1-year retention policy per data governance requirements.
    Deletes sessions and all related data (steps, events, artifacts).
    """

    def __init__(self, retention_days: int | None = None):
        """
        Initialize purge job.

        Args:
            retention_days: Number of days to retain sessions.
                          Defaults to settings.session_retention_days (365).
        """
        self.retention_days = retention_days or settings.session_retention_days
        self.engine = get_async_engine()

    async def execute(self) -> dict[str, Any]:
        """
        Execute the purge job.

        Returns:
            Dictionary with purge statistics including counts of deleted records.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

        logger.info(
            "purge_job_started",
            retention_days=self.retention_days,
            cutoff_date=cutoff_date.isoformat(),
        )

        async with AsyncSession(self.engine) as db_session:
            async with db_session.begin():
                # Find sessions to purge
                sessions_to_purge = await db_session.execute(
                    select(Session.id).where(
                        and_(
                            Session.created_at < cutoff_date,
                            Session.status.in_(["completed", "failed", "cancelled"]),
                        )
                    )
                )
                session_ids = [row[0] for row in sessions_to_purge.all()]

                if not session_ids:
                    logger.info("purge_job_completed", sessions_purged=0)
                    return {
                        "sessions_purged": 0,
                        "steps_purged": 0,
                        "events_purged": 0,
                        "artifacts_purged": 0,
                        "cutoff_date": cutoff_date.isoformat(),
                    }

                # Delete artifacts first (foreign key constraint)
                artifacts_result: CursorResult[Any] = await db_session.execute(
                    delete(Artifact).where(Artifact.session_id.in_(session_ids))
                )
                artifacts_purged = artifacts_result.rowcount or 0

                # Delete events
                events_result: CursorResult[Any] = await db_session.execute(
                    delete(Event).where(Event.session_id.in_(session_ids))
                )
                events_purged = events_result.rowcount or 0

                # Delete steps
                steps_result: CursorResult[Any] = await db_session.execute(
                    delete(Step).where(Step.session_id.in_(session_ids))
                )
                steps_purged = steps_result.rowcount or 0

                # Delete sessions
                sessions_result: CursorResult[Any] = await db_session.execute(
                    delete(Session).where(Session.id.in_(session_ids))
                )
                sessions_purged = sessions_result.rowcount or 0

        result = {
            "sessions_purged": sessions_purged,
            "steps_purged": steps_purged,
            "events_purged": events_purged,
            "artifacts_purged": artifacts_purged,
            "cutoff_date": cutoff_date.isoformat(),
        }

        logger.info(
            "purge_job_completed",
            **result,
        )

        return result

    async def dry_run(self) -> dict[str, Any]:
        """
        Perform a dry run to see what would be purged.

        Returns:
            Dictionary with counts of records that would be deleted.
        """
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)

        async with AsyncSession(self.engine) as db_session:
            # Count sessions to purge
            sessions_query = await db_session.execute(
                select(Session.id).where(
                    and_(
                        Session.created_at < cutoff_date,
                        Session.status.in_(["completed", "failed", "cancelled"]),
                    )
                )
            )
            session_ids = [row[0] for row in sessions_query.all()]

            if not session_ids:
                return {
                    "sessions_to_purge": 0,
                    "steps_to_purge": 0,
                    "events_to_purge": 0,
                    "artifacts_to_purge": 0,
                    "cutoff_date": cutoff_date.isoformat(),
                    "dry_run": True,
                }

            # Count related records
            artifacts_query = await db_session.execute(
                select(Artifact.id).where(Artifact.session_id.in_(session_ids))
            )
            artifacts_count = len(artifacts_query.all())

            events_query = await db_session.execute(
                select(Event.id).where(Event.session_id.in_(session_ids))
            )
            events_count = len(events_query.all())

            steps_query = await db_session.execute(
                select(Step.id).where(Step.session_id.in_(session_ids))
            )
            steps_count = len(steps_query.all())

        return {
            "sessions_to_purge": len(session_ids),
            "steps_to_purge": steps_count,
            "events_to_purge": events_count,
            "artifacts_to_purge": artifacts_count,
            "cutoff_date": cutoff_date.isoformat(),
            "dry_run": True,
        }


async def run_purge_job(retention_days: int | None = None) -> dict[str, Any]:
    """
    Convenience function to run the purge job.

    Args:
        retention_days: Optional override for retention period.

    Returns:
        Purge statistics.
    """
    job = SessionPurgeJob(retention_days)
    return await job.execute()


__all__ = ["SessionPurgeJob", "run_purge_job"]
