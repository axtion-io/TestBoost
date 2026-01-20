# Implementation Plan: API Endpoints for File Modifications Tracking

**Branch**: `006-file-modifications-api` | **Date**: 2026-01-10 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/006-file-modifications-api/spec.md`

## Summary

Add artifact content download endpoint (`GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content`) and new `file_modification` artifact type to track all file changes made by TestBoost workflows. This enables TestBoost-Web frontend to display file contents and diffs for user review.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.121, SQLAlchemy (async), Pydantic, structlog
**Storage**: PostgreSQL 15 (port 5433) - existing artifacts table with new metadata field
**Testing**: pytest, pytest-asyncio, httpx (for API testing)
**Target Platform**: Linux server (Docker)
**Project Type**: Single project (backend API)
**Performance Goals**: Content download < 2 seconds for files up to 1MB (SC-004)
**Constraints**: Files > 10MB rejected with HTTP 413, < 5 seconds for workflow capture (SC-002)
**Scale/Scope**: Existing user base, extend current artifact infrastructure

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Implementation Notes |
|-----------|--------|---------------------|
| 1. Zéro Complaisance | ✅ PASS | Real file content only, no synthetic data. Empty/null fields explicit. |
| 2. Outils via MCP | ✅ PASS | File operations via existing workflows, not direct agent calls |
| 3. Pas de Mocks Production | ✅ PASS | Real DB content returned to users |
| 4. Automatisation + Contrôle | ✅ PASS | file_modification artifacts created automatically, user can view/review |
| 5. Traçabilité Complète | ✅ PASS | FR-017 logs all accesses, artifacts are immutable |
| 6. Validation Avant Modification | ✅ PASS | UUID validation (FR-013), size check (FR-015) |
| 7. Isolation et Sécurité | ✅ PASS | API Key auth (FR-014), cascade delete only |
| 8. Découplage et Modularité | ✅ PASS | New endpoint extends existing router, new artifact type |
| 9. Transparence des Décisions | ✅ PASS | Clear error messages, diff generation for changes |
| 10. Robustesse | ✅ PASS | Proper HTTP error codes (400, 404, 413) |
| 11. Performance | ✅ PASS | SC-004: < 2s for 1MB files |
| 12. Standards Projet | ✅ PASS | Follows existing patterns in sessions.py |
| 13. Simplicité | ✅ PASS | Single endpoint, standard REST pattern |

**Gate Result**: ✅ ALL PASS - Proceed to implementation

## Project Structure

### Documentation (this feature)

```text
specs/006-file-modifications-api/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.yaml         # OpenAPI spec for new endpoint
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── api/
│   ├── routers/
│   │   └── sessions.py       # ADD: /content endpoint
│   └── models/
│       └── sessions.py       # ADD: FileModificationMetadata response model
├── db/
│   ├── models/
│   │   └── artifact.py       # MODIFY: Add metadata JSONB field
│   └── migrations/
│       └── versions/
│           └── xxx_add_artifact_metadata.py  # NEW: Migration
├── core/
│   └── session.py            # ADD: create_file_modification_artifact()
└── lib/
    └── diff.py               # NEW: Unified diff generation utility

tests/
├── unit/
│   └── test_diff.py          # NEW: Diff utility tests
└── integration/
    └── test_artifact_content.py  # NEW: API endpoint tests
```

**Structure Decision**: Single project pattern - backend-only feature extending existing API infrastructure. No frontend changes (consumed by separate TestBoost-Web project).

## Complexity Tracking

> No violations - all constitution gates pass without justification needed.

## Implementation Approach

### Phase 1: Core Infrastructure

1. **Database Migration**: Add `metadata` JSONB column to artifacts table
2. **Diff Utility**: Create `lib/diff.py` for unified diff generation
3. **Response Models**: Add Pydantic models for file_modification metadata

### Phase 2: API Endpoint

1. **Content Endpoint**: Add `GET .../artifacts/{artifact_id}/content`
2. **Validation**: UUID, size, binary detection
3. **Authentication**: Reuse existing API Key middleware
4. **Logging**: Add structured logging for audit trail

### Phase 3: Workflow Integration

1. **File Modification Tracking**: Add helper to capture changes in workflows
2. **Maven Maintenance**: Update to create file_modification artifacts
3. **Test Generation**: Update to create file_modification artifacts

### Phase 4: Testing & Documentation

1. **Unit Tests**: Diff utility, model validation
2. **Integration Tests**: API endpoint behavior
3. **Documentation**: Update API docs

## Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `src/lib/diff.py` | CREATE | Unified diff generation utility |
| `src/api/routers/sessions.py` | MODIFY | Add /content endpoint |
| `src/api/models/sessions.py` | MODIFY | Add FileModificationMetadata model |
| `src/db/models/artifact.py` | MODIFY | Add metadata JSONB field |
| `src/db/migrations/versions/xxx_*.py` | CREATE | Database migration |
| `src/core/session.py` | MODIFY | Add file modification helper |
| `tests/unit/test_diff.py` | CREATE | Unit tests for diff utility |
| `tests/integration/test_artifact_content.py` | CREATE | API integration tests |

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Large file performance | Low | Medium | 10MB limit enforced, streaming possible |
| Database bloat | Medium | Low | TEXT fields for content, retention policy exists |
| Migration issues | Low | Medium | Test migration on staging first |
| Binary file handling | Low | Low | Explicit 400 error for binary files |

## Dependencies

- Existing `artifacts` table and model
- Existing API Key authentication middleware
- Existing `SessionService` class
- Existing `ArtifactRepository` class
