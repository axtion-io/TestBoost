# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Session management service for workflow tracking."""

import uuid
from datetime import datetime
from pathlib import Path
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


# Workflow step definitions for each session type
# Each step has: code, name, description, auto_advance
# auto_advance: If True, automatically execute the next step when this one completes
#   - Analysis steps (read-only, no modifications) -> auto_advance=True
#   - Action steps (generate/modify files) -> auto_advance=False (user review needed)
#   - Validation steps (final) -> auto_advance=False (no next step or needs review)
WORKFLOW_STEPS: dict[str, list[dict[str, str | bool]]] = {
    "maven_maintenance": [
        {
            "code": "analyze_dependencies",
            "name": "Analyze Dependencies",
            "description": "Analyze project dependencies for outdated packages",
            "auto_advance": True,  # Analysis only, no modifications
        },
        {
            "code": "identify_vulnerabilities",
            "name": "Identify Vulnerabilities",
            "description": "Scan for security vulnerabilities in dependencies",
            "auto_advance": True,  # Analysis only, no modifications
        },
        {
            "code": "plan_updates",
            "name": "Plan Updates",
            "description": "Create update plan with prioritized changes",
            "auto_advance": False,  # User should review the plan before applying
        },
        {
            "code": "apply_updates",
            "name": "Apply Updates",
            "description": "Apply dependency updates to project",
            "auto_advance": False,  # Modifies files, user should review
        },
        {
            "code": "validate_changes",
            "name": "Validate Changes",
            "description": "Run tests to validate changes",
            "auto_advance": False,  # Final step
        },
    ],
    "test_generation": [
        {
            "code": "analyze_project",
            "name": "Analyze Project",
            "description": "Analyze project structure and existing tests",
            "auto_advance": True,  # Analysis only, no modifications
        },
        {
            "code": "identify_coverage_gaps",
            "name": "Identify Coverage Gaps",
            "description": "Identify areas lacking test coverage",
            "auto_advance": True,  # Analysis only, no modifications
        },
        {
            "code": "generate_tests",
            "name": "Generate Tests",
            "description": "Generate test cases for identified gaps",
            "auto_advance": False,  # Generates files, user should review
        },
        {
            "code": "validate_tests",
            "name": "Validate Tests",
            "description": "Run and validate generated tests",
            "auto_advance": False,  # Final step
        },
    ],
    "docker_deployment": [
        {
            "code": "analyze_dockerfile",
            "name": "Analyze Dockerfile",
            "description": "Analyze existing Dockerfile and configuration",
            "auto_advance": True,  # Analysis only, no modifications
        },
        {
            "code": "optimize_image",
            "name": "Optimize Image",
            "description": "Optimize Docker image size and layers",
            "auto_advance": False,  # Modifies Dockerfile, user should review
        },
        {
            "code": "generate_compose",
            "name": "Generate Compose",
            "description": "Generate or update docker-compose configuration",
            "auto_advance": False,  # Generates files, user should review
        },
        {
            "code": "validate_deployment",
            "name": "Validate Deployment",
            "description": "Validate deployment configuration",
            "auto_advance": False,  # Final step
        },
    ],
}


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

        # Initialize workflow steps for this session type
        await self._initialize_workflow_steps(session.id, session_type)

        return session

    async def _initialize_workflow_steps(
        self,
        session_id: uuid.UUID,
        session_type: str,
    ) -> list[Step]:
        """
        Initialize workflow steps for a session based on its type.

        Args:
            session_id: Session UUID
            session_type: Type of session (maven_maintenance, test_generation, docker_deployment)

        Returns:
            List of created steps
        """
        step_definitions = WORKFLOW_STEPS.get(session_type, [])

        if not step_definitions:
            logger.warning(
                "no_workflow_steps_defined",
                session_id=str(session_id),
                session_type=session_type,
            )
            return []

        created_steps: list[Step] = []
        for sequence, step_def in enumerate(step_definitions, start=1):
            step = await self.create_step(
                session_id=session_id,
                code=str(step_def["code"]),
                name=str(step_def["name"]),
                sequence=sequence,
                inputs={"description": str(step_def.get("description", ""))},
            )
            created_steps.append(step)

        logger.info(
            "workflow_steps_initialized",
            session_id=str(session_id),
            session_type=session_type,
            step_count=len(created_steps),
        )

        return created_steps

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
        **kwargs: Any,
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

    async def get_steps(
        self,
        session_id: uuid.UUID,
        status: str | None = None,
    ) -> list[Step]:
        """Get all steps for a session ordered by sequence.

        Args:
            session_id: Session UUID
            status: Optional filter by status (e.g., "completed", "pending")

        Returns:
            List of steps matching the filters
        """
        if status is not None:
            result = await self.db_session.execute(
                select(Step)
                .where(
                    and_(
                        Step.session_id == session_id,
                        Step.status == status,
                    )
                )
                .order_by(Step.sequence)
            )
            return list(result.scalars().all())

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

    def _infer_content_type(self, file_format: str) -> str:
        """
        Infer MIME content type from file format.

        Args:
            file_format: File format type (json, yaml, xml, java, py, txt, etc.)

        Returns:
            MIME type string

        Example:
            >>> service._infer_content_type("json")
            "application/json"
            >>> service._infer_content_type("java")
            "text/x-java"
        """
        # Map file_format to MIME type
        format_to_mime = {
            # Data formats
            "json": "application/json",
            "yaml": "application/x-yaml",
            "yml": "application/x-yaml",
            "xml": "application/xml",
            "csv": "text/csv",
            "toml": "application/toml",
            # Programming languages
            "java": "text/x-java",
            "py": "text/x-python",
            "python": "text/x-python",
            "js": "text/javascript",
            "javascript": "text/javascript",
            "ts": "text/typescript",
            "typescript": "text/typescript",
            "go": "text/x-go",
            "rs": "text/x-rust",
            "rust": "text/x-rust",
            "c": "text/x-c",
            "cpp": "text/x-c++",
            "h": "text/x-c-header",
            # Markup & documentation
            "html": "text/html",
            "md": "text/markdown",
            "markdown": "text/markdown",
            "txt": "text/plain",
            "log": "text/plain",
            # Configuration
            "properties": "text/x-java-properties",
            "conf": "text/plain",
            "cfg": "text/plain",
            "ini": "text/plain",
            # Shell scripts
            "sh": "application/x-sh",
            "bash": "application/x-sh",
            "bat": "application/x-bat",
            "ps1": "application/x-powershell",
        }

        return format_to_mime.get(file_format.lower(), "application/octet-stream")

    async def get_artifact(
        self,
        session_id: uuid.UUID,
        artifact_id: uuid.UUID,
    ) -> Artifact | None:
        """
        Get a single artifact by session ID and artifact ID.

        Args:
            session_id: Session UUID
            artifact_id: Artifact UUID

        Returns:
            Artifact or None if not found
        """
        result = await self.db_session.execute(
            select(Artifact).where(
                and_(
                    Artifact.session_id == session_id,
                    Artifact.id == artifact_id,
                )
            )
        )
        return result.scalar_one_or_none()

    async def get_artifacts(
        self,
        session_id: uuid.UUID,
        artifact_type: str | None = None,
        file_format: str | None = None,
    ) -> list[Artifact]:
        """
        Get artifacts for a session.

        Args:
            session_id: Session UUID
            artifact_type: Filter by artifact type
            file_format: Filter by file format (json, yaml, xml, md, etc.)

        Returns:
            List of artifacts matching the filters
        """
        # Use the repository method that supports multiple filters
        return await self.artifact_repo.get_artifacts(
            session_id=session_id,
            artifact_type=artifact_type,
            file_format=file_format,
        )

    async def get_step_artifacts(
        self,
        session_id: uuid.UUID,
        step_code: str,
        artifact_type: str | None = None,
        file_format: str | None = None,
    ) -> list[Artifact]:
        """
        Get artifacts for a specific step.

        Args:
            session_id: Session UUID
            step_code: Step code (e.g., "analyze_project", "identify_coverage_gaps")
            artifact_type: Filter by artifact type (optional)
            file_format: Filter by file format (optional)

        Returns:
            List of artifacts matching the filters for the specified step
        """
        return await self.artifact_repo.get_step_artifacts(
            session_id=session_id,
            step_code=step_code,
            artifact_type=artifact_type,
            file_format=file_format,
        )

    async def create_artifact(
        self,
        session_id: uuid.UUID,
        name: str,
        artifact_type: str,
        content: str | bytes,
        file_path: str,
        file_format: str = "json",
        content_type: str | None = None,
        artifact_metadata: dict[str, Any] | None = None,
        step_id: uuid.UUID | None = None,
    ) -> Artifact:
        """
        Create an artifact with content stored on disk.

        CRITICAL: This method writes content to disk BEFORE creating database record.

        Args:
            session_id: Session UUID
            name: Artifact name
            artifact_type: Type of artifact
            content: Artifact content to write to disk (str for text, bytes for binary)
            file_path: Path where content will be stored
            file_format: File format (json, yaml, xml, java, py, txt, etc.)
            content_type: MIME type (if None, inferred from file_format)
            artifact_metadata: Optional artifact metadata
            step_id: Optional step UUID

        Returns:
            Created artifact

        Raises:
            Exception: If file write fails (permission denied, disk full, I/O error)
        """
        # 1. Write file to disk FIRST (FR-025, FR-027)
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        try:
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content, encoding="utf-8")  # FR-028
        except (PermissionError, OSError, IOError) as e:
            logger.error(
                "artifact_write_failed",
                file_path=file_path,
                error=str(e),
                session_id=str(session_id),
            )
            raise Exception(f"Failed to write artifact to disk: {str(e)}") from e

        # 2. Calculate size from actual file (FR-030)
        size_bytes = path.stat().st_size

        # 3. Infer content_type if not provided
        if content_type is None:
            content_type = self._infer_content_type(file_format)

        # 4. Create database record AFTER file exists (FR-029)
        artifact = await self.artifact_repo.create(
            session_id=session_id,
            step_id=step_id,
            name=name,
            artifact_type=artifact_type,
            content_type=content_type,
            file_path=file_path,
            size_bytes=size_bytes,
            artifact_metadata=artifact_metadata,
            file_format=file_format,
        )

        await self.emit_event(
            session_id=session_id,
            step_id=step_id,
            event_type="artifact_created",
            event_data={
                "artifact_id": str(artifact.id),
                "name": name,
                "type": artifact_type,
                "file_format": file_format,
                "size_bytes": size_bytes,
            },
            message=f"Artifact '{name}' created",
        )

        logger.info(
            "artifact_created",
            artifact_id=str(artifact.id),
            file_path=file_path,
            size_bytes=size_bytes,
            file_format=file_format,
        )

        return artifact

    async def create_file_modification_artifact(
        self,
        session_id: uuid.UUID,
        file_path: str,
        operation: str,
        original_content: str | None,
        modified_content: str | None,
        step_id: uuid.UUID | None = None,
        content_type: str = "text/plain",
    ) -> Artifact:
        """
        Create a file_modification artifact with diff.

        Args:
            session_id: Session UUID
            file_path: Path to the modified file (relative to project root)
            operation: Operation type: 'create', 'modify', or 'delete'
            original_content: Original file content (None for create)
            modified_content: Modified file content (None for delete)
            step_id: Optional step UUID
            content_type: MIME type of the file

        Returns:
            Created file_modification artifact
        """
        from src.lib.diff import generate_unified_diff

        # Generate unified diff
        diff = generate_unified_diff(original_content, modified_content, file_path)

        # Build metadata
        metadata = {
            "file_path": file_path,
            "operation": operation,
            "original_content": original_content,
            "modified_content": modified_content,
            "diff": diff,
        }

        # Determine content to store (modified for create/modify, original for delete)
        content = modified_content if operation != "delete" else original_content
        if content is None:
            content = ""

        # Infer file format from extension
        file_extension = Path(file_path).suffix.lstrip(".")
        file_format = file_extension if file_extension else "txt"

        # Determine artifact storage path (different from project file path)
        artifact_file_path = f"artifacts/{session_id}/modifications/{file_path}"

        return await self.create_artifact(
            session_id=session_id,
            step_id=step_id,
            name=file_path,
            artifact_type="file_modification",
            content=content,
            file_path=artifact_file_path,
            file_format=file_format,
            content_type=content_type,
            artifact_metadata=metadata,
        )


__all__ = [
    "SessionService",
    "WORKFLOW_STEPS",
    "get_active_session_for_project",
    "set_active_session_for_project",
    "invalidate_project_cache",
    "clear_project_cache",
    "get_all_cached_projects",
]
