# API Authentication

Documentation for TestBoost API authentication.

## X-API-Key Authentication (CHK024)

### Key Format

API keys follow a structured format for identification and validation:

```
tb_{environment}_{random_bytes}

Format: tb_[env]_[32 hex characters]
Length: 40 characters total
```

**Examples**:
- Production: `tb_prod_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4`
- Staging: `tb_stag_f1e2d3c4b5a6f1e2d3c4b5a6f1e2d3c4`
- Development: `tb_dev_0123456789abcdef0123456789abcdef`

### Key Components

| Component | Format | Description |
|-----------|--------|-------------|
| Prefix | `tb_` | TestBoost identifier |
| Environment | `prod\|stag\|dev` | Deployment environment |
| Random | 32 hex chars | Cryptographically random |

### Validation Rules

1. **Length**: Must be exactly 40 characters
2. **Prefix**: Must start with `tb_`
3. **Environment**: Must be valid environment code
4. **Random**: Must be valid hexadecimal (0-9, a-f)

### Validation Regex

```python
import re

API_KEY_PATTERN = re.compile(r'^tb_(prod|stag|dev)_[a-f0-9]{32}$')

def validate_api_key(key: str) -> bool:
    """Validate API key format."""
    return bool(API_KEY_PATTERN.match(key))
```

## Request Authentication

### Header Format

```http
GET /api/v1/sessions HTTP/1.1
Host: api.testboost.example.com
X-API-Key: tb_prod_a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4
Content-Type: application/json
```

### Authentication Flow

```
┌─────────┐      ┌─────────────┐      ┌────────────┐
│ Client  │      │   FastAPI   │      │  Key Store │
└────┬────┘      └──────┬──────┘      └─────┬──────┘
     │                  │                    │
     │ Request + X-API-Key                   │
     │─────────────────>│                    │
     │                  │                    │
     │                  │ Validate format    │
     │                  │───────────────────>│
     │                  │                    │
     │                  │<───────────────────│
     │                  │   Key valid/invalid│
     │                  │                    │
     │  Response        │                    │
     │<─────────────────│                    │
     │                  │                    │
```

## Error Responses

### Missing API Key

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "authentication_required",
  "message": "X-API-Key header is required",
  "code": "AUTH001"
}
```

### Invalid Format

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "invalid_key_format",
  "message": "API key format is invalid",
  "code": "AUTH002"
}
```

### Expired Key

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "key_expired",
  "message": "API key has expired",
  "code": "AUTH003"
}
```

### Revoked Key

```http
HTTP/1.1 401 Unauthorized
Content-Type: application/json

{
  "error": "key_revoked",
  "message": "API key has been revoked",
  "code": "AUTH004"
}
```

## Key Management

### Key Generation

```python
import secrets

def generate_api_key(environment: str = "prod") -> str:
    """Generate a new API key."""
    random_bytes = secrets.token_hex(16)  # 32 hex characters
    return f"tb_{environment}_{random_bytes}"
```

### Key Storage

API keys are stored hashed:

```python
import hashlib

def hash_api_key(key: str) -> str:
    """Hash API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()
```

### Key Rotation

1. Generate new key
2. Add new key to allowed keys
3. Notify user of new key
4. Set expiration on old key (7 days)
5. Remove old key after expiration

## Rate Limiting

| Plan | Requests/min | Requests/day |
|------|--------------|--------------|
| Free | 60 | 1,000 |
| Pro | 600 | 50,000 |
| Enterprise | 6,000 | Unlimited |

### Rate Limit Headers

```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1704067200
```

### Rate Limit Exceeded

```http
HTTP/1.1 429 Too Many Requests
Content-Type: application/json
Retry-After: 60

{
  "error": "rate_limit_exceeded",
  "message": "Rate limit exceeded. Retry in 60 seconds.",
  "code": "RATE001"
}
```

## Security Best Practices

1. **Never log API keys**: Use key prefix only for logging
2. **Use environment variables**: Store keys in env vars, not code
3. **Rotate regularly**: Rotate keys every 90 days
4. **Limit scope**: Use environment-specific keys
5. **Monitor usage**: Alert on unusual patterns

## API Endpoints

### Session Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v2/sessions` | List all sessions |
| POST | `/api/v2/sessions` | Create new session |
| GET | `/api/v2/sessions/{session_id}` | Get session details |
| GET | `/api/v2/sessions/{session_id}/steps` | Get session steps |
| POST | `/api/v2/sessions/{session_id}/steps/{step_code}/execute` | Execute a step |
| POST | `/api/v2/sessions/{session_id}/pause` | Pause session |
| POST | `/api/v2/sessions/{session_id}/resume` | Resume session |
| GET | `/api/v2/sessions/{session_id}/artifacts` | Get session artifacts |
| DELETE | `/api/v2/sessions/{session_id}` | Cancel session |

### Security Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/audit/scan` | Scan for vulnerabilities |
| GET | `/api/audit/report/{session_id}` | Get audit report (JSON) |
| GET | `/api/audit/report/{session_id}/html` | Get audit report (HTML) |

**Example - Scan vulnerabilities**:
```http
POST /api/audit/scan HTTP/1.1
Host: localhost:8000
X-API-Key: tb_dev_0123456789abcdef0123456789abcdef
Content-Type: application/json

{
  "project_path": "/path/to/project",
  "severity": "high",
  "output_format": "json"
}
```

**Response**:
```json
{
  "success": true,
  "session_id": "abc123-def456",
  "project_path": "/path/to/project",
  "total_vulnerabilities": 2,
  "vulnerabilities": [
    {
      "cve": "CVE-2021-1234",
      "severity": "high",
      "dependency": "org.example:lib:1.0",
      "description": "Remote code execution vulnerability"
    }
  ],
  "summary": {
    "critical": 0,
    "high": 2,
    "medium": 0,
    "low": 0
  }
}
```

### Impact Analysis

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/testboost/tests/impact` | Analyze code change impact |

**Example - Analyze impact**:
```http
POST /api/testboost/tests/impact HTTP/1.1
Host: localhost:8000
X-API-Key: tb_dev_0123456789abcdef0123456789abcdef
Content-Type: application/json

{
  "project_path": "/path/to/project",
  "verbose": true
}
```

**Response**:
```json
{
  "success": true,
  "impacts": [
    {
      "file": "src/main/java/com/example/UserService.java",
      "change_category": "business_rule",
      "risk_level": "high",
      "required_tests": ["unit", "integration"],
      "test_requirements": [
        {
          "type": "nominal",
          "description": "Test user creation with valid data"
        }
      ]
    }
  ],
  "summary": {
    "total_files": 1,
    "high_risk": 1,
    "medium_risk": 0,
    "low_risk": 0
  }
}
```

### Test Generation

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/testboost/tests/analyze` | Analyze test coverage |
| POST | `/api/testboost/tests/generate` | Generate tests |

### Health & Metrics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/metrics/json` | Prometheus metrics (JSON) |
