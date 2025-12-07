"""Project lock service for exclusive access."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import ProjectLock
from src.db.repository import ProjectLockRepository
from src.lib.config import get_settings
from src.lib.logging import get_logger

logger = get_logger(__name__)


class LockService:
    """Service for managing project locks."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = ProjectLockRepository(session)
        self.settings = get_settings()

    async def acquire_lock(
        self,
        project_path: str,
        session_id: uuid.UUID,
        timeout_seconds: int | None = None,
    ) -> ProjectLock | None:
        """Acquire a lock on a project. Returns None if already locked."""
        # Check for existing lock
        existing = await self.repository.get_by_project(project_path)

        if existing:
            # Check if expired
            if existing.expires_at < datetime.utcnow():
                await self.repository.delete(existing.id)
            else:
                logger.warning(
                    "lock_acquisition_failed",
                    project_path=project_path,
                    existing_session=str(existing.session_id),
                )
                return None

        # Calculate expiration
        timeout = timeout_seconds or self.settings.project_lock_timeout_seconds
        expires_at = datetime.utcnow() + timedelta(seconds=timeout)

        # Create lock
        lock = await self.repository.create(
            project_path=project_path,
            session_id=session_id,
            acquired_at=datetime.utcnow(),
            expires_at=expires_at,
        )

        logger.info(
            "lock_acquired",
            project_path=project_path,
            session_id=str(session_id),
            expires_at=expires_at.isoformat(),
        )

        return lock

    async def release_lock(self, project_path: str) -> bool:
        """Release a lock on a project."""
        lock = await self.repository.get_by_project(project_path)

        if lock:
            await self.repository.delete(lock.id)
            logger.info("lock_released", project_path=project_path)
            return True

        return False

    async def is_locked(self, project_path: str) -> bool:
        """Check if a project is currently locked."""
        lock = await self.repository.get_by_project(project_path)

        return bool(lock and lock.expires_at > datetime.utcnow())

    async def cleanup_expired(self) -> int:
        """Clean up expired locks."""
        count = await self.repository.cleanup_expired()

        if count > 0:
            logger.info("expired_locks_cleaned", count=count)

        return count
