"""Artifact model for storing generated files and reports."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class Artifact(Base):
    """Artifact model for workflow outputs like reports and generated files."""

    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("steps.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    # Note: Using artifact_metadata to avoid conflict with SQLAlchemy's metadata attribute
    artifact_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata", JSONB, nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="artifacts")
    step: Mapped["Step | None"] = relationship("Step", back_populates="artifacts")

    __table_args__ = (
        Index("ix_artifacts_session_id", "session_id"),
        Index("ix_artifacts_step_id", "step_id"),
        Index("ix_artifacts_artifact_type", "artifact_type"),
    )


# Forward references
from src.db.models.session import Session  # noqa: E402
from src.db.models.step import Step  # noqa: E402
