# Research: API Endpoints for File Modifications Tracking

**Feature**: 006-file-modifications-api
**Date**: 2026-01-10

## Summary

Research findings for implementing artifact content download and file modification tracking in TestBoost.

---

## 1. Existing Artifact Infrastructure

### Decision
Extend the existing `artifacts` table with a `metadata` JSONB column to store file modification details.

### Rationale
- Current `Artifact` model already has `session_id`, `artifact_type`, `content_type`, `file_path`, `size_bytes`
- JSONB column provides flexibility for different metadata structures per artifact type
- PostgreSQL JSONB is well-indexed and queryable
- Avoids creating a separate table with foreign key overhead

### Alternatives Considered
1. **Separate `file_modifications` table**: Rejected - adds complexity, requires joins, artifact already has session relationship
2. **Store content inline in artifact model**: Rejected - current design uses `file_path` for external storage, but file_modification needs content in DB per spec clarifications
3. **Add multiple new columns**: Rejected - JSONB is more flexible for evolving metadata needs

### Implementation
```python
# In src/db/models/artifact.py
from sqlalchemy import Column, JSON

class Artifact(Base):
    # ... existing fields ...
    metadata = Column(JSON, nullable=True)  # JSONB for PostgreSQL
```

---

## 2. Content Storage Strategy

### Decision
Store `original_content`, `modified_content`, and `diff` as TEXT fields within the `metadata` JSONB column.

### Rationale
- Spec clarification confirmed DB storage (not filesystem)
- TEXT can store up to 1GB in PostgreSQL (well above 10MB limit)
- Keeps all file_modification data together in metadata
- Enables atomic operations (content and diff stored together)

### Alternatives Considered
1. **Filesystem storage with path references**: Rejected per spec clarification - DB storage chosen
2. **Separate content table**: Rejected - unnecessary complexity for single-type usage
3. **Compression**: Deferred - can be added later if DB size becomes issue

### Performance Notes
- PostgreSQL TOAST automatically compresses large TEXT values
- 10MB limit enforced at application level (FR-015)
- Index on `artifact_type` already exists for filtering

---

## 3. Unified Diff Generation

### Decision
Use Python's built-in `difflib` module with `unified_diff` function.

### Rationale
- Standard library - no additional dependencies
- Produces standard unified diff format (compatible with all diff viewers)
- Handles line-by-line comparison efficiently
- Well-tested and stable

### Alternatives Considered
1. **External diff command**: Rejected - requires shell access, MCP principle concern
2. **Third-party library (diff-match-patch)**: Rejected - overkill for line-based diffs
3. **Custom implementation**: Rejected - reinventing the wheel

### Implementation
```python
# In src/lib/diff.py
import difflib
from typing import Optional

def generate_unified_diff(
    original: Optional[str],
    modified: Optional[str],
    file_path: str,
    context_lines: int = 3
) -> str:
    """Generate unified diff format."""
    original_lines = (original or "").splitlines(keepends=True)
    modified_lines = (modified or "").splitlines(keepends=True)

    diff = difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        n=context_lines
    )
    return "".join(diff)
```

---

## 4. Content-Type Detection

### Decision
Use Python's `mimetypes` module combined with existing `content_type` field on artifacts.

### Rationale
- `mimetypes` is standard library
- Artifact already stores `content_type` - reuse it
- Common extensions well-supported (java, xml, json, properties, yaml, etc.)

### Mapping Table
| Extension | Content-Type |
|-----------|--------------|
| .java | text/x-java |
| .xml | application/xml |
| .json | application/json |
| .properties | text/plain |
| .yaml, .yml | text/yaml |
| .md | text/markdown |
| .txt | text/plain |
| .py | text/x-python |

### Binary Detection
```python
def is_binary_content(content: bytes) -> bool:
    """Detect if content is binary (contains null bytes)."""
    return b'\x00' in content[:8192]  # Check first 8KB
```

---

## 5. Authentication Integration

### Decision
Reuse existing API Key authentication middleware from `src/api/middleware/auth.py`.

### Rationale
- FR-014 requires same auth as other session endpoints
- Middleware already configured and tested
- No code changes needed - new endpoint automatically protected

