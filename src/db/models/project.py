"""
Project model for tracking Maven projects in TestBoost.

Stores project metadata, configuration, and status information.
"""

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, String
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

if TYPE_CHECKING:
    from src.db.models.dependency import Dependency
    from src.db.models.modification import Modification


class ProjectStatus(str, enum.Enum):
    """Status of a project in TestBoost."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    ANALYZING = "analyzing"
    UPDATING = "updating"
    ERROR = "error"


class BuildSystem(str, enum.Enum):
    """Build system used by the project."""

    MAVEN = "maven"
    GRADLE = "gradle"


class Project(Base):
    """
    Represents a software project tracked by TestBoost.

    Attributes:
        id: Unique identifier for the project
        name: Human-readable project name
        path: Filesystem path to the project root
        build_system: Build system used (Maven, Gradle)
        status: Current status of the project
        java_version: Java version used by the project
        pom_path: Path to pom.xml relative to project root
        repository_url: URL of the source repository
        default_branch: Default git branch name
        last_analyzed: Timestamp of last dependency analysis
        analysis_config: Configuration for dependency analysis
        project_metadata: Additional project metadata
        created_at: Timestamp when project was added
        updated_at: Timestamp of last update
    """

    __tablename__ = "projects"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    path: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)

    build_system: Mapped[BuildSystem] = mapped_column(
        SQLEnum(BuildSystem), nullable=False, default=BuildSystem.MAVEN
    )

    status: Mapped[ProjectStatus] = mapped_column(
        SQLEnum(ProjectStatus), nullable=False, default=ProjectStatus.ACTIVE
    )

    java_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    pom_path: Mapped[str] = mapped_column(String(512), nullable=False, default="pom.xml")

    repository_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    default_branch: Mapped[str] = mapped_column(String(255), nullable=False, default="main")

    last_analyzed: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    analysis_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=dict)

    project_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    dependencies: Mapped[list["Dependency"]] = relationship(
        "Dependency", back_populates="project", cascade="all, delete-orphan"
    )

    modifications: Mapped[list["Modification"]] = relationship(
        "Modification", back_populates="project", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id}, name='{self.name}', status={self.status})>"

    @property
    def full_pom_path(self) -> str:
        """Get the full path to the pom.xml file."""
        import os

        return os.path.join(self.path, self.pom_path)

    def to_dict(self) -> dict[str, Any]:
        """Convert project to dictionary representation."""
        return {
            "id": str(self.id),
            "name": self.name,
            "path": self.path,
            "build_system": self.build_system.value,
            "status": self.status.value,
            "java_version": self.java_version,
            "pom_path": self.pom_path,
            "repository_url": self.repository_url,
            "default_branch": self.default_branch,
            "last_analyzed": self.last_analyzed.isoformat() if self.last_analyzed else None,
            "analysis_config": self.analysis_config,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
