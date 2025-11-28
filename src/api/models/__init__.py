"""Pydantic schemas for API request/response models."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    """Schema for creating a new session."""

    session_type: str = Field(
        ..., description="Type of session (maven_maintenance, test_generation, docker_deployment)"
    )
    project_path: str = Field(..., description="Path to the project directory")
    mode: str = Field(
        default="interactive", description="Execution mode (interactive, autonomous, analysis_only)"
    )
    config: dict[str, Any] = Field(default_factory=dict, description="Session configuration")


class SessionResponse(BaseModel):
    """Schema for session response."""

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


class StepResponse(BaseModel):
    """Schema for step response."""

    id: uuid.UUID
    session_id: uuid.UUID
    name: str
    status: str
    sequence: int
    input_data: dict[str, Any]
    output_data: dict[str, Any] | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class EventResponse(BaseModel):
    """Schema for event response."""

    id: uuid.UUID
    session_id: uuid.UUID
    step_id: uuid.UUID | None = None
    event_type: str
    event_data: dict[str, Any]
    message: str | None = None
    timestamp: datetime

    model_config = {"from_attributes": True}


class ArtifactResponse(BaseModel):
    """Schema for artifact response."""

    id: uuid.UUID
    session_id: uuid.UUID
    step_id: uuid.UUID | None = None
    artifact_type: str
    name: str
    content: str | None = None
    file_path: str | None = None
    metadata: dict[str, Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorResponse(BaseModel):
    """Schema for error response."""

    detail: str
    request_id: str | None = None


__all__ = [
    "SessionCreate",
    "SessionResponse",
    "StepResponse",
    "EventResponse",
    "ArtifactResponse",
    "ErrorResponse",
]
