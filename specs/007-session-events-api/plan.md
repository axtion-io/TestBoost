# Implementation Plan: Session Events API Endpoint

**Branch**: `007-session-events-api` | **Date**: 2026-01-13 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/007-session-events-api/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Add a REST API endpoint at `GET /api/v2/sessions/{session_id}/events` to retrieve session events with support for real-time polling via query parameters (since timestamp, event type filtering, limit). This enables frontend monitoring of session progress and troubleshooting by exposing the existing event log through a paginated API. The implementation leverages existing Event model, SessionService methods, and follows established API response patterns.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.121, SQLAlchemy 2.x (async), Pydantic, structlog
**Storage**: PostgreSQL 15 on port 5433 - existing `events` table with indexes on session_id, timestamp, event_type
**Testing**: pytest, pytest-asyncio, httpx (for API testing)
**Target Platform**: Linux server (Docker deployment)
**Project Type**: Single project (backend API)
**Performance Goals**:
- API response time < 500ms at p95 for polling requests
- Database query time < 100ms for typical event volumes (10k events/session)
- Support 100 concurrent polling requests without degradation
**Constraints**:
- Must use existing Event model and indexes (no schema changes)
- Must follow existing API response patterns (items + total)
- No WebSocket/SSE - HTTP polling only
- Default limit 100, max 1000 events per request
**Scale/Scope**:
- Typical sessions: 100-1000 events
- High-volume sessions: up to 10,000 events
- Expected concurrent users: 10-50 polling active sessions

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ 1. Zéro Complaisance
- **Status**: PASS
- **Rationale**: Endpoint returns actual events from database, no synthetic data. Empty responses clearly indicate no events available.

### ✅ 2. Outils via MCP Exclusivement
- **Status**: N/A
- **Rationale**: This feature is a REST API endpoint, not an agent using tools. No MCP servers involved.

### ✅ 3. Pas de Mocks en Production Utilisateur
- **Status**: PASS
- **Rationale**: No mocks. Direct database queries via SQLAlchemy ORM. Real event data only.

### ✅ 4. Automatisation avec Contrôle Utilisateur
- **Status**: PASS
- **Rationale**: Read-only API endpoint. No automation or user control needed - pure data retrieval.

### ✅ 5. Traçabilité Complète
- **Status**: PASS
- **Rationale**: Events are immutable audit trail entries. This endpoint exposes existing traceability to clients.

### ✅ 6. Validation Avant Modification
- **Status**: N/A
- **Rationale**: Read-only endpoint performs no modifications. Session existence validated before query.

### ✅ 7. Isolation et Sécurité
- **Status**: PASS
- **Rationale**: Read-only access. No data modification. Session ownership/access control via existing auth.

### ✅ 8. Découplage et Modularité
- **Status**: PASS
- **Rationale**: New endpoint in existing sessions router. Uses SessionService abstraction. No tight coupling.

### ✅ 9. Transparence des Décisions
- **Status**: PASS
- **Rationale**: API returns descriptive errors (404 if session not found, 400 for invalid params). Clear response structure.

### ✅ 10. Robustesse et Tolérance aux Erreurs
- **Status**: PASS
- **Rationale**: Graceful error handling for invalid session IDs, malformed timestamps, and database errors.

### ✅ 11. Performance Raisonnable
- **Status**: PASS
- **Rationale**: Leverages existing database indexes. Query optimization ensures < 500ms responses for polling.

### ✅ 12. Respect des Standards du Projet Cible
- **Status**: PASS
- **Rationale**: Follows existing API patterns (SessionResponse, items+total structure). Consistent with /sessions, /steps, /artifacts endpoints.

### ✅ 13. Simplicité d'Utilisation
- **Status**: PASS
- **Rationale**: Standard REST GET with optional query params. Follows intuitive conventions (since, limit, event_type).

**Constitution Result**: ✅ ALL GATES PASSED - No violations to justify

## Project Structure

### Documentation (this feature)

```text
specs/007-session-events-api/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── events-api.yaml  # OpenAPI spec for the new endpoint
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── api/
│   └── routers/
│       └── sessions.py          # Add new GET /{session_id}/events endpoint
├── core/
│   └── session.py               # Leverage existing get_audit_trail() method
├── db/
│   ├── models/
│   │   └── event.py            # Existing Event model (no changes needed)
│   └── repository.py            # Existing EventRepository (already has get_by_session)
└── lib/
    └── logging.py               # Use for request logging

tests/
├── unit/
│   └── api/
│       └── test_events_endpoint.py    # New unit tests for events endpoint
├── integration/
│   └── test_events_api.py             # Integration tests with real DB
└── contract/
    └── test_events_contract.py         # OpenAPI contract validation tests
```

