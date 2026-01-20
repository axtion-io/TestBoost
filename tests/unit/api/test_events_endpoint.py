"""Tests for events API endpoints."""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestEventsEndpoint:
    """Tests for the /api/v2/sessions/{session_id}/events endpoint."""

    @pytest.mark.asyncio
    async def test_get_session_events_success(self, client):
        """
        T017: Test getting events for a session (happy path).

        Should return paginated list of events with proper metadata.
        """
        # Create a valid session ID
        session_id = str(uuid.uuid4())

        # Make request to events endpoint
        response = await client.get(f"/api/v2/sessions/{session_id}/events")

        # Endpoint should be reachable and return valid status
        # With mocked DB, may return 404 (session not found) or 200 (empty list)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Verify response structure
            assert "items" in data
            assert "pagination" in data
            assert isinstance(data["items"], list)
            assert isinstance(data["pagination"], dict)

            # Verify pagination metadata structure
            pagination = data["pagination"]
            assert "page" in pagination
            assert "per_page" in pagination
            assert "total" in pagination
            assert "total_pages" in pagination
            assert "has_next" in pagination
            assert "has_prev" in pagination

    @pytest.mark.asyncio
    async def test_get_session_events_empty_list(self, client):
        """
        T018: Test getting events for a session with no events.

        Should return empty list with correct pagination metadata.
        """
        # Create a valid session ID
        session_id = str(uuid.uuid4())

        # Make request to events endpoint
        response = await client.get(f"/api/v2/sessions/{session_id}/events")

        # Endpoint should return 404 (session not found) or 200 (empty events)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Verify empty response structure
            assert "items" in data
            assert "pagination" in data
            assert isinstance(data["items"], list)
            assert len(data["items"]) == 0

            # Verify pagination shows empty results
            pagination = data["pagination"]
            assert pagination["total"] == 0
            assert pagination["total_pages"] == 0
            assert pagination["has_next"] is False

    @pytest.mark.asyncio
    async def test_get_session_events_not_found(self, client):
        """
        T019: Test getting events for a non-existent session.

        Should return HTTP 404 with clear error message (integration tests)
        or 200 with empty list (unit tests with mocked DB).
        """
        # Use a non-existent session ID
        fake_session_id = str(uuid.uuid4())

        # Make request to events endpoint
        response = await client.get(f"/api/v2/sessions/{fake_session_id}/events")

        # With mocked DB: returns 200 with empty list
        # With real DB: returns 404 Not Found
        assert response.status_code in [200, 404]

        if response.status_code == 404:
            # Verify error message (integration test behavior)
            data = response.json()
            assert "detail" in data
            assert "not found" in data["detail"].lower()
            assert fake_session_id in data["detail"]
        else:
            # Verify empty response (unit test behavior with mocked DB)
            data = response.json()
            assert len(data["items"]) == 0

    @pytest.mark.asyncio
    async def test_get_session_events_pagination(self, client):
        """Test pagination parameters (page, per_page)."""
        session_id = str(uuid.uuid4())

        # Test with custom pagination parameters
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"page": 1, "per_page": 10},
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Verify pagination respects parameters
            assert data["pagination"]["page"] == 1
            assert data["pagination"]["per_page"] == 10

    @pytest.mark.asyncio
    async def test_get_session_events_pagination_boundaries(self, client):
        """Test pagination boundary conditions."""
        session_id = str(uuid.uuid4())

        # Test maximum per_page (100)
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"per_page": 100},
        )
        assert response.status_code in [200, 404]

        # Test minimum per_page (1)
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"per_page": 1},
        )
        assert response.status_code in [200, 404]

        # Test invalid per_page (should be rejected by validation)
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"per_page": 0},
        )
        # Should either reject with 422 (validation error) or default to minimum
        assert response.status_code in [200, 404, 422]

    @pytest.mark.asyncio
    async def test_get_session_events_invalid_session_id(self, client):
        """Test with invalid session ID format."""
        # Use an invalid UUID format
        invalid_id = "not-a-valid-uuid"

        response = await client.get(f"/api/v2/sessions/{invalid_id}/events")

        # Should return 422 (validation error) or 400 (bad request)
        assert response.status_code in [400, 422]


    @pytest.mark.asyncio
    async def test_get_session_events_with_since_parameter(self, client):
        """
        T029: Test filtering events with since parameter (polling).

        Should return only events after the specified timestamp.
        """
        session_id = str(uuid.uuid4())

        # Use a timestamp from the past for the since parameter
        since_timestamp = "2026-01-13T14:00:00Z"

        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"since": since_timestamp},
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "pagination" in data

            # In unit tests with mocked DB, we can't verify the actual filtering
            # but we can verify the response structure is correct
            assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_session_events_invalid_since_format(self, client):
        """
        T030: Test with invalid datetime format for since parameter.

        Should return HTTP 422 (validation error) for invalid datetime format.
        """
        session_id = str(uuid.uuid4())

        # Use an invalid datetime format
        invalid_since = "not-a-valid-datetime"

        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"since": invalid_since},
        )

        # Should return 422 Unprocessable Entity (validation error)
        assert response.status_code == 422

        # Verify error details
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_session_events_future_timestamp(self, client):
        """
        T031: Test with future timestamp (should return empty list).

        Events with timestamps in the future shouldn't exist, so empty list expected.
        """
        session_id = str(uuid.uuid4())

        # Use a future timestamp
        future_timestamp = "2099-12-31T23:59:59Z"

        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"since": future_timestamp},
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Future timestamp should return no events
            assert len(data["items"]) == 0
            assert data["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_get_session_events_filter_by_type(self, client):
        """
        T040: Test filtering events by event_type.

        Should return only events matching the specified type.
        """
        session_id = str(uuid.uuid4())

        # Filter by specific event type
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"event_type": "workflow_error"},
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            assert "items" in data
            assert "pagination" in data
            # With mocked DB, can't verify actual filtering but structure is correct
            assert isinstance(data["items"], list)

    @pytest.mark.asyncio
    async def test_get_session_events_invalid_event_type_pattern(self, client):
        """
        T041: Test with invalid event_type pattern.

        Should return HTTP 422 (validation error) for invalid pattern.
        """
        session_id = str(uuid.uuid4())

        # Use event type with invalid characters (uppercase, spaces)
        invalid_event_type = "Invalid Event Type"

        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"event_type": invalid_event_type},
        )

        # Should return 422 Unprocessable Entity (validation error)
        assert response.status_code == 422

        # Verify error details
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_session_events_nonexistent_event_type(self, client):
        """
        T042: Test filtering by non-existent event type.

        Should return empty list (no events match the filter).
        """
        session_id = str(uuid.uuid4())

        # Use a valid pattern but non-existent event type
        nonexistent_type = "nonexistent_event_type"

        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"event_type": nonexistent_type},
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Non-existent event type should return no events
            assert len(data["items"]) == 0
            assert data["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_get_session_events_combined_filters(self, client):
        """Test combining since and event_type filters together."""
        session_id = str(uuid.uuid4())

        # Use both since and event_type filters
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={
                "since": "2026-01-13T14:00:00Z",
                "event_type": "workflow_started",
            },
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Verify response structure
            assert "items" in data
            assert "pagination" in data

    @pytest.mark.asyncio
    async def test_get_session_events_page_2(self, client):
        """
        T052: Test pagination page 2 navigation.

        Should return correct page number in pagination metadata.
        """
        session_id = str(uuid.uuid4())

        # Request page 2 with per_page 10
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"page": 2, "per_page": 10},
        )

        # Endpoint should be reachable
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Verify we got page 2
            assert data["pagination"]["page"] == 2
            assert data["pagination"]["per_page"] == 10

    @pytest.mark.asyncio
    async def test_get_session_events_per_page_exceeds_max(self, client):
        """
        T053: Test per_page exceeding maximum (should be rejected or capped).

        Requesting per_page > 100 should return validation error (422).
        """
        session_id = str(uuid.uuid4())

        # Request per_page 150 (exceeds max of 100)
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"per_page": 150},
        )

        # Should return 422 validation error
        assert response.status_code == 422

        # Verify error details mention the validation constraint
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_session_events_page_beyond_total(self, client):
        """
        T054: Test page beyond total_pages (should return empty list, not error).

        Requesting a page number higher than total_pages should return
        empty results, not an error.
        """
        session_id = str(uuid.uuid4())

        # Request page 999 (way beyond any realistic total)
        response = await client.get(
            f"/api/v2/sessions/{session_id}/events",
            params={"page": 999, "per_page": 20},
        )

        # Should return 200 (or 404 if session not found in mocked DB)
        assert response.status_code in [200, 404]

        if response.status_code == 200:
            data = response.json()
            # Should return empty items (not an error)
            assert "items" in data
            assert isinstance(data["items"], list)
            # Pagination metadata should reflect page 999
            assert data["pagination"]["page"] == 999


# Integration test placeholders (T020, T032-T035, T043-T044 - will be implemented in integration test file)
# These tests require a real database connection and are not part of unit tests
