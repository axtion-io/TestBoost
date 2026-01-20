"""Sessions API router for workflow tracking."""

import uuid
from datetime import datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models.pagination import (
    PaginationMeta,
    create_pagination_meta,
)
from src.core.session import SessionService
from src.db import get_db
from src.db.models.session import SessionMode, SessionStatus, SessionType
from src.db.models.step import StepStatus
from src.lib.diff import is_binary_content
from src.lib.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/sessions", tags=["sessions"])


# Helper functions


def log_and_raise_http_error(
    status_code: int,
    detail: str,
    *,
    event: str,
    request_id: str = "unknown",
    **context: Any,
) -> NoReturn:
    """
    Log an error event and raise an HTTPException.

    This helper ensures all HTTP errors are logged with context before being raised,
    making debugging and monitoring much easier.

    Args:
        status_code: HTTP status code
        detail: Human-readable error message
        event: Event name for structured logging
        request_id: Request ID for tracing
        **context: Additional context fields for logging

    Raises:
        HTTPException: Always raises after logging
    """
    # Determine log level based on status code
    if status_code >= 500:
        log_level = logger.error
    elif status_code == 404:
        log_level = logger.warning
    else:
        log_level = logger.info

    # Log with context
    log_level(
        event,
        request_id=request_id,
        status_code=status_code,
        detail=detail,
        **context,
    )

    # Raise exception
    raise HTTPException(status_code=status_code, detail=detail)


# Request/Response Models


class SessionCreateRequest(BaseModel):
    """Request model for creating a session."""

    session_type: str = Field(
        ...,
        description="Type of session (maven_maintenance, test_generation, docker_deployment)",
    )
    project_path: str = Field(..., description="Path to the project directory")
    mode: str = Field(
        default="interactive",
        description="Execution mode (interactive, autonomous, analysis_only)",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Session configuration",
    )


class SessionUpdateRequest(BaseModel):
    """Request model for updating a session."""

    status: str | None = Field(None, description="New status")
    config: dict[str, Any] | None = Field(None, description="Updated configuration")
    result: dict[str, Any] | None = Field(None, description="Session result")
    error_message: str | None = Field(None, description="Error message")


class SessionResponse(BaseModel):
    """Response model for a session."""

    id: uuid.UUID
    session_type: str
    status: str
    mode: str
    project_path: str
    config: dict[str, Any]
    result: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class SessionListResponse(BaseModel):
    """Response model for session list."""

    items: list[SessionResponse]
    pagination: PaginationMeta


class StepResponse(BaseModel):
    """Response model for a step."""

    id: uuid.UUID
    session_id: uuid.UUID
    code: str
    name: str
    status: str
    sequence: int
    inputs: dict[str, Any]
    outputs: dict[str, Any] | None = None
    error_message: str | None = None
    retry_count: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class StepListResponse(BaseModel):
    """Response model for step list."""

    items: list[StepResponse]
    total: int


class StepExecuteRequest(BaseModel):
    """Request model for executing a step."""

    inputs: dict[str, Any] = Field(
        default_factory=dict,
        description="Input data for step execution",
    )
    run_workflow: bool = Field(
        default=True,
        description="If True, execute the actual workflow step. If False, just mark as in_progress.",
    )
    run_in_background: bool = Field(
        default=True,
        description="If True and run_workflow=True, run workflow in background task.",
    )


class StepUpdateRequest(BaseModel):
    """Request model for updating a step."""

    status: str = Field(
        ...,
        description="New status (completed, failed, skipped)",
    )
    outputs: dict[str, Any] | None = Field(
        None,
        description="Step output data (for completed status)",
    )
    error_message: str | None = Field(
        None,
        description="Error message (for failed status)",
    )


class StepExecuteResponse(BaseModel):
    """Response model for step execution."""

    id: uuid.UUID
    code: str
    name: str
    status: str
    message: str


class FileModificationMetadata(BaseModel):
    """Metadata for file_modification artifact type."""

    file_path: str = Field(..., description="Path to the modified file (relative to project root)")
    operation: str = Field(..., description="Operation type: create, modify, or delete")
    original_content: str | None = Field(None, description="Original file content (null for create)")
    modified_content: str | None = Field(None, description="Modified file content (null for delete)")
    diff: str = Field(..., description="Unified diff format showing changes")


