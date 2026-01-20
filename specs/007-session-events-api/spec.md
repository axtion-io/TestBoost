# Feature Specification: Session Events API Endpoint

**Feature Branch**: `007-session-events-api`
**Created**: 2026-01-13
**Status**: Draft
**Input**: User description: "Ajouter un endpoint API pour récupérer les événements/logs d'une session en temps réel avec possibilité de polling"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View Complete Session Event History (Priority: P1)

As a TestBoost user viewing a session in the web interface, I need to see all events that occurred during that session so I can understand what actions were taken and diagnose any issues.

**Why this priority**: This is the foundation capability - without retrieving events at all, no other event-related features are possible. This provides immediate value by making session activity visible.

**Independent Test**: Can be fully tested by calling the API endpoint for a completed session and verifying all events are returned in chronological order.

**Acceptance Scenarios**:

1. **Given** a session with multiple events, **When** I request all events for that session, **Then** I receive a list of all events with their timestamps, types, messages, and associated data
2. **Given** a session with no events, **When** I request events for that session, **Then** I receive an empty event list with appropriate metadata
3. **Given** a session that doesn't exist, **When** I request events for that session, **Then** I receive a clear error indicating the session was not found

---

### User Story 2 - Monitor Session Progress in Real-Time (Priority: P2)

As a user watching an active session, I need to see new events as they occur (via polling) so I can monitor progress and react quickly to issues without refreshing the entire page.

**Why this priority**: Enables real-time monitoring which is critical for user experience when sessions are running. Builds on P1 by adding time-based filtering.

**Independent Test**: Can be tested by starting a long-running session, polling for events with a timestamp filter, and verifying only new events since the last poll are returned.

**Acceptance Scenarios**:

1. **Given** I last fetched events at timestamp T, **When** I request events since T, **Then** I receive only events that occurred after timestamp T
2. **Given** no new events occurred since timestamp T, **When** I request events since T, **Then** I receive an empty list indicating no new events
3. **Given** I'm polling every 2 seconds, **When** each request completes, **Then** the response time is consistently under 500ms to avoid UI lag

---

### User Story 3 - Filter Events by Type (Priority: P3)

As a user troubleshooting a specific aspect of a session, I need to filter events by type (e.g., errors only, warnings only) so I can focus on relevant information without noise.

**Why this priority**: Enhances usability but not strictly required for basic monitoring. Can be added after core retrieval and polling work.

**Independent Test**: Can be tested by requesting events with a specific event type filter and verifying only matching events are returned.

**Acceptance Scenarios**:

1. **Given** a session with mixed event types, **When** I filter by event_type "error", **Then** I receive only error events
2. **Given** a session with no events of the requested type, **When** I filter by that type, **Then** I receive an empty list
3. **Given** I want to see multiple event types, **When** I don't specify a filter, **Then** I receive all event types

---

### User Story 4 - Limit Event Batch Size (Priority: P3)

As a frontend developer implementing the events display, I need to control how many events are returned per request so I can manage memory usage and render performance.

**Why this priority**: Important for production performance but not needed for initial functionality. Default limits can be used initially.

**Independent Test**: Can be tested by requesting events with different limit values and verifying the exact number of events returned matches the limit.

**Acceptance Scenarios**:

1. **Given** a session with 500 events, **When** I request events with limit=50, **Then** I receive exactly 50 events
2. **Given** a session with 20 events, **When** I request events with limit=50, **Then** I receive all 20 events
3. **Given** I don't specify a limit, **When** I request events, **Then** I receive up to the default maximum (100 events)

---

### Edge Cases

