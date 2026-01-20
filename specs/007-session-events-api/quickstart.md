# Quickstart: Session Events API

**Feature**: 007-session-events-api
**Date**: 2026-01-13

## Overview

The Session Events API provides real-time access to workflow events through a simple REST endpoint with support for polling, filtering, and pagination. This guide shows you how to integrate event monitoring into your frontend or client application.

**Endpoint**: `GET /api/v2/sessions/{session_id}/events`

---

## Quick Examples

### 1. Get Recent Events (Initial Load)

Fetch the 50 most recent events for a session:

```bash
curl -X GET "http://localhost:8000/api/v2/sessions/123e4567-e89b-12d3-a456-426614174000/events?per_page=50" \
  -H "X-API-Key: your-api-key-here"
```

**Response**:
```json
{
  "items": [
    {
      "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "session_id": "123e4567-e89b-12d3-a456-426614174000",
      "step_id": null,
      "event_type": "workflow_completed",
      "event_data": {
        "workflow_type": "test_generation",
        "duration_seconds": 45.67,
        "tests_generated": 12
      },
      "message": "Test generation completed. Generated 12 tests.",
      "timestamp": "2026-01-13T14:30:45.123456Z"
    }
    // ... more events
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 156,
    "total_pages": 4,
    "has_next": true,
    "has_prev": false
  }
}
```

---

### 2. Poll for New Events (Real-Time Monitoring)

After initial load, poll every 2 seconds for new events:

```bash
# Get timestamp of newest event from previous response
LAST_TIMESTAMP="2026-01-13T14:30:45.123456Z"

# Poll for events since that timestamp
curl -X GET "http://localhost:8000/api/v2/sessions/123e4567-e89b-12d3-a456-426614174000/events?since=$LAST_TIMESTAMP&per_page=50" \
  -H "X-API-Key: your-api-key-here"
```

**Response** (only new events):
```json
{
  "items": [
    {
      "id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "event_type": "status_changed",
      "event_data": {
        "old_status": "running",
        "new_status": "completed"
      },
      "timestamp": "2026-01-13T14:31:00.456789Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

### 3. Filter by Event Type (Troubleshooting)

Get only error events to diagnose issues:

```bash
curl -X GET "http://localhost:8000/api/v2/sessions/123e4567-e89b-12d3-a456-426614174000/events?event_type=workflow_error" \
  -H "X-API-Key: your-api-key-here"