class ArtifactResponse(BaseModel):
    """Response model for an artifact."""

    id: uuid.UUID
    session_id: uuid.UUID
    step_id: uuid.UUID | None = None
    name: str
    artifact_type: str
    content_type: str
    file_path: str
    size_bytes: int
    created_at: datetime
    # Use validation_alias to map from artifact_metadata (SQLAlchemy) to metadata (API)
    metadata: dict[str, Any] | None = Field(
        None,
        validation_alias="artifact_metadata",
        description="Type-specific metadata (present for file_modification type)",
    )

    model_config = {"from_attributes": True, "populate_by_name": True}


class ArtifactListResponse(BaseModel):
    """Response model for artifact list."""

    items: list[ArtifactResponse]
    total: int


# Endpoints


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: SessionCreateRequest,
    http_request: Request,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Create a new workflow session.

    Args:
        request: Session creation parameters
        http_request: FastAPI request (for request_id)

    Returns:
        Created session
    """
    request_id = getattr(http_request.state, "request_id", "unknown")

    # Validate session type
    valid_types = [t.value for t in SessionType]
    if request.session_type not in valid_types:
        log_and_raise_http_error(
            400,
            f"Invalid session_type. Must be one of: {', '.join(valid_types)}",
            event="invalid_session_type",
            request_id=request_id,
            provided_type=request.session_type,
            valid_types=valid_types,
        )

    # Validate mode
    valid_modes = [m.value for m in SessionMode]
    if request.mode not in valid_modes:
        log_and_raise_http_error(
            400,
            f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
            event="invalid_session_mode",
            request_id=request_id,
            provided_mode=request.mode,
            valid_modes=valid_modes,
        )

    service = SessionService(db)

    session = await service.create_session(
        session_type=request.session_type,
        project_path=request.project_path,
        mode=request.mode,
        config=request.config,
    )

    logger.info(
        "session_created_via_api",
        session_id=str(session.id),
        session_type=request.session_type,
    )

    return SessionResponse.model_validate(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(
    status: str | None = Query(None, description="Filter by status"),
    session_type: str | None = Query(None, description="Filter by session type"),
    project_path: str | None = Query(None, description="Filter by project path (partial match)"),
    created_after: datetime | None = Query(None, description="Filter by creation date (after)"),
    created_before: datetime | None = Query(None, description="Filter by creation date (before)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    db: AsyncSession = Depends(get_db),
) -> SessionListResponse:
    """
    List sessions with optional filters and pagination.

    Args:
        status: Filter by session status
        session_type: Filter by session type
        project_path: Filter by project path (partial match)
        created_after: Filter sessions created after this date
        created_before: Filter sessions created before this date
        page: Page number (1-indexed)
        per_page: Number of items per page

    Returns:
        Paginated list of sessions
    """
    service = SessionService(db)

    sessions, total = await service.list_sessions(
        status=status,
        session_type=session_type,
        project_path=project_path,
        created_after=created_after,
        created_before=created_before,
        page=page,
        per_page=per_page,
    )

    return SessionListResponse(
        items=[SessionResponse.model_validate(s) for s in sessions],
        pagination=create_pagination_meta(page, per_page, total),
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Get a session by ID.

    Args:
        session_id: Session UUID

    Returns:
        Session details
    """
    service = SessionService(db)

    session = await service.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    return SessionResponse.model_validate(session)


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: uuid.UUID,
    request: SessionUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Update a session.

    Args:
        session_id: Session UUID
        request: Update parameters

    Returns:
        Updated session
    """
    service = SessionService(db)

    # Check session exists
    existing = await service.get_session(session_id)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    # Build update kwargs
    update_kwargs: dict[str, Any] = {}

    if request.status is not None:
        # Validate status
        valid_statuses = [s.value for s in SessionStatus]
        if request.status not in valid_statuses:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )
        update_kwargs["status"] = request.status

    if request.config is not None:
        update_kwargs["config"] = request.config

    if request.result is not None:
        update_kwargs["result"] = request.result

    if request.error_message is not None:
        update_kwargs["error_message"] = request.error_message

    if not update_kwargs:
        raise HTTPException(
            status_code=400,
            detail="No fields to update",
        )

    # Handle status-specific updates
    if request.status:
        session = await service.update_status(
            session_id,
            request.status,
            error_message=request.error_message,
            result=request.result,
        )
    else:
        session = await service.update_session(session_id, **update_kwargs)

    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    logger.info(
        "session_updated_via_api",
        session_id=str(session_id),
        updated_fields=list(update_kwargs.keys()),
    )

    # Refresh to get updated data
    session = await service.get_session(session_id)
    return SessionResponse.model_validate(session)


@router.delete("/{session_id}", status_code=204)
async def delete_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a session and all related data.

    Args:
        session_id: Session UUID
    """
    service = SessionService(db)

    result = await service.delete_session(session_id)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    logger.info("session_deleted_via_api", session_id=str(session_id))


