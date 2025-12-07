"""Session model for workflow tracking."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class SessionStatus(str, Enum):
    """Session status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class SessionType(str, Enum):
    """Session type enumeration."""

    MAVEN_MAINTENANCE = "maven_maintenance"
    TEST_GENERATION = "test_generation"
    DOCKER_DEPLOYMENT = "docker_deployment"


class SessionMode(str, Enum):
    """Execution mode enumeration."""

    INTERACTIVE = "interactive"
    AUTONOMOUS = "autonomous"
    ANALYSIS_ONLY = "analysis_only"
    DEBUG = "debug"


class Session(Base):
    """Session model representing a workflow execution."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SessionStatus.PENDING.value
    )
    mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default=SessionMode.INTERACTIVE.value
    )
    project_path: Mapped[str] = mapped_column(Text, nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    steps: Mapped[list["Step"]] = relationship(
        "Step", back_populates="session", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="session", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sessions_status", "status"),
        Index("ix_sessions_project_path", "project_path"),
        Index("ix_sessions_created_at", "created_at"),
    )


# Forward references for type hints
from src.db.models.artifact import Artifact  # noqa: E402
from src.db.models.event import Event  # noqa: E402
from src.db.models.step import Step  # noqa: E402
