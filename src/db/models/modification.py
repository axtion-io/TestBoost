"""
Modification model for tracking changes made during maintenance.

Stores information about dependency updates and other modifications.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.project import Project


class ModificationType(str, enum.Enum):
    """Type of modification."""

    DEPENDENCY_UPDATE = "dependency_update"
    DEPENDENCY_ADD = "dependency_add"
    DEPENDENCY_REMOVE = "dependency_remove"
    PROPERTY_CHANGE = "property_change"
    PLUGIN_UPDATE = "plugin_update"
    CONFIG_CHANGE = "config_change"


class ModificationStatus(str, enum.Enum):
    """Status of the modification."""

    PENDING = "pending"
    APPLIED = "applied"
    VALIDATED = "validated"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


class Modification(Base):
    """
    Represents a modification made during maintenance workflow.

    Attributes:
        id: Unique identifier for the modification
        project_id: Foreign key to the project
        session_id: ID of the maintenance session
        modification_type: Type of modification
        status: Current status of the modification
        target: Target of the modification (e.g., dependency coordinates)
        old_value: Value before modification
        new_value: Value after modification
        file_path: Path to the modified file
        line_number: Line number of the modification
        reason: Reason for the modification
        validation_result: Result of validation tests
        rolled_back_at: Timestamp if rolled back
        applied_at: Timestamp when applied
        mod_metadata: Additional modification metadata
        created_at: Timestamp when modification was created
        updated_at: Timestamp of last update
    """

    __tablename__ = "modifications"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    session_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    modification_type: Mapped[ModificationType] = mapped_column(
        SQLEnum(ModificationType), nullable=False
    )

    status: Mapped[ModificationStatus] = mapped_column(
        SQLEnum(ModificationStatus), nullable=False, default=ModificationStatus.PENDING
    )

    target: Mapped[str] = mapped_column(String(512), nullable=False)

    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)

    file_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    line_number: Mapped[int | None] = mapped_column(nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    validation_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    mod_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="modifications")

    def __repr__(self) -> str:
        return (
            f"<Modification(id={self.id}, "
            f"type={self.modification_type}, "
            f"status={self.status})>"
        )

    @property
    def is_applied(self) -> bool:
        """Check if modification has been applied."""
        return self.status in (ModificationStatus.APPLIED, ModificationStatus.VALIDATED)

    @property
    def is_rolled_back(self) -> bool:
        """Check if modification was rolled back."""
        return self.status == ModificationStatus.ROLLED_BACK

    def to_dict(self) -> dict[str, Any]:
        """Convert modification to dictionary representation."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "session_id": str(self.session_id) if self.session_id else None,
            "modification_type": self.modification_type.value,
            "status": self.status.value,
            "target": self.target,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "reason": self.reason,
            "validation_result": self.validation_result,
            "rolled_back_at": self.rolled_back_at.isoformat() if self.rolled_back_at else None,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "is_applied": self.is_applied,
            "is_rolled_back": self.is_rolled_back,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