@router.get("/{session_id}/steps", response_model=StepListResponse)
async def get_session_steps(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> StepListResponse:
    """
    Get all steps for a session.

    Args:
        session_id: Session UUID

    Returns:
        List of steps ordered by sequence
    """
    service = SessionService(db)

    # Check session exists
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    steps = await service.get_steps(session_id)

    return StepListResponse(
        items=[StepResponse.model_validate(s) for s in steps],
        total=len(steps),
    )


@router.get("/{session_id}/steps/{step_code}", response_model=StepResponse)
async def get_session_step(
    session_id: uuid.UUID,
    step_code: str,
    db: AsyncSession = Depends(get_db),
) -> StepResponse:
    """
    Get a specific step by code.

    Args:
        session_id: Session UUID
        step_code: Step code identifier

    Returns:
        Step details
    """
    service = SessionService(db)

    # Check session exists
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    step = await service.get_step_by_code(session_id, step_code)

    if not step:
        raise HTTPException(
            status_code=404,
            detail=f"Step not found: {step_code}",
        )

    return StepResponse.model_validate(step)


@router.post(
    "/{session_id}/steps/{step_code}/execute",
    response_model=StepExecuteResponse,
)
async def execute_session_step(
    session_id: uuid.UUID,
    step_code: str,
    request: StepExecuteRequest = StepExecuteRequest(),
    db: AsyncSession = Depends(get_db),
) -> StepExecuteResponse:
    """
    Execute a step.

    By default (run_workflow=False), just marks the step as in_progress.
    With run_workflow=True, actually executes the workflow step and updates
    status to completed/failed when done.

    Args:
        session_id: Session UUID
        step_code: Step code identifier
        request: Execution parameters

    Returns:
        Step execution status
    """
    service = SessionService(db)

    # Check session exists
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    # Check session status allows execution
    if session.status not in [SessionStatus.PENDING.value, SessionStatus.IN_PROGRESS.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute step: session status is {session.status}",
        )

    # Get step
    step = await service.get_step_by_code(session_id, step_code)

    if not step:
        raise HTTPException(
            status_code=404,
            detail=f"Step not found: {step_code}",
        )

    # Check step can be executed
    if step.status not in [StepStatus.PENDING.value, StepStatus.FAILED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute step: step status is {step.status}",
        )

    # Update step inputs if provided
    if request.inputs:
        await service.step_repo.update(step.id, inputs=request.inputs)

    if request.run_workflow:
        # Execute actual workflow step using StepExecutor
        from src.core.step_executor import StepExecutionError, StepExecutor

        executor = StepExecutor(db)

        try:
            await executor.execute_step(
                session_id=session_id,
                step_code=step_code,
                inputs=request.inputs,
                run_in_background=request.run_in_background,
            )

            # Refresh step to get updated status
            updated_step = await service.get_step_by_code(session_id, step_code)

            if not updated_step:
                raise HTTPException(status_code=500, detail="Step disappeared during execution")

            message = (
                f"Step '{updated_step.name}' started in background"
                if request.run_in_background
                else f"Step '{updated_step.name}' completed"
            )

            logger.info(
                "step_workflow_executed_via_api",
                session_id=str(session_id),
                step_code=step_code,
                run_in_background=request.run_in_background,
                status=updated_step.status,
            )

            return StepExecuteResponse(
                id=updated_step.id,
                code=updated_step.code,
                name=updated_step.name,
                status=updated_step.status,
                message=message,
            )

        except StepExecutionError as e:
            logger.error(
                "step_workflow_execution_failed",
                session_id=str(session_id),
                step_code=step_code,
                error=str(e),
            )
            raise HTTPException(
                status_code=500,
                detail=f"Step execution failed: {e}",
            ) from e
    else:
        # Just mark step as in progress (legacy behavior)
        updated_step = await service.execute_step(session_id, step_code)

        if not updated_step:
            raise HTTPException(
                status_code=500,
                detail="Failed to execute step",
            )

        logger.info(
            "step_marked_in_progress_via_api",
            session_id=str(session_id),
            step_code=step_code,
        )

        return StepExecuteResponse(
            id=updated_step.id,
            code=updated_step.code,
            name=updated_step.name,
            status=updated_step.status,
            message=f"Step '{updated_step.name}' is now in progress",
        )


@router.patch(
    "/{session_id}/steps/{step_code}",
    response_model=StepResponse,
)
async def update_session_step(
    session_id: uuid.UUID,
    step_code: str,
    request: StepUpdateRequest,
    db: AsyncSession = Depends(get_db),
) -> StepResponse:
    """
    Update a step's status (complete, fail, or skip).

    Args:
        session_id: Session UUID
        step_code: Step code identifier
        request: Update parameters

    Returns:
        Updated step details
    """
    service = SessionService(db)

    # Check session exists
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    # Get step
    step = await service.get_step_by_code(session_id, step_code)
    if not step:
        raise HTTPException(
            status_code=404,
            detail=f"Step not found: {step_code}",
        )

    # Validate status
    valid_statuses = [s.value for s in StepStatus]
    if request.status not in valid_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
        )

    # Only allow certain status transitions
    allowed_transitions = {
        StepStatus.PENDING.value: [StepStatus.IN_PROGRESS.value, StepStatus.SKIPPED.value],
        StepStatus.IN_PROGRESS.value: [StepStatus.COMPLETED.value, StepStatus.FAILED.value, StepStatus.SKIPPED.value],
        StepStatus.FAILED.value: [StepStatus.IN_PROGRESS.value, StepStatus.SKIPPED.value],
    }

    current_status = step.status
    if current_status in allowed_transitions:
        if request.status not in allowed_transitions[current_status]:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from {current_status} to {request.status}",
            )
    elif current_status in [StepStatus.COMPLETED.value, StepStatus.SKIPPED.value]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update step: step is already {current_status}",
        )

    # Update step status
    updated_step = await service.update_step_status(
        step_id=step.id,
        status=request.status,
        outputs=request.outputs,
        error_message=request.error_message,
    )

    if not updated_step:
        raise HTTPException(
            status_code=500,
            detail="Failed to update step",
        )

    logger.info(
        "step_updated_via_api",
        session_id=str(session_id),
        step_code=step_code,
        new_status=request.status,
    )

    return StepResponse.model_validate(updated_step)