**Structure Decision**: Single project structure (Option 1). The new endpoint integrates into the existing `src/api/routers/sessions.py` file, following the established pattern where session-related endpoints are grouped (we already have sessions, steps, artifacts in this router). The implementation will reuse `SessionService.get_audit_trail()` which provides the exact filtering capabilities needed (event_type, since timestamp).

## Complexity Tracking

No constitution violations - this section intentionally left empty per template instructions.

---

## Phase 0: Research ✅ COMPLETED

**Status**: Complete (2026-01-13)

**Research Completed**:
1. ✅ Event types documented - 11 distinct event types identified across lifecycle events
2. ✅ Pagination patterns analyzed - PaginationMeta + items structure from existing endpoints
3. ✅ Index performance verified - Existing indexes adequate for < 500ms requirement
4. ✅ get_audit_trail() implementation analyzed - Reusable for API layer with pagination wrapper

**Key Findings**:
- Event model already has all required fields and optimal indexes
- SessionService.get_audit_trail() provides 80% of needed functionality
- No database migrations required - leverage existing schema
- API should use descending order (newest first) for polling optimization

**Output**: [research.md](./research.md)

---

## Phase 1: Design & Contracts ✅ COMPLETED

**Status**: Complete (2026-01-13)

**Deliverables Created**:
1. ✅ [data-model.md](./data-model.md) - Event entity documentation with field definitions, indexes, and relationships
2. ✅ [contracts/events-api.yaml](./contracts/events-api.yaml) - Complete OpenAPI 3.0 specification with examples
3. ✅ [quickstart.md](./quickstart.md) - Developer integration guide with React/Python examples

**Design Decisions**:
- Response format: EventListResponse with items + PaginationMeta (consistent with existing endpoints)
- Query params: page, per_page, since (datetime), event_type (string filter)
- Ordering: DESC by timestamp (newest first) for polling optimization
- Pagination: Standard page-based (not cursor-based) for consistency

**Agent Context Updated**: ✅ CLAUDE.md updated with feature technologies

**Constitution Check Re-verification**: ✅ ALL GATES STILL PASS
- No design changes violate constitution principles
- Read-only endpoint maintains compliance with all 13 principles

**Output**: Complete design artifacts ready for Phase 2 (tasks generation)

---

## Phase 2: Task Generation ✅ COMPLETED

**Status**: Complete (2026-01-13)

**Deliverables Created**:
1. ✅ [tasks.md](./tasks.md) - Complete implementation task list with 66 actionable tasks

**Task Organization**:
- Phase 1: Setup (3 tasks)
- Phase 2: Foundational (5 tasks)
- Phase 3: US1 - View Complete Session Event History - P1 (15 tasks)
- Phase 4: US2 - Monitor Session Progress in Real-Time - P2 (12 tasks)
- Phase 5: US3 - Filter Events by Type - P3 (9 tasks)
- Phase 6: US4 - Limit Event Batch Size - P3 (12 tasks)
- Phase 7: Polish & Cross-Cutting Concerns (10 tasks)

**Key Features**:
- All tasks follow strict checklist format (checkbox, ID, priority markers, story labels, file paths)
- 24 tasks marked as parallelizable for efficient implementation
- Clear dependency graph showing story completion order
- MVP scope identified (Phase 1-3 = 23 tasks)
- Independent test criteria defined for each user story
- Performance targets documented (p95 < 500ms)

**MVP Recommendation**: Deliver Phase 1-3 (US1) first for immediate value, then incrementally add US2-US4.

**Output**: [tasks.md](./tasks.md) ready for implementation

---

## Notes

- **Existing foundation**: Event model already has all required fields and indexes. SessionService.get_audit_trail() provides 80% of needed functionality.
- **Key design decision**: Return events in descending order (newest first) to optimize real-time polling use case where users care most about recent events.
- **Performance strategy**: Leverage existing indexes on (session_id, timestamp, event_type). No new migrations needed.
- **API consistency**: Follow StepListResponse and ArtifactListResponse patterns with items + total fields.
