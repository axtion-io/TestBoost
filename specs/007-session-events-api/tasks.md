# Implementation Tasks: Session Events API Endpoint

**Branch**: `007-session-events-api` | **Date**: 2026-01-13
**Input**: Complete design artifacts from `/speckit.plan` command

## Overview

This document provides actionable, dependency-ordered tasks for implementing the Session Events API endpoint feature. Tasks are organized by user story to enable independent implementation and testing. Each user story can be completed and tested before moving to the next.

**Technology Stack**:
- Python 3.11+
- FastAPI 0.121 (async REST API)
- SQLAlchemy 2.x (async ORM)
- Pydantic (data validation)
- PostgreSQL 15 (port 5433)
- structlog (structured logging)
- pytest, pytest-asyncio, httpx (testing)

**Implementation Strategy**: MVP-first approach. Deliver User Story 1 (P1) as minimal viable product, then incrementally add US2-US4.

---

## Phase 1: Setup

**Goal**: Initialize project structure and verify prerequisites.

**Tasks**:

- [X] T001 Verify existing Event model has all required fields in src/db/models/event.py
- [X] T002 Verify existing database indexes on events table (ix_events_session_id, ix_events_timestamp, ix_events_event_type)
- [X] T003 Create API response models directory structure if needed in src/api/models/

---

## Phase 2: Foundational Tasks

**Goal**: Implement shared components required by all user stories.

**Tasks**:

- [X] T004 [P] Create EventResponse Pydantic model in src/api/models/events.py
- [X] T005 [P] Create PaginationMeta Pydantic model in src/api/models/pagination.py (if not exists)
- [X] T006 [P] Create EventListResponse Pydantic model in src/api/models/events.py
- [X] T007 Add helper function create_pagination_meta() in src/api/models/pagination.py
- [X] T008 Document EventResponse schema with field descriptions and examples in src/api/models/events.py

---

## Phase 3: User Story 1 - View Complete Session Event History (P1)

**Story**: As a TestBoost user viewing a session in the web interface, I need to see all events that occurred during that session so I can understand what actions were taken and diagnose any issues.

**Independent Test Criteria**:
- ✅ API endpoint returns all events for a completed session
- ✅ Events are ordered by timestamp descending (newest first)
- ✅ Response includes all required fields (id, session_id, step_id, event_type, event_data, message, timestamp)
- ✅ Empty sessions return empty event list with correct pagination metadata
- ✅ Non-existent sessions return HTTP 404 with clear error message

**Tasks**:

- [X] T009 [US1] Add GET /{session_id}/events endpoint to sessions router in src/api/routers/sessions.py
- [X] T010 [US1] Implement basic event query logic with session_id filter in src/api/routers/sessions.py
- [X] T011 [US1] Add session existence validation before querying events in src/api/routers/sessions.py
- [X] T012 [US1] Implement descending timestamp ordering (newest first) in query in src/api/routers/sessions.py
- [X] T013 [US1] Implement count query for pagination metadata in src/api/routers/sessions.py
- [X] T014 [US1] Build EventListResponse with items and pagination metadata in src/api/routers/sessions.py
- [X] T015 [US1] Add error handling for session not found (HTTP 404) in src/api/routers/sessions.py
- [X] T016 [US1] Add structured logging for endpoint requests in src/api/routers/sessions.py
- [X] T017 [P] [US1] Write unit test for get_session_events endpoint (happy path) in tests/unit/api/test_events_endpoint.py
- [X] T018 [P] [US1] Write unit test for empty event list response in tests/unit/api/test_events_endpoint.py
- [X] T019 [P] [US1] Write unit test for session not found error in tests/unit/api/test_events_endpoint.py
- [ ] T020 [P] [US1] Write integration test with real database in tests/integration/test_events_api.py
- [ ] T021 [US1] Manual testing: Create test session with events and verify API response
- [ ] T022 [US1] Manual testing: Verify event ordering (newest first)
- [ ] T023 [US1] Manual testing: Verify pagination metadata accuracy

---

## Phase 4: User Story 2 - Monitor Session Progress in Real-Time (P2)

**Story**: As a user watching an active session, I need to see new events as they occur (via polling) so I can monitor progress and react quickly to issues without refreshing the entire page.

**Independent Test Criteria**:
- ✅ API accepts `since` query parameter with ISO 8601 datetime
- ✅ Only events after the specified timestamp are returned
- ✅ Empty result returned when no new events exist
- ✅ Response time consistently under 500ms for polling requests
- ✅ Invalid datetime format returns HTTP 400 with clear error message

**Tasks**:

