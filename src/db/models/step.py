"""Step model for workflow step tracking."""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class StepStatus(StrEnum):
    """Step status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class Step(Base):
    """Step model representing a workflow step execution."""

    __tablename__ = "steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StepStatus.PENDING.value
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    outputs: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="steps")
    events: Mapped[list["Event"]] = relationship(
        "Event", back_populates="step", cascade="all, delete-orphan"
    )
    artifacts: Mapped[list["Artifact"]] = relationship(
        "Artifact", back_populates="step", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_steps_session_id", "session_id"),
        Index("ix_steps_status", "status"),
        Index("ix_steps_sequence", "session_id", "sequence"),
    )


# Forward references
from src.db.models.artifact import Artifact  # noqa: E402
from src.db.models.event import Event  # noqa: E402
from src.db.models.session import Session  # noqa: E402