- What happens when requesting events for a session that is currently running and generating new events?
- How does the system handle concurrent requests polling for the same session's events?
- What occurs if the timestamp in the "since" parameter is in the future?
- How does filtering interact with the limit parameter (is limit applied before or after filtering)?
- What happens with very large event payloads (e.g., events containing substantial JSON data)?
- How are events ordered when they have identical timestamps?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a REST endpoint at GET /api/v2/sessions/{session_id}/events that returns events for the specified session
- **FR-002**: System MUST verify the session exists before attempting to retrieve events and return HTTP 404 if not found
- **FR-003**: System MUST support an optional "since" query parameter accepting ISO8601 datetime format to filter events after a specific timestamp
- **FR-004**: System MUST support an optional "event_type" query parameter to filter events by their type classification
- **FR-005**: System MUST support an optional "limit" query parameter to control the maximum number of events returned, with a default value of 100 and maximum of 1000
- **FR-006**: System MUST return events in descending chronological order (newest first) to optimize real-time monitoring use cases
- **FR-007**: Response MUST include pagination metadata (total count, returned count) following existing API patterns
- **FR-008**: Each event in the response MUST include: unique identifier, session_id, step_id (if applicable), event_type, timestamp, message, and event_data (structured data)
- **FR-009**: System MUST complete requests within 500ms even when polling every 2 seconds to support real-time monitoring without UI lag
- **FR-010**: System MUST use efficient database queries with appropriate indexes to support high-frequency polling
- **FR-011**: API responses MUST follow the existing API response format patterns (consistent with SessionsResponse structure)
- **FR-012**: System MUST document the endpoint with OpenAPI specifications including all parameters, response schemas, and error codes
- **FR-013**: System MUST handle invalid query parameters gracefully with HTTP 400 and descriptive error messages
- **FR-014**: When "since" parameter is provided with an invalid datetime format, system MUST return HTTP 400 with clear format requirements

### Key Entities

- **Session Event**: Represents a logged occurrence during a session's lifecycle. Contains timestamp (when event occurred), event_type (classification like "info", "warning", "error", "step_started", "step_completed"), message (human-readable description), event_data (structured payload with context-specific information), session_id (parent session), step_id (optional, if event relates to specific step), and unique identifier
- **Event Response**: Container for returning events to clients. Contains items array (list of events), total count (total matching events), returned count (events in current response), and timestamp of the request (for use in subsequent "since" filters)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: API endpoint responds to event requests in under 500ms at 95th percentile when polling active sessions every 2 seconds
- **SC-002**: System accurately returns only events matching the specified filters (since timestamp, event_type) with 100% accuracy
- **SC-003**: Endpoint handles at least 100 concurrent polling requests without performance degradation or errors
- **SC-004**: Users can monitor active sessions in real-time with events appearing within 2 seconds of occurrence (polling interval + response time)
- **SC-005**: Event retrieval uses efficient database queries that complete in under 100ms for typical session event volumes (up to 10,000 events per session)
- **SC-006**: API documentation is complete with all parameters, responses, and examples, requiring zero clarification questions from frontend developers

## Assumptions *(optional)*

- Events are already being logged to the database during session execution
- The existing Event model in src/db/models/event.py contains all necessary fields
- SessionService methods get_audit_trail() and get_session_events() can be leveraged or adapted for this endpoint
- Frontend will implement polling with a 2-second interval for active sessions
- Event types follow a defined taxonomy (e.g., "info", "warning", "error", "step_started", "step_completed")
- Pagination follows the same pattern as existing API endpoints (e.g., /api/v2/sessions)
- The backend has appropriate database indexes on events table for session_id and timestamp columns
- Event data payloads are reasonably sized (under 1MB per event) to avoid response size issues

## Dependencies *(optional)*

- Existing Event model (src/db/models/event.py)
- SessionService class with event retrieval capabilities
- PostgreSQL database with events table
- Sessions router (src/api/routers/sessions.py) for adding the new endpoint
- Existing API response patterns and pagination structures

## Out of Scope *(optional)*

- WebSocket or Server-Sent Events (SSE) for push-based real-time updates (future consideration for Phase 2)
- Event streaming or log tailing functionality
- Aggregation or analytics on events (e.g., event counts by type)
- Event modification or deletion capabilities
- Exporting events to external logging systems
- Real-time event notifications or alerts
- Event search across multiple sessions
- Advanced filtering (date ranges, multiple event types, regex matching on messages)
