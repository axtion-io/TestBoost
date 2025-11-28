"""Session management service for workflow tracking."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import Artifact, Event, Session, Step
from src.db.models.session import SessionMode, SessionStatus
from src.db.models.step import StepStatus
from src.db.repository import ArtifactRepository, EventRepository, SessionRepository, StepRepository
from src.lib.logging import get_logger

logger = get_logger(__name__)


# Project cache for tracking active sessions per project
_project_cache: dict[str, uuid.UUID] = {}


def get_active_session_for_project(project_path: str) -> uuid.UUID | None:
    """
    Get the active session ID for a project from cache.

    Args:
        project_path: Path to the project

    Returns:
        Session UUID if active session exists, None otherwise
    """
    return _project_cache.get(project_path)


def set_active_session_for_project(project_path: str, session_id: uuid.UUID) -> None:
    """
    Set the active session for a project in cache.

    Args:
        project_path: Path to the project
        session_id: Session UUID
    """
    _project_cache[project_path] = session_id
    logger.debug(
        "project_cache_set",
        project_path=project_path,
        session_id=str(session_id),
    )


def invalidate_project_cache(project_path: str) -> bool:
    """
    Invalidate the cache entry for a project.

    Args:
        project_path: Path to the project

    Returns:
        True if cache entry was removed, False if not found
    """
    if project_path in _project_cache:
        session_id = _project_cache.pop(project_path)
        logger.info(
            "project_cache_invalidated",
            project_path=project_path,
            session_id=str(session_id),
        )
        return True
    return False


def clear_project_cache() -> int:
    """
    Clear all project cache entries.

    Returns:
        Number of entries cleared
    """
    count = len(_project_cache)
    _project_cache.clear()
    logger.info("project_cache_cleared", entries_cleared=count)
    return count


def get_all_cached_projects() -> dict[str, uuid.UUID]:
    """
    Get all cached project-session mappings.

    Returns:
        Dictionary of project_path to session_id mappings
    """
    return _project_cache.copy()


class SessionService:
    """Service for managing workflow sessions."""

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.session_repo = SessionRepository(db_session)
        self.step_repo = StepRepository(db_session)
        self.event_repo = EventRepository(db_session)
        self.artifact_repo = ArtifactRepository(db_session)

    # Session CRUD Operations (T116)

    async def create_session(
        self,
        session_type: str,
        project_path: str,
        mode: str = SessionMode.INTERACTIVE.value,
        config: dict[str, Any] | None = None,
    ) -> Session:
        """
        Create a new workflow session.

        Args:
            session_type: Type of session (maven_maintenance, test_generation, docker_deployment)
            project_path: Path to the project directory
            mode: Execution mode (interactive, autonomous, analysis_only)
            config: Session configuration

        Returns:
            Created session
        """
        session = await self.session_repo.create(
            session_type=session_type,
            project_path=project_path,
            mode=mode,
            config=config or {},
            status=SessionStatus.PENDING.value,
        )

        logger.info(
            "session_created",
            session_id=str(session.id),
            session_type=session_type,
            project_path=project_path,
            mode=mode,
        )

        # Set project cache for active session tracking
        set_active_session_for_project(project_path, session.id)

        # Emit session created event
        await self.event_repo.create(
            session_id=session.id,
            event_type="session_created",
            event_data={"session_type": session_type, "mode": mode},
            message=f"Session created for {project_path}",
            timestamp=datetime.utcnow(),
        )

        return session

    async def get_session(self, session_id: uuid.UUID) -> Session | None:
        """
        Get a session by ID with all relationships loaded.

        Args:
            session_id: Session UUID

        Returns:
            Session or None if not found
        """
        result = await self.db_session.execute(
            select(Session)
            .options(
                selectinload(Session.steps),
                selectinload(Session.events),
                selectinload(Session.artifacts),
            )
            .where(Session.id == session_id)
        )
        return result.scalar_one_or_none()

    async def update_session(
        self,
        session_id: uuid.UUID,
        **kwargs,
    ) -> Session | None:
        """
        Update a session.

        Args:
            session_id: Session UUID
            **kwargs: Fields to update

        Returns:
            Updated session or None if not found
        """
        session = await self.session_repo.update(session_id, **kwargs)

        if session:
            logger.info(
                "session_updated",
                session_id=str(session_id),
                updated_fields=list(kwargs.keys()),
            )

        return session

    async def delete_session(self, session_id: uuid.UUID) -> bool:
        """
        Delete a session and all related data.

        Args:
            session_id: Session UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.session_repo.delete(session_id)

        if result:
            logger.info("session_deleted", session_id=str(session_id))

        return result

    # Real-time Status Updates (T117)

    async def update_status(
        self,
        session_id: uuid.UUID,
        status: str,
        error_message: str | None = None,
        result: dict[str, Any] | None = None,
    ) -> Session | None:
        """
        Update session status with real-time tracking.

        Args:
            session_id: Session UUID
            status: New status
            error_message: Optional error message
            result: Optional result data

        Returns:
            Updated session
        """
        update_data: dict[str, Any] = {
            "status": status,
            "updated_at": datetime.utcnow(),
        }

        if error_message is not None:
            update_data["error_message"] = error_message

        if result is not None:
            update_data["result"] = result

        if status in [
            SessionStatus.COMPLETED.value,
            SessionStatus.FAILED.value,
            SessionStatus.CANCELLED.value,
        ]:
            update_data["completed_at"] = datetime.utcnow()

        session = await self.session_repo.update(session_id, **update_data)

        if session:
            # Emit status change event
            await self.event_repo.create(
                session_id=session_id,
                event_type="status_changed",
                event_data={"old_status": session.status, "new_status": status},
                message=f"Status changed to {status}",
                timestamp=datetime.utcnow(),
            )

            # Invalidate project cache on terminal states
            if status in [
                SessionStatus.COMPLETED.value,
                SessionStatus.FAILED.value,
                SessionStatus.CANCELLED.value,
            ]:
                invalidate_project_cache(session.project_path)

            logger.info(
                "session_status_updated",
                session_id=str(session_id),
                status=status,
            )

        return session

    async def start_session(self, session_id: uuid.UUID) -> Session | None:
        """Start a pending session."""
        return await self.update_status(session_id, SessionStatus.IN_PROGRESS.value)

    async def pause_session(self, session_id: uuid.UUID) -> Session | None:
        """Pause an in-progress session."""
        return await self.update_status(session_id, SessionStatus.PAUSED.value)

    async def resume_session(self, session_id: uuid.UUID) -> Session | None:
        """Resume a paused session."""
        return await self.update_status(session_id, SessionStatus.IN_PROGRESS.value)

    async def complete_session(
        self,
        session_id: uuid.UUID,
        result: dict[str, Any] | None = None,
    ) -> Session | None:
        """Mark session as completed."""
        return await self.update_status(
            session_id,
            SessionStatus.COMPLETED.value,
            result=result,
        )

    async def fail_session(
        self,
        session_id: uuid.UUID,
        error_message: str,
    ) -> Session | None:
        """Mark session as failed."""
        return await self.update_status(
            session_id,
            SessionStatus.FAILED.value,
            error_message=error_message,
        )

    async def cancel_session(self, session_id: uuid.UUID) -> Session | None:
        """Cancel a session."""
        return await self.update_status(session_id, SessionStatus.CANCELLED.value)

    # Session History with Filters (T118)

    async def list_sessions(
        self,
        status: str | None = None,
        session_type: str | None = None,
        project_path: str | None = None,
        created_after: datetime | None = None,
        created_before: datetime | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[Session], int]:
        """
        List sessions with filters and pagination.

        Args:
            status: Filter by status
            session_type: Filter by session type
            project_path: Filter by project path (partial match)
            created_after: Filter by creation date
            created_before: Filter by creation date
            page: Page number (1-indexed)
            per_page: Items per page

        Returns:
            Tuple of (sessions list, total count)
        """
        # Build filter conditions
        conditions = []

        if status:
            conditions.append(Session.status == status)

        if session_type:
            conditions.append(Session.session_type == session_type)

        if project_path:
            conditions.append(Session.project_path.ilike(f"%{project_path}%"))

        if created_after:
            conditions.append(Session.created_at >= created_after)

        if created_before:
            conditions.append(Session.created_at <= created_before)

        # Build query
        query = select(Session)
        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(Session.id)
        if conditions:
            count_query = count_query.where(and_(*conditions))
        count_result = await self.db_session.execute(count_query)
        total = len(count_result.all())

        # Apply pagination and ordering
        offset = (page - 1) * per_page
        query = query.order_by(desc(Session.created_at)).offset(offset).limit(per_page)

        result = await self.db_session.execute(query)
        sessions = list(result.scalars().all())

        return sessions, total

    async def get_session_history(
        self,
        project_path: str,
        limit: int = 10,
    ) -> list[Session]:
        """
        Get session history for a specific project.

        Args:
            project_path: Project path
            limit: Maximum number of sessions to return

        Returns:
            List of sessions ordered by creation date descending
        """
        result = await self.db_session.execute(
            select(Session)
            .where(Session.project_path == project_path)
            .order_by(desc(Session.created_at))
            .limit(limit)
        )
        return list(result.scalars().all())

    # Audit Trail Queries (T119)

    async def get_audit_trail(
        self,
        session_id: uuid.UUID,
        event_type: str | None = None,
        since: datetime | None = None,
    ) -> list[Event]:
        """
        Get audit trail events for a session.

        Args:
            session_id: Session UUID
            event_type: Filter by event type
            since: Filter events after this timestamp

        Returns:
            List of events ordered by timestamp
        """
        conditions = [Event.session_id == session_id]

        if event_type:
            conditions.append(Event.event_type == event_type)

        if since:
            conditions.append(Event.timestamp >= since)

        result = await self.db_session.execute(
            select(Event).where(and_(*conditions)).order_by(Event.timestamp)
        )
        return list(result.scalars().all())

    async def get_session_events(self, session_id: uuid.UUID) -> list[Event]:
        """Get all events for a session."""
        return await self.event_repo.get_by_session(session_id)

    async def emit_event(
        self,
        session_id: uuid.UUID,
        event_type: str,
        event_data: dict[str, Any] | None = None,
        step_id: uuid.UUID | None = None,
        message: str | None = None,
    ) -> Event:
        """
        Emit an event for a session.

        Args:
            session_id: Session UUID
            event_type: Type of event
            event_data: Event payload
            step_id: Optional step UUID
            message: Optional message

        Returns:
            Created event
        """
        event = await self.event_repo.create(
            session_id=session_id,
            step_id=step_id,
            event_type=event_type,
            event_data=event_data or {},
            message=message,
            timestamp=datetime.utcnow(),
        )

        logger.debug(
            "event_emitted",
            session_id=str(session_id),
            event_type=event_type,
            step_id=str(step_id) if step_id else None,
        )

        return event

    # Step Management

    async def get_steps(self, session_id: uuid.UUID) -> list[Step]:
        """Get all steps for a session ordered by sequence."""
        return await self.step_repo.get_by_session(session_id)

    async def get_step_by_code(
        self,
        session_id: uuid.UUID,
        step_code: str,
    ) -> Step | None:
        """
        Get a specific step by its code.

        Args:
            session_id: Session UUID
            step_code: Step code identifier

        Returns:
            Step or None if not found
        """
        result = await self.db_session.execute(
            select(Step).where(
                and_(
                    Step.session_id == session_id,
                    Step.code == step_code,
                )
            )
        )
        return result.scalar_one_or_none()

    async def create_step(
        self,
        session_id: uuid.UUID,
        code: str,
        name: str,
        sequence: int,
        inputs: dict[str, Any] | None = None,
    ) -> Step:
        """
        Create a new step for a session.

        Args:
            session_id: Session UUID
            code: Step code identifier
            name: Step display name
            sequence: Step order
            inputs: Step input data

        Returns:
            Created step
        """
        step = await self.step_repo.create(
            session_id=session_id,
            code=code,
            name=name,
            sequence=sequence,
            inputs=inputs or {},
            status=StepStatus.PENDING.value,
        )

        await self.emit_event(
            session_id=session_id,
            step_id=step.id,
            event_type="step_created",
            event_data={"code": code, "name": name, "sequence": sequence},
            message=f"Step '{name}' created",
        )

        return step

    async def update_step_status(
        self,
        step_id: uuid.UUID,
        status: str,
        outputs: dict[str, Any] | None = None,
        error_message: str | None = None,
    ) -> Step | None:
        """
        Update step status.

        Args:
            step_id: Step UUID
            status: New status
            outputs: Step output data
            error_message: Error message if failed

        Returns:
            Updated step
        """
        update_data: dict[str, Any] = {"status": status}

        if status == StepStatus.IN_PROGRESS.value:
            update_data["started_at"] = datetime.utcnow()
        elif status in [
            StepStatus.COMPLETED.value,
            StepStatus.FAILED.value,
            StepStatus.SKIPPED.value,
        ]:
            update_data["completed_at"] = datetime.utcnow()

        if outputs is not None:
            update_data["outputs"] = outputs

        if error_message is not None:
            update_data["error_message"] = error_message

        step = await self.step_repo.update(step_id, **update_data)

        if step:
            await self.emit_event(
                session_id=step.session_id,
                step_id=step_id,
                event_type="step_status_changed",
                event_data={"status": status, "code": step.code},
                message=f"Step '{step.name}' status changed to {status}",
            )

        return step

    async def execute_step(
        self,
        session_id: uuid.UUID,
        step_code: str,
    ) -> Step | None:
        """
        Execute a step (mark as in progress).

        Args:
            session_id: Session UUID
            step_code: Step code identifier

        Returns:
            Updated step or None if not found
        """
        step = await self.get_step_by_code(session_id, step_code)
        if step:
            return await self.update_step_status(step.id, StepStatus.IN_PROGRESS.value)
        return None

    # Artifact Management

    async def get_artifacts(
        self,
        session_id: uuid.UUID,
        artifact_type: str | None = None,
    ) -> list[Artifact]:
        """
        Get artifacts for a session.

        Args:
            session_id: Session UUID
            artifact_type: Filter by artifact type

        Returns:
            List of artifacts
        """
        if artifact_type:
            result = await self.db_session.execute(
                select(Artifact).where(
                    and_(
                        Artifact.session_id == session_id,
                        Artifact.artifact_type == artifact_type,
                    )
                )
            )
            return list(result.scalars().all())

        return await self.artifact_repo.get_by_session(session_id)

    async def create_artifact(
        self,
        session_id: uuid.UUID,
        name: str,
        artifact_type: str,
        content_type: str,
        file_path: str,
        size_bytes: int = 0,
        step_id: uuid.UUID | None = None,
    ) -> Artifact:
        """
        Create an artifact for a session.

        Args:
            session_id: Session UUID
            name: Artifact name
            artifact_type: Type of artifact
            content_type: MIME type
            file_path: Path to the artifact file
            size_bytes: File size in bytes
            step_id: Optional step UUID

        Returns:
            Created artifact
        """
        artifact = await self.artifact_repo.create(
            session_id=session_id,
            step_id=step_id,
            name=name,
            artifact_type=artifact_type,
            content_type=content_type,
            file_path=file_path,
            size_bytes=size_bytes,
        )

        await self.emit_event(
            session_id=session_id,
            step_id=step_id,
            event_type="artifact_created",
            event_data={
                "artifact_id": str(artifact.id),
                "name": name,
                "type": artifact_type,
            },
            message=f"Artifact '{name}' created",
        )

        return artifact


__all__ = [
    "SessionService",
    "get_active_session_for_project",
    "set_active_session_for_project",
    "invalidate_project_cache",
    "clear_project_cache",
    "get_all_cached_projects",
]