- [X] T024 [US2] Add optional `since` query parameter (datetime) to endpoint in src/api/routers/sessions.py
- [X] T025 [US2] Implement timestamp filtering in event query (timestamp > since) in src/api/routers/sessions.py
- [X] T026 [US2] Add datetime validation with Pydantic Query validator in src/api/routers/sessions.py
- [X] T027 [US2] Add error handling for invalid datetime format (HTTP 400) in src/api/routers/sessions.py
- [X] T028 [US2] Update count query to respect since filter in src/api/routers/sessions.py
- [X] T029 [P] [US2] Write unit test for since parameter filtering in tests/unit/api/test_events_endpoint.py
- [X] T030 [P] [US2] Write unit test for invalid datetime format error in tests/unit/api/test_events_endpoint.py
- [X] T031 [P] [US2] Write unit test for future timestamp (returns empty list) in tests/unit/api/test_events_endpoint.py
- [ ] T032 [P] [US2] Write integration test for polling scenario in tests/integration/test_events_api.py
- [ ] T033 [US2] Performance test: Verify response time < 500ms for polling queries in tests/integration/test_events_api.py
- [ ] T034 [US2] Manual testing: Start long-running session, poll with since parameter
- [ ] T035 [US2] Manual testing: Verify only new events returned in each poll

---

## Phase 5: User Story 3 - Filter Events by Type (P3)

**Story**: As a user troubleshooting a specific aspect of a session, I need to filter events by type (e.g., errors only, warnings only) so I can focus on relevant information without noise.

**Independent Test Criteria**:
- ✅ API accepts `event_type` query parameter
- ✅ Only events matching the specified type are returned
- ✅ Empty result returned when no events match the type
- ✅ All event types returned when no filter specified
- ✅ Invalid event_type pattern returns HTTP 400

**Tasks**:

- [X] T036 [US3] Add optional `event_type` query parameter (string) to endpoint in src/api/routers/sessions.py
- [X] T037 [US3] Implement event_type filtering in event query in src/api/routers/sessions.py
- [X] T038 [US3] Add pattern validation for event_type (^[a-z_]+$) in src/api/routers/sessions.py
- [X] T039 [US3] Update count query to respect event_type filter in src/api/routers/sessions.py
- [X] T040 [P] [US3] Write unit test for event_type filtering in tests/unit/api/test_events_endpoint.py
- [X] T041 [P] [US3] Write unit test for invalid event_type pattern in tests/unit/api/test_events_endpoint.py
- [X] T042 [P] [US3] Write unit test for non-existent event_type (empty list) in tests/unit/api/test_events_endpoint.py
- [ ] T043 [US3] Manual testing: Filter by "workflow_error" type
- [ ] T044 [US3] Manual testing: Verify filtering works with since parameter

---

## Phase 6: User Story 4 - Limit Event Batch Size (P3)

**Story**: As a frontend developer implementing the events display, I need to control how many events are returned per request so I can manage memory usage and render performance.

**Independent Test Criteria**:
- ✅ API accepts `page` and `per_page` query parameters
- ✅ Correct number of events returned based on per_page value
- ✅ Default per_page is 20, maximum is 100
- ✅ Pagination metadata accurate (page, total_pages, has_next, has_prev)
- ✅ Out-of-range page numbers return empty list (not error)

**Tasks**:

- [X] T045 [US4] Add optional `page` query parameter (int, default=1) to endpoint in src/api/routers/sessions.py
- [X] T046 [US4] Add optional `per_page` query parameter (int, default=20, max=100) to endpoint in src/api/routers/sessions.py
- [X] T047 [US4] Calculate offset from page and per_page in src/api/routers/sessions.py
- [X] T048 [US4] Apply LIMIT and OFFSET to event query in src/api/routers/sessions.py
- [X] T049 [US4] Calculate total_pages, has_next, has_prev in pagination metadata in src/api/routers/sessions.py
- [X] T050 [US4] Add validation for page >= 1 and per_page between 1-100 in src/api/routers/sessions.py
- [X] T051 [P] [US4] Write unit test for pagination (page 1, per_page 20) in tests/unit/api/test_events_endpoint.py
- [X] T052 [P] [US4] Write unit test for pagination (page 2) in tests/unit/api/test_events_endpoint.py
- [X] T053 [P] [US4] Write unit test for per_page exceeding maximum (capped at 100) in tests/unit/api/test_events_endpoint.py
- [X] T054 [P] [US4] Write unit test for page beyond total_pages (empty list) in tests/unit/api/test_events_endpoint.py
- [ ] T055 [US4] Manual testing: Request events with per_page=10, verify exactly 10 returned
- [ ] T056 [US4] Manual testing: Navigate through pages, verify no duplicate events

---

## Phase 7: Polish & Cross-Cutting Concerns

**Goal**: Complete documentation, final testing, and production readiness.

**Tasks**:

- [X] T057 [P] Create OpenAPI specification in specs/007-session-events-api/contracts/events-api.yaml (already exists, verify completeness)
- [ ] T058 [P] Write contract validation tests in tests/contract/test_events_contract.py
- [X] T059 Update API documentation with endpoint description and examples
- [ ] T060 [P] Add performance monitoring metrics (testboost_api_request_duration_seconds) in src/api/middleware/logging.py
- [ ] T061 [P] Write load test for 100 concurrent polling requests in tests/performance/test_events_load.py
- [X] T062 Verify all error messages are descriptive and actionable
- [X] T063 Review code for security issues (SQL injection prevention, input validation)
- [X] T064 Run full test suite and fix any failing tests
- [ ] T065 Update CLAUDE.md with any new patterns or conventions
- [ ] T066 Create pull request with implementation summary

