# API Error Reference

**Purpose**: Complete reference for API error codes and responses
**Version**: 1.0.0

---

## Error Response Format

All API errors follow a consistent JSON format:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Human-readable error description",
  "context": {
    "field": "project_path",
    "details": "Path does not exist"
  },
  "request_id": "req-abc-123"
}
```

---

## HTTP Status Codes

### 2xx Success

| Code | Name | Description |
|------|------|-------------|
| 200 | OK | Request succeeded |
| 201 | Created | Resource created successfully |
| 202 | Accepted | Request accepted for async processing |
| 204 | No Content | Success with no response body |

### 4xx Client Errors

| Code | Name | Error Code | Description |
|------|------|------------|-------------|
| 400 | Bad Request | VALIDATION_ERROR | Invalid request parameters |
| 401 | Unauthorized | AUTHENTICATION_ERROR | Missing or invalid API key |
| 403 | Forbidden | PERMISSION_DENIED | Access denied to resource |
| 404 | Not Found | NOT_FOUND | Resource does not exist |
| 409 | Conflict | CONFLICT | Resource conflict (e.g., locked project) |
| 422 | Unprocessable Entity | VALIDATION_ERROR | Semantic validation failed |
| 429 | Too Many Requests | RATE_LIMIT | Rate limit exceeded |

### 5xx Server Errors

| Code | Name | Error Code | Description |
|------|------|------------|-------------|
| 500 | Internal Server Error | INTERNAL_ERROR | Unexpected server error |
| 502 | Bad Gateway | UPSTREAM_ERROR | External service error |
| 503 | Service Unavailable | SERVICE_UNAVAILABLE | Service temporarily unavailable |
| 504 | Gateway Timeout | TIMEOUT | Request timed out |

---

## Error Codes by Category

### Authentication Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| AUTHENTICATION_ERROR | 401 | API key missing | Add X-API-Key header |
| INVALID_API_KEY | 401 | API key invalid | Check API key format |
| API_KEY_EXPIRED | 401 | API key expired | Generate new API key |

**Example**:
```json
{
  "error_code": "AUTHENTICATION_ERROR",
  "message": "API key is required",
  "context": {
    "header": "X-API-Key"
  }
}
```

### Validation Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| VALIDATION_ERROR | 400 | Field validation failed | Check field constraints |
| INVALID_JSON | 400 | Request body not valid JSON | Fix JSON syntax |
| MISSING_FIELD | 400 | Required field missing | Add required field |
| INVALID_FIELD_TYPE | 400 | Field type mismatch | Use correct type |
| INVALID_ENUM | 400 | Value not in allowed set | Use allowed value |

**Example**:
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Invalid session type",
  "context": {
    "field": "session_type",
    "value": "invalid",
    "allowed": ["maven_maintenance", "test_generation", "docker_deployment"]
  }
}
```

### Resource Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| NOT_FOUND | 404 | Resource not found | Check resource ID |
| SESSION_NOT_FOUND | 404 | Session does not exist | Verify session ID |
| PROJECT_NOT_FOUND | 404 | Project path invalid | Check project path |
| ARTIFACT_NOT_FOUND | 404 | Artifact not found | Check artifact ID |

**Example**:
```json
{
  "error_code": "SESSION_NOT_FOUND",
  "message": "Session not found: abc-123",
  "context": {
    "resource_type": "session",
    "resource_id": "abc-123"
  }
}
```

### Conflict Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| CONFLICT | 409 | Generic conflict | Check current state |
| PROJECT_LOCKED | 409 | Project already in use | Wait or cancel existing session |
| SESSION_IN_PROGRESS | 409 | Session already running | Wait for completion |
| DUPLICATE_RESOURCE | 409 | Resource already exists | Use existing or update |

**Example**:
```json
{
  "error_code": "PROJECT_LOCKED",
  "message": "Project is locked by another session",
  "context": {
    "project_path": "/path/to/project",
    "locked_by_session": "session-xyz-789",
    "locked_since": "2024-01-15T10:30:00Z"
  }
}
```

### Rate Limiting Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| RATE_LIMIT | 429 | Request rate exceeded | Wait and retry |
| LLM_RATE_LIMIT | 429 | LLM API rate exceeded | Wait for reset |

**Example**:
```json
{
  "error_code": "RATE_LIMIT",
  "message": "Rate limit exceeded",
  "context": {
    "retry_after_seconds": 60,
    "limit": 100,
    "window": "minute"
  }
}
```

### Timeout Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| TIMEOUT | 504 | Operation timed out | Increase timeout or simplify |
| LLM_TIMEOUT | 504 | LLM request timed out | Retry or reduce context |

**Example**:
```json
{
  "error_code": "TIMEOUT",
  "message": "Operation timed out after 300 seconds",
  "context": {
    "operation": "maven_test",
    "timeout_seconds": 300
  }
}
```

### LLM Errors

| Error Code | HTTP Status | Description | Resolution |
|------------|-------------|-------------|------------|
| LLM_ERROR | 502 | LLM API error | Check provider status |
| LLM_INVALID_KEY | 401 | LLM API key invalid | Update API key |
| LLM_QUOTA_EXCEEDED | 429 | LLM quota exhausted | Upgrade plan or wait |
| LLM_CONTEXT_OVERFLOW | 400 | Context too large | Reduce input size |

**Example**:
```json
{
  "error_code": "LLM_CONTEXT_OVERFLOW",
  "message": "Context window exceeded (>170k tokens)",
  "context": {
    "tokens_requested": 175000,
    "max_tokens": 170000
  }
}
```

---

## Endpoint-Specific Errors

### POST /sessions

| Error | Cause | Resolution |
|-------|-------|------------|
| VALIDATION_ERROR | Invalid session_type | Use allowed type |
| PROJECT_NOT_FOUND | project_path invalid | Check path exists |
| PROJECT_LOCKED | Project in use | Wait or cancel |

### GET /sessions/{id}

| Error | Cause | Resolution |
|-------|-------|------------|
| SESSION_NOT_FOUND | Invalid session ID | Check ID |
| AUTHENTICATION_ERROR | Missing API key | Add header |

### POST /sessions/{id}/start

| Error | Cause | Resolution |
|-------|-------|------------|
| SESSION_NOT_FOUND | Invalid session ID | Check ID |
| SESSION_IN_PROGRESS | Already running | Wait |
| LLM_ERROR | LLM unavailable | Retry later |

### POST /sessions/{id}/cancel

| Error | Cause | Resolution |
|-------|-------|------------|
| SESSION_NOT_FOUND | Invalid session ID | Check ID |
| CONFLICT | Cannot cancel in current state | Check session status |

---

## Retry Recommendations

| Error Code | Retry? | Backoff | Notes |
|------------|--------|---------|-------|
| RATE_LIMIT | Yes | Exponential | Respect retry_after |
| TIMEOUT | Yes | Linear | Increase timeout |
| LLM_RATE_LIMIT | Yes | Exponential | Wait for reset |
| LLM_ERROR | Yes | Exponential | May be transient |
| INTERNAL_ERROR | Maybe | Exponential | If persistent, contact support |
| VALIDATION_ERROR | No | - | Fix request |
| NOT_FOUND | No | - | Check resource |
| PROJECT_LOCKED | Yes | Poll | Check lock status |
