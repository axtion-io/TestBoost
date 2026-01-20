# Data Model: API Endpoints for File Modifications Tracking

**Feature**: 006-file-modifications-api
**Date**: 2026-01-10

## Entity Overview

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│   Session   │──1:N──│    Step     │──1:N──│  Artifact   │
└─────────────┘       └─────────────┘       └─────────────┘
      │                                            │
      └────────────────────1:N────────────────────┘
                                                   │
                                          ┌────────┴────────┐
                                          │    metadata     │
                                          │    (JSONB)      │
                                          │                 │
                                          │ file_path       │
                                          │ operation       │
                                          │ original_content│
                                          │ modified_content│
                                          │ diff            │
                                          └─────────────────┘
```

---

## Existing Entities (No Changes)

### Session

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| project_path | VARCHAR(500) | Path to analyzed project |
| session_type | VARCHAR(50) | maven_maintenance, test_generation, docker_deployment |
| mode | VARCHAR(50) | interactive, autonomous, analysis_only, debug |
| status | VARCHAR(20) | pending, in_progress, paused, completed, failed, cancelled |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |
| metadata | JSONB | Session-specific data |

### Step

| Field | Type | Description |
|-------|------|-------------|
| id | UUID | Primary key |
| session_id | UUID | Foreign key to Session |
| code | VARCHAR(100) | Step identifier |
| name | VARCHAR(255) | Human-readable name |
| sequence | INTEGER | Execution order |
| status | VARCHAR(20) | pending, in_progress, completed, failed, skipped |
| inputs | JSONB | Step input data |
| outputs | JSONB | Step output data |
| created_at | TIMESTAMP | Creation timestamp |
| updated_at | TIMESTAMP | Last update timestamp |

---

## Modified Entity: Artifact

### Schema Changes

| Field | Type | Change | Description |
|-------|------|--------|-------------|
| id | UUID | existing | Primary key |
| session_id | UUID | existing | Foreign key to Session (CASCADE delete) |
| step_id | UUID | existing | Foreign key to Step (CASCADE delete, nullable) |
| name | VARCHAR(255) | existing | Artifact name |
| artifact_type | VARCHAR(50) | existing | Type discriminator (add "file_modification") |
| content_type | VARCHAR(100) | existing | MIME type |
| file_path | TEXT | existing | Path to file |
| size_bytes | INTEGER | existing | Content size |
| created_at | TIMESTAMP | existing | Creation timestamp |
| **metadata** | **JSONB** | **NEW** | Type-specific metadata |

### New Artifact Type: file_modification

When `artifact_type = "file_modification"`, the `metadata` JSONB contains:

```json
{
  "file_path": "pom.xml",
  "operation": "modify",
  "original_content": "<project>...</project>",
  "modified_content": "<project>...</project>",
  "diff": "@@ -10,7 +10,7 @@\n-  <version>1.0</version>\n+  <version>1.1</version>"
}
```

### Metadata Schema (file_modification)

| Field | Type | Nullable | Description |
|-------|------|----------|-------------|
| file_path | string | No | Path relative to project root |
| operation | enum | No | "create", "modify", or "delete" |
| original_content | string | Yes | Original file content (null for create) |
| modified_content | string | Yes | Modified file content (null for delete) |
| diff | string | No | Unified diff format |

### Operation Rules

| Operation | original_content | modified_content | diff |
|-----------|------------------|------------------|------|
| create | null | required | All lines as additions (+) |
| modify | required | required | Standard unified diff |
| delete | required | null | All lines as deletions (-) |

---

## SQLAlchemy Model Changes

### Current Model (src/db/models/artifact.py)

```python
class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("steps.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=func.now())

    # Relationships
    session: Mapped["Session"] = relationship(back_populates="artifacts")
    step: Mapped["Step | None"] = relationship(back_populates="artifacts")
```

### Updated Model

```python
from sqlalchemy.dialects.postgresql import JSONB

class Artifact(Base):
    __tablename__ = "artifacts"

    # ... existing fields ...

    # NEW: Metadata field for type-specific data
    metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
```

---

## Pydantic Response Models

### FileModificationMetadata

```python
from pydantic import BaseModel
from typing import Literal, Optional

class FileModificationMetadata(BaseModel):
    """Metadata structure for file_modification artifact type."""
    file_path: str
    operation: Literal["create", "modify", "delete"]
    original_content: Optional[str] = None
    modified_content: Optional[str] = None
    diff: str

    class Config:
        json_schema_extra = {
            "example": {
                "file_path": "pom.xml",
                "operation": "modify",
                "original_content": "<project>...",
                "modified_content": "<project>...",
                "diff": "@@ -10,7 +10,7 @@..."
            }
        }
```

### Updated ArtifactResponse

```python
class ArtifactResponse(BaseModel):
    """API response model for Artifact."""
    id: UUID
    session_id: UUID
    step_id: Optional[UUID] = None
    name: str
    artifact_type: str
    content_type: str
    file_path: str
    size_bytes: int
    created_at: datetime
    metadata: Optional[dict] = None  # NEW: Include metadata in response

    class Config:
        from_attributes = True
```

---

## Database Migration

### Migration: add_artifact_metadata

```python
"""Add metadata column to artifacts table

Revision ID: 006_add_artifact_metadata
Revises: [previous_revision]
Create Date: 2026-01-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '006_add_artifact_metadata'
down_revision = '[previous_revision]'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column(
        'artifacts',
        sa.Column('metadata', JSONB, nullable=True)
    )

def downgrade() -> None:
    op.drop_column('artifacts', 'metadata')
```

---

## Indexes

### Existing Indexes (No Changes)

- `ix_artifacts_session_id` on `session_id`
- `ix_artifacts_step_id` on `step_id`
- `ix_artifacts_artifact_type` on `artifact_type`

### Optional: New Index for file_modification queries

```sql
-- If querying by file_path becomes common
CREATE INDEX ix_artifacts_metadata_file_path
ON artifacts USING GIN ((metadata->>'file_path'));
```

---

## Validation Rules

### Artifact Type Enum (Existing + New)

```python
ARTIFACT_TYPES = [
    "analysis_report",
    "dependency_tree",
    "build_output",
    "test_report",
    "generated_test",
    "file_modification",  # NEW
]
```

### Size Constraints

- `size_bytes` ≤ 10,485,760 (10MB) for file_modification artifacts
- Enforced at application level before database insert

### Content Validation

- `original_content` and `modified_content` must be valid UTF-8 text
- Binary content detection: reject if null bytes in first 8KB
- `diff` must be valid unified diff format (starts with `---` or is empty for identical files)

---

## Lifecycle Rules

### Creation

1. file_modification artifacts are created by `SessionService.create_file_modification_artifact()`
2. Created automatically during workflow file operations
3. Linked to session (required) and optionally to step

### Immutability (FR-016)

- Once created, file_modification artifacts cannot be updated
- No UPDATE operations allowed on metadata, original_content, modified_content, diff
- Only DELETE via cascade when parent session is deleted

### Deletion

- Individual DELETE not allowed for file_modification type
- Deleted only when parent session is deleted (CASCADE)
- Ensures complete audit trail is preserved

---

## Query Patterns

### Get all file modifications for a session

```python
# In repository
async def get_file_modifications(
    self, session_id: UUID
) -> list[Artifact]:
    stmt = select(Artifact).where(
        Artifact.session_id == session_id,
        Artifact.artifact_type == "file_modification"
    ).order_by(Artifact.created_at)
    result = await self.db.execute(stmt)
    return list(result.scalars().all())
```

### Get artifact with content for download

```python
# In repository
async def get_artifact_by_id(
    self, session_id: UUID, artifact_id: UUID
) -> Artifact | None:
    stmt = select(Artifact).where(
        Artifact.session_id == session_id,
        Artifact.id == artifact_id
    )
    result = await self.db.execute(stmt)
    return result.scalar_one_or_none()
```

---

## Data Volume Estimates

| Scenario | Artifacts per Session | Avg Size per Artifact | DB Impact |
|----------|----------------------|----------------------|-----------|
| Maven maintenance | 1-5 file changes | 50KB avg | 250KB/session |
| Test generation | 5-20 new files | 10KB avg | 200KB/session |
| Large refactoring | 50+ file changes | 30KB avg | 1.5MB/session |

### Retention Policy

- Existing session retention: 365 days (`session_retention_days` in config)
- file_modification artifacts follow session lifecycle
- Automatic cleanup via existing session purge job
