"""Sessions API router for workflow tracking."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
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
from src.lib.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v2/sessions", tags=["sessions"])


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


class StepExecuteResponse(BaseModel):
    """Response model for step execution."""

    id: uuid.UUID
    code: str
    name: str
    status: str
    message: str


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

    model_config = {"from_attributes": True}


class ArtifactListResponse(BaseModel):
    """Response model for artifact list."""

    items: list[ArtifactResponse]
    total: int


# Endpoints


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(
    request: SessionCreateRequest,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    """
    Create a new workflow session.

    Args:
        request: Session creation parameters

    Returns:
        Created session
    """
    # Validate session type
    valid_types = [t.value for t in SessionType]
    if request.session_type not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid session_type. Must be one of: {', '.join(valid_types)}",
        )

    # Validate mode
    valid_modes = [m.value for m in SessionMode]
    if request.mode not in valid_modes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode. Must be one of: {', '.join(valid_modes)}",
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
    Execute a step (mark as in progress).

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

    # Get and execute step
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

    # Mark step as in progress
    updated_step = await service.execute_step(session_id, step_code)

    if not updated_step:
        raise HTTPException(
            status_code=500,
            detail="Failed to execute step",
        )

    logger.info(
        "step_executed_via_api",
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
