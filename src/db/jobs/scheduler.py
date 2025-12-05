"""Job scheduler for background tasks."""

import asyncio
from collections.abc import Callable, Coroutine
from datetime import datetime, time
from typing import Any

from src.db.jobs.purge import SessionPurgeJob
from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class JobScheduler:
    """
    Simple job scheduler for running periodic background tasks.

    Supports scheduling jobs at specific times or intervals.
    """

    def __init__(self) -> None:
        """Initialize the scheduler."""
        self._running = False
        self._tasks: list[asyncio.Task[None]] = []
        self._jobs: dict[str, dict[str, Any]] = {}

    def register_job(
        self,
        name: str,
        job_func: Callable[[], Coroutine[Any, Any, Any]],
        schedule_time: time | None = None,
        interval_hours: int | None = None,
    ) -> None:
        """
        Register a job with the scheduler.

        Args:
            name: Unique job name
            job_func: Async function to execute
            schedule_time: Time of day to run (for daily jobs)
            interval_hours: Interval in hours (for periodic jobs)
        """
        if schedule_time is None and interval_hours is None:
            raise ValueError("Must specify either schedule_time or interval_hours")

        self._jobs[name] = {
            "func": job_func,
            "schedule_time": schedule_time,
            "interval_hours": interval_hours,
            "last_run": None,
        }

        logger.info(
            "job_registered",
            job_name=name,
            schedule_time=str(schedule_time) if schedule_time else None,
            interval_hours=interval_hours,
        )

    async def start(self) -> None:
        """Start the scheduler."""
        if self._running:
            logger.warning("scheduler_already_running")
            return

        self._running = True
        logger.info("scheduler_started", job_count=len(self._jobs))

        for name, job_config in self._jobs.items():
            task = asyncio.create_task(self._run_job_loop(name, job_config))
            self._tasks.append(task)

    async def stop(self) -> None:
        """Stop the scheduler and cancel all running tasks."""
        if not self._running:
            return

        self._running = False

        for task in self._tasks:
            task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        self._tasks.clear()
        logger.info("scheduler_stopped")

    async def _run_job_loop(self, name: str, job_config: dict[str, Any]) -> None:
        """
        Run a job in a loop based on its schedule.

        Args:
            name: Job name
            job_config: Job configuration
        """
        while self._running:
            try:
                # Calculate wait time
                if job_config["schedule_time"]:
                    wait_seconds = self._calculate_wait_until(job_config["schedule_time"])
                else:
                    # Interval-based scheduling
                    interval_seconds = job_config["interval_hours"] * 3600
                    if job_config["last_run"]:
                        elapsed = (datetime.utcnow() - job_config["last_run"]).total_seconds()
                        wait_seconds = max(0, interval_seconds - elapsed)
                    else:
                        wait_seconds = 0  # Run immediately on first start

                if wait_seconds > 0:
                    logger.debug(
                        "job_waiting",
                        job_name=name,
                        wait_seconds=wait_seconds,
                    )
                    await asyncio.sleep(wait_seconds)

                if not self._running:
                    break

                # Execute the job
                logger.info("job_executing", job_name=name)
                start_time = datetime.utcnow()

                try:
                    result = await job_config["func"]()
                    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

                    logger.info(
                        "job_completed",
                        job_name=name,
                        duration_ms=round(duration_ms, 2),
                        result=result,
                    )
                except Exception as e:
                    duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
                    logger.error(
                        "job_failed",
                        job_name=name,
                        duration_ms=round(duration_ms, 2),
                        error=str(e),
                    )

                job_config["last_run"] = datetime.utcnow()

                # For interval-based jobs, continue the loop
                # For time-based jobs, wait until next day
                if job_config["schedule_time"]:
                    # Wait at least 1 hour to avoid re-running
                    await asyncio.sleep(3600)

            except asyncio.CancelledError:
                logger.debug("job_cancelled", job_name=name)
                break
            except Exception as e:
                logger.error("job_loop_error", job_name=name, error=str(e))
                # Wait before retrying
                await asyncio.sleep(60)

    def _calculate_wait_until(self, target_time: time) -> float:
        """
        Calculate seconds until the next occurrence of target_time.

        Args:
            target_time: Time of day to wait for

        Returns:
            Seconds to wait
        """
        now = datetime.utcnow()
        target = datetime.combine(now.date(), target_time)

        if target <= now:
            # Target time already passed today, schedule for tomorrow
            target = target.replace(day=target.day + 1)

        return (target - now).total_seconds()

    async def run_job_now(self, name: str) -> Any:
        """
        Manually trigger a job to run immediately.

        Args:
            name: Job name

        Returns:
            Job result

        Raises:
            KeyError: If job not found
        """
        if name not in self._jobs:
            raise KeyError(f"Job not found: {name}")

        job_config = self._jobs[name]
        logger.info("job_manual_trigger", job_name=name)

        result = await job_config["func"]()
        job_config["last_run"] = datetime.utcnow()

        return result


def create_default_scheduler() -> JobScheduler:
    """
    Create a scheduler with default jobs configured.

    Returns:
        Configured JobScheduler instance
    """
    scheduler = JobScheduler()

    # Register session purge job - runs daily at 2 AM
    async def purge_job() -> dict[str, Any]:
        job = SessionPurgeJob()
        return await job.execute()

    scheduler.register_job(
        name="session_purge",
        job_func=purge_job,
        schedule_time=time(2, 0),  # 2 AM UTC
    )

    return scheduler


# Global scheduler instance
_scheduler: JobScheduler | None = None


def get_scheduler() -> "JobScheduler":
    """Get or create the global scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = create_default_scheduler()
    return _scheduler


async def start_scheduler() -> None:
    """Start the global scheduler."""
    scheduler = get_scheduler()
    await scheduler.start()


async def stop_scheduler() -> None:
    """Stop the global scheduler."""
    scheduler = get_scheduler()
    await scheduler.stop()


__all__ = [
    "JobScheduler",
    "create_default_scheduler",
    "get_scheduler",
    "start_scheduler",
    "stop_scheduler",
]