@router.get("/{session_id}/artifacts", response_model=ArtifactListResponse)
async def get_session_artifacts(
    session_id: uuid.UUID,
    artifact_type: str | None = Query(None, description="Filter by artifact type"),
    db: AsyncSession = Depends(get_db),
) -> ArtifactListResponse:
    """
    Get all artifacts for a session.

    Args:
        session_id: Session UUID
        artifact_type: Optional filter by artifact type

    Returns:
        List of artifacts
    """
    service = SessionService(db)

    # Check session exists
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    artifacts = await service.get_artifacts(session_id, artifact_type=artifact_type)

    return ArtifactListResponse(
        items=[ArtifactResponse.model_validate(a) for a in artifacts],
        total=len(artifacts),
    )


# Maximum content size for download (10MB per FR-015)
MAX_CONTENT_SIZE_BYTES = 10 * 1024 * 1024


@router.get("/{session_id}/artifacts/{artifact_id}/content")
async def get_artifact_content(
    session_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Download raw artifact content.

    For `file_modification` artifacts:
    - Returns `modified_content` for create/modify operations
    - Returns `original_content` for delete operations

    Args:
        session_id: Session UUID
        artifact_id: Artifact UUID

    Returns:
        Raw content with appropriate Content-Type header

    Raises:
        HTTPException 400: Binary content not supported
        HTTPException 404: Session or artifact not found
        HTTPException 413: Content exceeds 10MB limit
    """
    service = SessionService(db)

    # Log access for audit trail (FR-017)
    logger.info(
        "artifact_content_accessed",
        session_id=str(session_id),
        artifact_id=str(artifact_id),
    )

    # Check session exists first
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}",
        )

    # Get artifact (FR-013: UUID validation handled by FastAPI path params)
    artifact = await service.get_artifact(session_id, artifact_id)
    if not artifact:
        raise HTTPException(
            status_code=404,
            detail=f"Artifact not found: {artifact_id}",
        )

    # Check size limit (FR-015)
    if artifact.size_bytes > MAX_CONTENT_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail="Artifact content exceeds the 10MB download limit",
        )

    # Determine content based on artifact type
    content: str = ""

    if artifact.artifact_type == "file_modification":
        # For file_modification, get content from artifact_metadata
        artifact_meta = artifact.artifact_metadata or {}
        operation = artifact_meta.get("operation", "modify")

        if operation == "delete":
            content = artifact_meta.get("original_content", "")
        else:
            content = artifact_meta.get("modified_content", "")
    else:
        # For other artifacts, the content would be read from file_path
        # For now, return empty content as file reading is out of scope
        content = ""

    # Check for binary content (FR-004)
    if is_binary_content(content):
        raise HTTPException(
            status_code=400,
            detail="Cannot download binary artifact as text. Use appropriate client for binary files.",
        )

    return Response(
        content=content,
        media_type=artifact.content_type,
    )


# Pause/Resume Request/Response Models


class PauseRequest(BaseModel):
    reason: str | None = Field(None, description="Reason for pausing")


class PauseResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    checkpoint_id: str | None
    message: str


class ResumeRequest(BaseModel):
    checkpoint_id: str | None = Field(None, description="Checkpoint to resume from")
    updated_state: dict[str, Any] | None = Field(None, description="State updates on resume")


class ResumeResponse(BaseModel):
    session_id: uuid.UUID
    status: str
    message: str


# Pause/Resume Endpoints


@router.post("/{session_id}/pause", response_model=PauseResponse)
async def pause_session(
    session_id: uuid.UUID,
    request: PauseRequest = PauseRequest(),
    db: AsyncSession = Depends(get_db),
) -> PauseResponse:
    service = SessionService(db)
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if session.status not in [SessionStatus.IN_PROGRESS.value]:
        raise HTTPException(status_code=400, detail=f"Cannot pause: status is {session.status}")
    await service.update_status(session_id, SessionStatus.PAUSED.value)
    checkpoint_id = str(uuid.uuid4())
    logger.info("session_paused_via_api", session_id=str(session_id), reason=request.reason)
    return PauseResponse(
        session_id=session_id,
        status=SessionStatus.PAUSED.value,
        checkpoint_id=checkpoint_id,
        message=f"Session paused. Checkpoint: {checkpoint_id}",
    )


@router.post("/{session_id}/resume", response_model=ResumeResponse)
async def resume_session(
    session_id: uuid.UUID,
    request: ResumeRequest = ResumeRequest(),
    db: AsyncSession = Depends(get_db),
) -> ResumeResponse:
    service = SessionService(db)
    session = await service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    if session.status not in [SessionStatus.PAUSED.value]:
        raise HTTPException(status_code=400, detail=f"Cannot resume: status is {session.status}")
    await service.update_status(session_id, SessionStatus.IN_PROGRESS.value)
    logger.info(
        "session_resumed_via_api", session_id=str(session_id), checkpoint_id=request.checkpoint_id
    )
    return ResumeResponse(
        session_id=session_id,
        status=SessionStatus.IN_PROGRESS.value,
        message=f"Session resumed from: {request.checkpoint_id or 'latest'}",
    )


__all__ = ["router"]