---

## Dependencies

### Story Completion Order

```
Phase 1 (Setup) → Phase 2 (Foundational)
                      ↓
          Phase 3 (US1 - Basic Retrieval)
                      ↓
          Phase 4 (US2 - Polling/Since Filter)
                      ↓
     ┌────────────────┴────────────────┐
     ↓                                  ↓
Phase 5 (US3 - Type Filter)    Phase 6 (US4 - Pagination)
     └────────────────┬────────────────┘
                      ↓
          Phase 7 (Polish & Testing)
```

**Dependencies**:
- US2, US3, US4 all depend on US1 (basic retrieval)
- US3 and US4 are independent of each other
- Phase 7 depends on all user stories being complete

### Parallel Execution Opportunities

**Phase 2 (Foundational)**:
- T004, T005, T006, T008 can be done in parallel (different models)

**Phase 3 (US1)**:
- T017, T018, T019 can be written in parallel (different test cases)
- T020 can start once T009-T016 are complete

**Phase 4 (US2)**:
- T029, T030, T031 can be written in parallel (different test cases)

**Phase 5 (US3)**:
- T040, T041, T042 can be written in parallel (different test cases)

**Phase 6 (US4)**:
- T051, T052, T053, T054 can be written in parallel (different test cases)

**Phase 7 (Polish)**:
- T057, T058, T060, T061 can be done in parallel (independent concerns)

---

## Task Summary

**Total Tasks**: 66
- Phase 1 (Setup): 3 tasks
- Phase 2 (Foundational): 5 tasks
- Phase 3 (US1 - P1): 15 tasks
- Phase 4 (US2 - P2): 12 tasks
- Phase 5 (US3 - P3): 9 tasks
- Phase 6 (US4 - P3): 12 tasks
- Phase 7 (Polish): 10 tasks

**Parallelizable Tasks**: 24 tasks marked with [P]

**MVP Scope** (Recommended first delivery):
- Phase 1, Phase 2, Phase 3 (US1) = 23 tasks
- Delivers: Complete event retrieval API with error handling and basic tests
- Provides immediate value: Session activity visibility

**Incremental Delivery**:
- MVP + Phase 4 (US2) = Add real-time polling capability
- MVP + Phase 4 + Phase 5 (US3) = Add event filtering
- MVP + Phase 4 + Phase 5 + Phase 6 (US4) = Add pagination controls
- All phases + Phase 7 = Production-ready release

---

## Implementation Notes

### Key Design Decisions (from research.md)

1. **Event Ordering**: Descending by timestamp (newest first) to optimize polling
2. **Pagination**: Page-based (not cursor-based) for consistency with existing endpoints
3. **Query Performance**: Existing indexes adequate, composite index (session_id, timestamp) optional optimization
4. **API Layer**: Endpoint owns pagination logic, no changes to SessionService.get_audit_trail()

### Performance Targets

- p50: < 100ms
- p95: < 500ms
- p99: < 1000ms
- Database query: < 100ms for 10k events/session

### Testing Strategy

- Unit tests: Mock database, test endpoint logic
- Integration tests: Real database, test full request/response cycle
- Contract tests: Validate OpenAPI specification compliance
- Performance tests: Load testing with 100 concurrent requests

### File Modification Summary

**New Files**:
- `src/api/models/events.py` (EventResponse, EventListResponse)
- `tests/unit/api/test_events_endpoint.py` (unit tests)
- `tests/integration/test_events_api.py` (integration tests)
- `tests/contract/test_events_contract.py` (contract tests)
- `tests/performance/test_events_load.py` (load tests)

**Modified Files**:
- `src/api/routers/sessions.py` (add GET /{session_id}/events endpoint)
- `src/api/models/pagination.py` (if PaginationMeta doesn't exist)

**No Changes Needed**:
- `src/db/models/event.py` (Event model already complete)
- `src/core/session.py` (get_audit_trail() kept unchanged)

---

## Validation Checklist

Before marking this feature complete, verify:

- [ ] All 66 tasks completed
- [ ] All unit tests passing (>95% coverage for new code)
- [ ] All integration tests passing
- [ ] Contract tests validate OpenAPI spec
- [ ] Performance tests meet SLI targets (p95 < 500ms)
- [ ] Manual testing completed for each user story
- [ ] OpenAPI documentation complete and accurate
- [ ] No security vulnerabilities (SQL injection, XSS, etc.)
- [ ] Error messages are descriptive and actionable
- [ ] Code reviewed and approved
- [ ] Pull request merged to main branch

---

**Generated**: 2026-01-13 by `/speckit.tasks` command
**Status**: Ready for implementation
