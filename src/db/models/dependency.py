"""
Dependency model for tracking Maven dependencies.

Stores dependency information, versions, and update status.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.project import Project


class DependencyScope(enum.StrEnum):
    """Maven dependency scope."""

    COMPILE = "compile"
    PROVIDED = "provided"
    RUNTIME = "runtime"
    TEST = "test"
    SYSTEM = "system"
    IMPORT = "import"


class UpdateStatus(enum.StrEnum):
    """Status of dependency update."""

    CURRENT = "current"
    UPDATE_AVAILABLE = "update_available"
    VULNERABLE = "vulnerable"
    UNKNOWN = "unknown"


class Dependency(Base):
    """
    Represents a Maven dependency in a project.

    Attributes:
        id: Unique identifier for the dependency
        project_id: Foreign key to the project
        group_id: Maven group ID
        artifact_id: Maven artifact ID
        current_version: Currently used version
        latest_version: Latest available version
        scope: Maven dependency scope
        update_status: Current update status
        is_direct: Whether this is a direct dependency
        is_managed: Whether version is managed by parent/BOM
        vulnerabilities: List of known vulnerabilities
        release_notes_url: URL to release notes
        last_checked: Timestamp of last version check
        dep_metadata: Additional dependency metadata
        created_at: Timestamp when dependency was added
        updated_at: Timestamp of last update
    """

    __tablename__ = "dependencies"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True
    )

    group_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    artifact_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    current_version: Mapped[str] = mapped_column(String(100), nullable=False)

    latest_version: Mapped[str | None] = mapped_column(String(100), nullable=True)

    scope: Mapped[DependencyScope] = mapped_column(
        SQLEnum(DependencyScope), nullable=False, default=DependencyScope.COMPILE
    )

    update_status: Mapped[UpdateStatus] = mapped_column(
        SQLEnum(UpdateStatus), nullable=False, default=UpdateStatus.UNKNOWN
    )

    is_direct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    is_managed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    vulnerabilities: Mapped[list[Any] | None] = mapped_column(JSON, nullable=True, default=list)

    release_notes_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    last_checked: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    dep_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="dependencies")

    def __repr__(self) -> str:
        return (
            f"<Dependency(id={self.id}, "
            f"coords='{self.group_id}:{self.artifact_id}:{self.current_version}')>"
        )

    @property
    def coordinates(self) -> str:
        """Get Maven coordinates string."""
        return f"{self.group_id}:{self.artifact_id}:{self.current_version}"

    @property
    def has_update(self) -> bool:
        """Check if an update is available."""
        return self.latest_version is not None and self.latest_version != self.current_version

    @property
    def is_vulnerable(self) -> bool:
        """Check if dependency has known vulnerabilities."""
        return bool(self.vulnerabilities)

    def to_dict(self) -> dict[str, Any]:
        """Convert dependency to dictionary representation."""
        return {
            "id": str(self.id),
            "project_id": str(self.project_id),
            "group_id": self.group_id,
            "artifact_id": self.artifact_id,
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "scope": self.scope.value,
            "update_status": self.update_status.value,
            "is_direct": self.is_direct,
            "is_managed": self.is_managed,
            "vulnerabilities": self.vulnerabilities,
            "release_notes_url": self.release_notes_url,
            "last_checked": self.last_checked.isoformat() if self.last_checked else None,
            "has_update": self.has_update,
            "is_vulnerable": self.is_vulnerable,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