### Verification
- Endpoint path `/api/v2/sessions/*/artifacts/*/content` not in bypass list
- X-API-Key header validated by `api_key_auth_middleware`

---

## 6. Logging for Audit Trail

### Decision
Use existing `structlog` infrastructure with dedicated log event type.

### Rationale
- FR-017 requires logging all accesses
- Existing structured logging already captures request_id
- Simple to add artifact-specific fields

### Implementation
```python
from src.lib.logging import get_logger

logger = get_logger(__name__)

# In endpoint
logger.info(
    "artifact_content_accessed",
    session_id=str(session_id),
    artifact_id=str(artifact_id),
    user=request.state.user_id,  # If available, else "api_key"
    content_type=artifact.content_type,
    size_bytes=artifact.size_bytes
)
```

---

## 7. Error Response Format

### Decision
Use existing error middleware patterns from `src/api/middleware/error.py`.

### Rationale
- Consistent with existing API responses
- ErrorHandlerMiddleware already formats JSON responses
- Custom exceptions available: NotFoundError, ValidationError

### Error Mappings
| Condition | HTTP Code | Error Class |
|-----------|-----------|-------------|
| Artifact not found | 404 | NotFoundError |
| Session not found | 404 | NotFoundError |
| Binary content | 400 | ValidationError |
| Size > 10MB | 413 | Custom (RequestEntityTooLarge) |
| Invalid UUID | 400 | ValidationError |

---

## 8. Database Migration Strategy

### Decision
Use Alembic migration with proper up/down scripts.

### Rationale
- Existing migration infrastructure (alembic.ini, versions/)
- JSONB column addition is non-destructive
- Existing artifacts remain unchanged (metadata=NULL)

### Migration Script
```python
"""Add metadata column to artifacts table

Revision ID: xxx
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

def upgrade() -> None:
    op.add_column('artifacts', sa.Column('metadata', JSONB, nullable=True))

def downgrade() -> None:
    op.drop_column('artifacts', 'metadata')
```

---

## 9. Workflow Integration Points

### Decision
Create a helper function in `SessionService` that workflows call when modifying files.

### Rationale
- Centralized logic for creating file_modification artifacts
- Workflows already use SessionService for artifact creation
- Automatic diff generation at capture time

### Implementation
```python
async def create_file_modification_artifact(
    self,
    session_id: UUID,
    step_id: Optional[UUID],
    file_path: str,
    operation: Literal["create", "modify", "delete"],
    original_content: Optional[str],
    modified_content: Optional[str]
) -> Artifact:
    """Create a file_modification artifact with diff."""
    diff = generate_unified_diff(original_content, modified_content, file_path)

    metadata = {
        "file_path": file_path,
        "operation": operation,
        "original_content": original_content,
        "modified_content": modified_content,
        "diff": diff
    }

    return await self.create_artifact(
        session_id=session_id,
        step_id=step_id,
        name=file_path,
        artifact_type="file_modification",
        content_type="application/json",  # Metadata is JSON
        file_path=file_path,
        size_bytes=len((modified_content or original_content or "").encode()),
        metadata=metadata
    )
```

---

## 10. Frontend Contract

### Decision
Return raw content with appropriate Content-Type header for content endpoint.

### Rationale
- Frontend needs raw content for syntax highlighting
- Content-Type enables proper rendering
- Simple response format (not wrapped in JSON)

### Response Format
```
GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content

Response:
- Status: 200 OK
- Content-Type: text/x-java (or appropriate type)
- Body: Raw file content (plain text)

For file_modification type:
- Return the modified_content (or original_content for deleted files)
```

---

## Summary of Decisions

| Topic | Decision |
|-------|----------|
| Storage | JSONB metadata column on artifacts table |
| Content Storage | TEXT within metadata JSONB |
| Diff Generation | Python difflib.unified_diff |
| Content-Type | mimetypes module + existing field |
| Authentication | Existing API Key middleware |
| Logging | structlog with artifact-specific event |
| Errors | Existing error middleware patterns |
| Migration | Alembic with JSONB column |
| Workflow Integration | SessionService helper method |
| API Response | Raw content with Content-Type header |