```

**Response**:
```json
{
  "items": [
    {
      "id": "d4e5f6a7-b8c9-0123-def0-123456789abc",
      "event_type": "workflow_error",
      "event_data": {
        "error": "LLM API rate limit exceeded",
        "error_type": "LLMRateLimitError",
        "recoverable": true,
        "retry_after": 60
      },
      "message": "LLM API rate limit exceeded. Retrying in 60 seconds.",
      "timestamp": "2026-01-13T14:25:30.123456Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

---

## Frontend Integration

### React/JavaScript Example

```javascript
import { useState, useEffect } from 'react';

function SessionEvents({ sessionId }) {
  const [events, setEvents] = useState([]);
  const [lastTimestamp, setLastTimestamp] = useState(null);
  const [loading, setLoading] = useState(true);

  // Initial load
  useEffect(() => {
    fetchEvents();
  }, [sessionId]);

  // Polling for new events
  useEffect(() => {
    if (!lastTimestamp) return; // Skip until initial load completes

    const pollInterval = setInterval(() => {
      fetchNewEvents();
    }, 2000); // Poll every 2 seconds

    return () => clearInterval(pollInterval);
  }, [lastTimestamp]);

  async function fetchEvents() {
    setLoading(true);
    try {
      const response = await fetch(
        `/api/v2/sessions/${sessionId}/events?per_page=100`,
        {
          headers: { 'X-API-Key': 'your-api-key-here' }
        }
      );
      const data = await response.json();

      setEvents(data.items);
      if (data.items.length > 0) {
        setLastTimestamp(data.items[0].timestamp); // Newest event (descending order)
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
    } finally {
      setLoading(false);
    }
  }

  async function fetchNewEvents() {
    try {
      const response = await fetch(
        `/api/v2/sessions/${sessionId}/events?since=${lastTimestamp}&per_page=50`,
        {
          headers: { 'X-API-Key': 'your-api-key-here' }
        }
      );
      const data = await response.json();

      if (data.items.length > 0) {
        setEvents(prev => [...data.items, ...prev]); // Prepend new events
        setLastTimestamp(data.items[0].timestamp);
      }
    } catch (error) {
      console.error('Failed to poll events:', error);
    }
  }

  if (loading) return <div>Loading events...</div>;

  return (
    <div className="events-container">
      <h2>Session Events</h2>
      <div className="events-list">
        {events.map(event => (
          <div key={event.id} className={`event event-${event.event_type}`}>
            <span className="timestamp">{new Date(event.timestamp).toLocaleString()}</span>
            <span className="type">{event.event_type}</span>
            <span className="message">{event.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
```

---

### Python Client Example

```python
import requests
from datetime import datetime
from time import sleep
from typing import List, Dict, Any

class SessionEventsClient:
    """Client for polling session events."""

    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url
        self.headers = {"X-API-Key": api_key}

    def get_events(
        self,
        session_id: str,
        since: str | None = None,
        event_type: str | None = None,
        page: int = 1,
        per_page: int = 20,
    ) -> Dict[str, Any]:
        """Fetch events for a session with optional filtering."""
        params = {
            "page": page,
            "per_page": per_page,
        }
        if since:
            params["since"] = since
        if event_type:
            params["event_type"] = event_type

        url = f"{self.base_url}/api/v2/sessions/{session_id}/events"
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def monitor_session(
        self,
        session_id: str,
        poll_interval: int = 2,
        event_callback: callable = None,
    ):
        """Monitor session events in real-time."""
        last_timestamp = None

        # Initial load
        print(f"Loading initial events for session {session_id}...")
        data = self.get_events(session_id, per_page=100)
        events = data["items"]

        if events:
            last_timestamp = events[0]["timestamp"]  # Newest event
            for event in reversed(events):  # Display oldest first
                if event_callback:
                    event_callback(event)
                else:
                    self._print_event(event)

        # Poll for new events
        print(f"\nPolling for new events every {poll_interval}s...")
        while True:
            sleep(poll_interval)

            data = self.get_events(session_id, since=last_timestamp, per_page=50)
            new_events = data["items"]

            if new_events:
                last_timestamp = new_events[0]["timestamp"]
                for event in reversed(new_events):
                    if event_callback:
                        event_callback(event)
                    else:
                        self._print_event(event)

    def _print_event(self, event: Dict[str, Any]):
        """Pretty print an event."""
        timestamp = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        print(f"[{timestamp.strftime('%H:%M:%S')}] {event['event_type']}: {event.get('message', 'No message')}")


# Usage example
if __name__ == "__main__":
    client = SessionEventsClient(
        base_url="http://localhost:8000",
        api_key="your-api-key-here"
    )

    # Monitor a session
    session_id = "123e4567-e89b-12d3-a456-426614174000"

    # Custom event handler
    def handle_event(event):
        if event["event_type"] == "workflow_error":
            print(f"⚠️  ERROR: {event['message']}")
        elif event["event_type"] == "workflow_completed":
            print(f"✅ COMPLETED: {event['message']}")
        else:
            print(f"ℹ️  {event['event_type']}: {event.get('message', '')}")

    client.monitor_session(session_id, poll_interval=2, event_callback=handle_event)
```

---

## Common Use Cases

### Use Case 1: Real-Time Progress Bar

Show workflow progress in a UI progress bar:

```javascript
async function updateProgressBar(sessionId) {
  const response = await fetch(`/api/v2/sessions/${sessionId}/events?per_page=1`);
  const data = await response.json();

  if (data.items.length > 0) {
    const latestEvent = data.items[0];

    // Update UI based on event type
    if (latestEvent.event_type === 'workflow_started') {
      progressBar.indeterminate = true;
      progressBar.label = 'Starting...';
    } else if (latestEvent.event_type === 'step_status_changed') {
      const { step_code, new_status } = latestEvent.event_data;
      progressBar.label = `${step_code}: ${new_status}`;
    } else if (latestEvent.event_type === 'workflow_completed') {
      progressBar.indeterminate = false;
      progressBar.value = 100;
      progressBar.label = 'Completed';
    }
  }
}
```

### Use Case 2: Error Alerting

Show toast notification when errors occur:

```javascript
async function checkForErrors(sessionId, lastCheckTimestamp) {
  const response = await fetch(
    `/api/v2/sessions/${sessionId}/events?event_type=workflow_error&since=${lastCheckTimestamp}`
  );
  const data = await response.json();

  data.items.forEach(event => {
    showToast({
      type: 'error',
      title: 'Workflow Error',
      message: event.message,
      duration: 5000,
    });
  });
}
```

### Use Case 3: Activity Log

Display full event log with filtering:

```javascript
function EventLog({ sessionId }) {
  const [filter, setFilter] = useState(null); // null = all events
  const [events, setEvents] = useState([]);

  async function fetchFilteredEvents(eventType) {
    const params = new URLSearchParams({
      per_page: 100,
      ...(eventType && { event_type: eventType })
    });

    const response = await fetch(
      `/api/v2/sessions/${sessionId}/events?${params}`,
      { headers: { 'X-API-Key': 'your-api-key-here' } }
    );
    const data = await response.json();
    setEvents(data.items);
  }

  return (
    <div>
      <div className="filters">
        <button onClick={() => { setFilter(null); fetchFilteredEvents(); }}>
          All Events
        </button>
        <button onClick={() => { setFilter('workflow_error'); fetchFilteredEvents('workflow_error'); }}>
          Errors Only
        </button>
        <button onClick={() => { setFilter('status_changed'); fetchFilteredEvents('status_changed'); }}>
          Status Changes
        </button>
      </div>

      <div className="events">
        {events.map(event => (
          <EventRow key={event.id} event={event} />
        ))}
      </div>
    </div>
  );
}
```

---

## Query Parameters Reference

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `page` | integer | No | 1 | Page number (1-indexed) |
| `per_page` | integer | No | 20 | Items per page (max 100) |
| `since` | datetime | No | - | Filter events after this timestamp (ISO 8601) |
| `event_type` | string | No | - | Filter by event type (e.g., "workflow_error") |

**Pagination Behavior**:
- Events are returned in **descending order** (newest first)
- `page=1` returns the most recent events
- `has_next=true` indicates more pages available
- If `page` exceeds `total_pages`, returns empty `items` array (not an error)

**Filtering Behavior**:
- `since` filters events where `timestamp > since` (exclusive)
- `event_type` matches exact event type (case-sensitive)
- Filters are combined with AND logic
- Empty result set if no events match filters

---

## Error Handling

### HTTP 404 - Session Not Found

```json
{
  "detail": "Session not found: 123e4567-e89b-12d3-a456-426614174000"
}
```

**Resolution**: Verify session ID exists. Check `/api/v2/sessions` endpoint.

---

### HTTP 400 - Invalid since Parameter

```json
{
  "detail": "Invalid datetime format for 'since' parameter. Expected ISO 8601 format (e.g., 2026-01-13T14:30:00Z)"
}
```

**Resolution**: Ensure `since` parameter uses ISO 8601 format with timezone.

**Valid formats**:
- `2026-01-13T14:30:00Z` (UTC)
- `2026-01-13T14:30:00+00:00` (Timezone-aware)
- `2026-01-13T14:30:00.123456Z` (With microseconds)

---

### HTTP 400 - Invalid Pagination

```json
{
  "detail": "per_page must be between 1 and 100"
}
```

**Resolution**: Adjust `per_page` to be within 1-100 range.

---

## Performance Tips

### 1. Use Appropriate Polling Intervals

- **Active sessions**: Poll every 2 seconds for real-time updates
- **Completed sessions**: No polling needed (load once)
- **Long-running sessions**: Consider 5-second interval to reduce server load

### 2. Optimize Initial Load

- Use `per_page=50` or `per_page=100` for initial load to get sufficient history
- Don't fetch entire event log at once (use pagination)

### 3. Filter Strategically

- Use `event_type` filter to reduce response size when you only need specific events
- Use `since` parameter for polling to avoid re-fetching same events

### 4. Cache Results

- Cache events in frontend state to avoid redundant API calls
- Only fetch new events using `since` parameter

---

## Event Types Reference

| Event Type | Description | When Emitted |
|------------|-------------|--------------|
| `session_created` | Session initialized | Session creation |
| `status_changed` | Session status changed | Status transitions |
| `step_created` | Step created | Workflow step initialization |
| `step_status_changed` | Step status changed | Step execution progress |
| `artifact_created` | Artifact generated | File/report creation |
| `workflow_started` | Workflow began | Workflow start |
| `workflow_resumed` | Workflow resumed | After pause/checkpoint |
| `workflow_paused` | Workflow paused | Manual pause or checkpoint |
| `workflow_completed` | Workflow succeeded | Successful completion |
| `workflow_failed` | Workflow failed | Failure outcome |
| `workflow_error` | Workflow error occurred | Error during execution |

**Common event_data Fields**:
- `duration_seconds`: Operation duration
- `old_status`, `new_status`: State transitions
- `error`, `error_type`: Error information
- `step_code`: Step identifier
- `artifact_id`: Created artifact

---

## Testing

### Manual Testing with curl

```bash
# Test 1: Get recent events
curl -X GET "http://localhost:8000/api/v2/sessions/{session_id}/events?per_page=10" \
  -H "X-API-Key: test-key"

# Test 2: Filter by event type
curl -X GET "http://localhost:8000/api/v2/sessions/{session_id}/events?event_type=workflow_error" \
  -H "X-API-Key: test-key"

# Test 3: Poll for new events
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
curl -X GET "http://localhost:8000/api/v2/sessions/{session_id}/events?since=$TIMESTAMP" \
  -H "X-API-Key: test-key"

# Test 4: Pagination
curl -X GET "http://localhost:8000/api/v2/sessions/{session_id}/events?page=2&per_page=20" \
  -H "X-API-Key: test-key"
```

---

## Next Steps

1. **Implement endpoint**: Follow the contract in `contracts/events-api.yaml`
2. **Write tests**: See test plans in feature specification
3. **Integrate frontend**: Use the React/JavaScript examples above
4. **Monitor performance**: Track response times and optimize as needed

For detailed implementation guidance, see:
- **Data Model**: `data-model.md`
- **API Contract**: `contracts/events-api.yaml`
- **Feature Spec**: `spec.md`
