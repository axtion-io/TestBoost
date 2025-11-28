"""ProjectLock model for exclusive project locking."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base


class ProjectLock(Base):
    """ProjectLock model for preventing concurrent modifications."""

    __tablename__ = "project_locks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_path: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    session: Mapped["Session"] = relationship("Session")

    __table_args__ = (
        Index("ix_project_locks_project_path", "project_path"),
        Index("ix_project_locks_expires_at", "expires_at"),
    )


# Forward references
from src.db.models.session import Session  # noqa: E402
