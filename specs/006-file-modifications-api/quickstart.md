# Quickstart: File Modifications API

**Feature**: 006-file-modifications-api
**Date**: 2026-01-10

## Overview

This guide provides quick instructions for implementing and testing the file modifications API feature.

---

## Prerequisites

- PostgreSQL 15 running on port 5433
- Python 3.11+ environment with TestBoost dependencies
- API Key configured in environment

```bash
# Environment variables
export DATABASE_URL="postgresql+asyncpg://testboost:testboost@localhost:5433/testboost"
export API_KEY="your-api-key-here"
```

---

## Implementation Checklist

### 1. Database Migration

```bash
# Create the migration
cd src/db/migrations
alembic revision --autogenerate -m "add_artifact_metadata"

# Run the migration
alembic upgrade head
```

### 2. Create Diff Utility

Create `src/lib/diff.py`:

```python
import difflib
from typing import Optional

def generate_unified_diff(
    original: Optional[str],
    modified: Optional[str],
    file_path: str,
    context_lines: int = 3
) -> str:
    """Generate unified diff format from original and modified content."""
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

### 3. Add Content Endpoint

In `src/api/routers/sessions.py`, add:

```python
from fastapi import Response
from src.lib.logging import get_logger

logger = get_logger(__name__)

@router.get("/{session_id}/artifacts/{artifact_id}/content")
async def get_artifact_content(
    session_id: UUID,
    artifact_id: UUID,
    db: AsyncSession = Depends(get_db)
) -> Response:
    """Download raw artifact content."""
    service = SessionService(db)

    # Log access for audit trail (FR-017)
    logger.info(
        "artifact_content_accessed",
        session_id=str(session_id),
        artifact_id=str(artifact_id)
    )

    # Get artifact
    artifact = await service.get_artifact(session_id, artifact_id)
    if not artifact:
        raise NotFoundError(f"Artifact {artifact_id} not found")

    # Check size limit (FR-015)
    if artifact.size_bytes > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(
            status_code=413,
            detail="Artifact content exceeds the 10MB download limit"
        )

    # Get content based on artifact type
    if artifact.artifact_type == "file_modification":
        metadata = artifact.metadata or {}
        operation = metadata.get("operation")
        if operation == "delete":
            content = metadata.get("original_content", "")
        else:
            content = metadata.get("modified_content", "")
    else:
        # For other artifact types, read from file_path
        content = await read_artifact_file(artifact.file_path)

    return Response(
        content=content,
        media_type=artifact.content_type
    )
```

### 4. Add SessionService Helper

In `src/core/session.py`, add:

```python
from src.lib.diff import generate_unified_diff
from typing import Literal

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

    content_size = len((modified_content or original_content or "").encode())

    return await self.create_artifact(
        session_id=session_id,
        step_id=step_id,
        name=file_path,
        artifact_type="file_modification",
        content_type="application/json",
        file_path=file_path,
        size_bytes=content_size,
        metadata=metadata
    )
```

---

## Testing

### Manual Testing with curl

```bash
# Set variables
SESSION_ID="your-session-id"
ARTIFACT_ID="your-artifact-id"
API_KEY="your-api-key"
BASE_URL="http://localhost:8000"

# List file modification artifacts
curl -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v2/sessions/$SESSION_ID/artifacts?type=file_modification"

# Download artifact content
curl -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v2/sessions/$SESSION_ID/artifacts/$ARTIFACT_ID/content"

# Test error cases
# 404 - Artifact not found
curl -H "X-API-Key: $API_KEY" \
  "$BASE_URL/api/v2/sessions/$SESSION_ID/artifacts/00000000-0000-0000-0000-000000000000/content"

# 401 - No API key
curl "$BASE_URL/api/v2/sessions/$SESSION_ID/artifacts/$ARTIFACT_ID/content"
```

### Python Test Script

```python
import httpx
import asyncio

async def test_artifact_content():
    async with httpx.AsyncClient() as client:
        base = "http://localhost:8000"
        headers = {"X-API-Key": "your-api-key"}

        # Create a test session first
        session_resp = await client.post(
            f"{base}/api/v2/sessions",
            json={
                "project_path": "test-projects/sample",
                "session_type": "maven_maintenance",
                "mode": "interactive"
            },
            headers=headers
        )
        session_id = session_resp.json()["id"]

        # List artifacts (should include any file_modification types)
        artifacts_resp = await client.get(
            f"{base}/api/v2/sessions/{session_id}/artifacts",
            params={"type": "file_modification"},
            headers=headers
        )
        print(f"Artifacts: {artifacts_resp.json()}")

        # If artifacts exist, download content
        artifacts = artifacts_resp.json()
        if artifacts:
            artifact_id = artifacts[0]["id"]
            content_resp = await client.get(
                f"{base}/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content",
                headers=headers
            )
            print(f"Content-Type: {content_resp.headers['content-type']}")
            print(f"Content: {content_resp.text[:500]}")

if __name__ == "__main__":
    asyncio.run(test_artifact_content())
```

### Unit Tests

```bash
# Run diff utility tests
pytest tests/unit/test_diff.py -v

# Run API integration tests
pytest tests/integration/test_artifact_content.py -v

# Run all related tests
pytest tests/ -k "artifact" -v
```

---

## Workflow Integration Example

When modifying files in a workflow:

```python
# In your workflow step
async def modify_pom_xml(session_service, session_id, step_id, project_path):
    pom_path = f"{project_path}/pom.xml"

    # Read original content
    with open(pom_path, 'r') as f:
        original_content = f.read()

    # Make modifications
    modified_content = update_version(original_content, "1.1.0")

    # Write changes
    with open(pom_path, 'w') as f:
        f.write(modified_content)

    # Create file_modification artifact for tracking
    await session_service.create_file_modification_artifact(
        session_id=session_id,
        step_id=step_id,
        file_path="pom.xml",
        operation="modify",
        original_content=original_content,
        modified_content=modified_content
    )
```

---

## Verification Checklist

- [ ] Database migration applied successfully
- [ ] `/content` endpoint returns correct Content-Type headers
- [ ] 404 returned for non-existent artifacts
- [ ] 400 returned for binary content
- [ ] 413 returned for content > 10MB
- [ ] API Key authentication enforced
- [ ] Access logging working (check logs)
- [ ] file_modification artifacts have correct metadata structure
- [ ] Unified diff format is valid and renderable

---

## Troubleshooting

### Common Issues

**Migration fails**
```bash
# Check current migration state
alembic current

# Rollback if needed
alembic downgrade -1
```

**Content-Type incorrect**
- Verify `content_type` field is set correctly when creating artifacts
- Check mimetypes module mapping

**Large file rejected**
- Expected behavior for files > 10MB
- Response should be HTTP 413 with clear message

**Diff not rendering**
- Verify diff starts with `---` line
- Check for encoding issues (UTF-8 required)

---

## API Quick Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v2/sessions/{id}/artifacts` | GET | List artifacts (filter with `?type=file_modification`) |
| `/api/v2/sessions/{id}/artifacts/{id}/content` | GET | Download raw content |

| Header | Required | Description |
|--------|----------|-------------|
| X-API-Key | Yes | Authentication token |

| Response Code | Meaning |
|---------------|---------|
| 200 | Success - content returned |
| 400 | Bad request - binary content or invalid params |
| 401 | Unauthorized - missing/invalid API key |
| 404 | Not found - session or artifact doesn't exist |
| 413 | Payload too large - content > 10MB |
