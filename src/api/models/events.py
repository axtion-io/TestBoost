"""Event API response models."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.api.models.pagination import PaginationMeta


class EventResponse(BaseModel):
    """
    API response schema for a single event.

    Events represent logged occurrences during a session's lifecycle. Each event
    captures what happened, when it happened, and relevant context data.

    Attributes:
        id: Unique event identifier
        session_id: Parent session identifier
        step_id: Parent step identifier (if event relates to a specific step), null otherwise
        event_type: Event classification (e.g., "workflow_started", "step_completed", "workflow_error")
        event_data: Structured event payload with context-specific information
        message: Human-readable event description for logging and display
        timestamp: When the event occurred (ISO 8601 format, timezone-aware)

    Example:
        ```json
        {
            "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            "session_id": "123e4567-e89b-12d3-a456-426614174000",
            "step_id": "456e7890-e89b-12d3-a456-426614174001",
            "event_type": "workflow_completed",
            "event_data": {
                "workflow_type": "test_generation",
                "duration_seconds": 45.67,
                "tests_generated": 12,
                "success": true
            },
            "message": "Test generation workflow completed successfully. Generated 12 tests in 45.67 seconds.",
            "timestamp": "2026-01-13T14:30:00.123456Z"
        }
        ```
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(
        ...,
        description="Unique event identifier",
        json_schema_extra={"example": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"},
    )

    session_id: uuid.UUID = Field(
        ...,
        description="Parent session identifier",
        json_schema_extra={"example": "123e4567-e89b-12d3-a456-426614174000"},
    )

    step_id: uuid.UUID | None = Field(
        None,
        description="Parent step identifier (if event relates to a specific step)",
        json_schema_extra={"example": "456e7890-e89b-12d3-a456-426614174001"},
    )

    event_type: str = Field(
        ...,
        description="Event classification",
        json_schema_extra={"example": "workflow_started"},
    )

    event_data: dict[str, Any] = Field(
        ...,
        description="Structured event payload with context-specific information",
        json_schema_extra={
            "example": {
                "workflow_type": "test_generation",
                "duration_seconds": 45.67,
                "tests_generated": 12,
            }
        },
    )

    message: str | None = Field(
        None,
        description="Human-readable event description for logging and display",
        json_schema_extra={
            "example": "Test generation workflow completed successfully. Generated 12 tests in 45.67 seconds."
        },
    )

    timestamp: datetime = Field(
        ...,
        description="When the event occurred (ISO 8601 format, timezone-aware)",
        json_schema_extra={"example": "2026-01-13T14:30:00.123456Z"},
    )


class EventListResponse(BaseModel):
    """
    API response for paginated event list.

    Contains a list of events for the current page along with pagination metadata
    to support navigation (next/previous page, total count, etc.).

    Events are returned in descending chronological order (newest first) to optimize
    real-time monitoring use cases where users care most about recent events.

    Attributes:
        items: List of events for the current page
        pagination: Pagination metadata (page, per_page, total, total_pages, has_next, has_prev)

    Example:
        ```json
        {
            "items": [
                {
                    "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "session_id": "123e4567-e89b-12d3-a456-426614174000",
                    "step_id": null,
                    "event_type": "workflow_completed",
                    "event_data": {
                        "workflow_type": "test_generation",
                        "duration_seconds": 45.67,
                        "tests_generated": 12,
                        "success": true
                    },
                    "message": "Test generation workflow completed successfully.",
                    "timestamp": "2026-01-13T14:30:45.123456Z"
                }
            ],
            "pagination": {
                "page": 1,
                "per_page": 20,
                "total": 45,
                "total_pages": 3,
                "has_next": true,
                "has_prev": false
            }
        }
        ```
    """

    items: list[EventResponse] = Field(..., description="List of events for the current page")

    pagination: PaginationMeta = Field(..., description="Pagination metadata")


__all__ = [
    "EventResponse",
    "EventListResponse",
]
