"""Repository pattern for database operations."""

import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.base import Base
from src.db.models import Artifact, Event, ProjectLock, Session, Step

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Base repository with common CRUD operations."""

    def __init__(self, session: AsyncSession, model: type[T]):
        self.session = session
        self.model = model

    async def create(self, **kwargs: Any) -> T:
        """Create a new entity."""
        entity = self.model(**kwargs)
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get(self, id: uuid.UUID) -> T | None:
        """Get entity by ID."""
        return await self.session.get(self.model, id)

    async def get_all(self) -> list[T]:
        """Get all entities."""
        result = await self.session.execute(select(self.model))
        return list(result.scalars().all())

    async def update(self, id: uuid.UUID, **kwargs: Any) -> T | None:
        """Update entity by ID."""
        entity = await self.get(id)
        if entity:
            for key, value in kwargs.items():
                setattr(entity, key, value)
            await self.session.flush()
        return entity

    async def delete(self, id: uuid.UUID) -> bool:
        """Delete entity by ID."""
        entity = await self.get(id)
        if entity:
            await self.session.delete(entity)
            await self.session.flush()
            return True
        return False


class SessionRepository(BaseRepository[Session]):
    """Repository for Session operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Session)

    async def get_by_status(self, status: str) -> list[Session]:
        """Get sessions by status."""
        result = await self.session.execute(select(Session).where(Session.status == status))
        return list(result.scalars().all())

    async def get_by_project(self, project_path: str) -> list[Session]:
        """Get sessions by project path."""
        result = await self.session.execute(
            select(Session).where(Session.project_path == project_path)
        )
        return list(result.scalars().all())


class StepRepository(BaseRepository[Step]):
    """Repository for Step operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Step)

    async def get_by_session(self, session_id: uuid.UUID) -> list[Step]:
        """Get steps by session ID ordered by sequence."""
        result = await self.session.execute(
            select(Step).where(Step.session_id == session_id).order_by(Step.sequence)
        )
        return list(result.scalars().all())


class EventRepository(BaseRepository[Event]):
    """Repository for Event operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Event)

    async def get_by_session(self, session_id: uuid.UUID) -> list[Event]:
        """Get events by session ID ordered by timestamp."""
        result = await self.session.execute(
            select(Event).where(Event.session_id == session_id).order_by(Event.timestamp)
        )
        return list(result.scalars().all())


class ArtifactRepository(BaseRepository[Artifact]):
    """Repository for Artifact operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Artifact)

    async def get_by_session(self, session_id: uuid.UUID) -> list[Artifact]:
        """Get artifacts by session ID."""
        result = await self.session.execute(
            select(Artifact).where(Artifact.session_id == session_id)
        )
        return list(result.scalars().all())


class ProjectLockRepository(BaseRepository[ProjectLock]):
    """Repository for ProjectLock operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ProjectLock)

    async def get_by_project(self, project_path: str) -> ProjectLock | None:
        """Get lock by project path."""
        result = await self.session.execute(
            select(ProjectLock).where(ProjectLock.project_path == project_path)
        )
        return result.scalar_one_or_none()

    async def cleanup_expired(self) -> int:
        """Delete expired locks and return count."""
        result = await self.session.execute(
            select(ProjectLock).where(ProjectLock.expires_at < datetime.utcnow())
        )
        expired = list(result.scalars().all())
        for lock in expired:
            await self.session.delete(lock)
        await self.session.flush()
        return len(expired)
