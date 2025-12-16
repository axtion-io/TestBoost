# External Dependencies

Documentation of external service dependencies and availability assumptions (CHK078, CHK079).

## Service Dependency Matrix

| Service | Purpose | Required | SLA Target | Fallback Behavior |
|---------|---------|----------|------------|-------------------|
| PostgreSQL | Data persistence | Yes | 99.9% | Retry with backoff, fail gracefully |
| Google Gemini API | LLM inference | Yes | 99.5% | Queue requests, retry, degrade |
| Docker Engine | Container execution | Yes | 99.9% | Queue jobs, alert operators |
| Maven Central | Dependency resolution | No | 99.0% | Use cached metadata |
| GitHub API | Repository operations | No | 99.5% | Cache results, retry |

## LLM Provider Dependencies

### Google Gemini (Primary)

**Service**: `generativelanguage.googleapis.com`

| Metric | Expected | Degraded | Action |
|--------|----------|----------|--------|
| Latency (p95) | < 5s | 5-15s | Log warning, continue |
| Latency (p99) | < 10s | 10-30s | Log error, may timeout |
| Error rate | < 1% | 1-5% | Retry with exponential backoff |
| Availability | 99.5% | < 99% | Queue requests, alert |

**Fallback Strategy**:
1. Retry failed requests up to 3 times with exponential backoff
2. Queue requests during transient outages (up to 5 minutes)
3. Return cached results where applicable
4. Degrade to simpler analysis if LLM unavailable

**Rate Limits**:
- Requests per minute: 60 (free tier) / 1000 (paid)
- Tokens per minute: 60,000 (free) / 1,000,000 (paid)
- Implement client-side rate limiting at 80% of quota

### Provider Switching (Future)

```python
# Configuration for multi-provider support
llm_config:
  primary:
    provider: google-genai
    model: gemini-2.0-flash
  fallback:
    provider: openai  # Future support
    model: gpt-4o-mini
  failover_threshold: 3  # Switch after 3 consecutive failures
```

## Database Dependencies

### PostgreSQL

**Connection**: Port 5433 (custom port)

| Metric | Expected | Degraded | Critical |
|--------|----------|----------|----------|
| Connection latency | < 10ms | 10-50ms | > 50ms |
| Query latency (p95) | < 100ms | 100-500ms | > 500ms |
| Connection pool | < 80% | 80-90% | > 90% |
| Availability | 99.9% | 99-99.9% | < 99% |

**Fallback Strategy**:
1. Connection pool recovery with exponential backoff
2. Read replicas for read-heavy operations (future)
3. Graceful degradation: queue writes, serve cached reads
4. Circuit breaker after 5 consecutive failures

**Health Check**:
```python
async def check_db_health() -> bool:
    """Check database connectivity and performance."""
    try:
        start = time.time()
        await db.execute("SELECT 1")
        latency = time.time() - start
        return latency < 0.1  # 100ms threshold
    except Exception:
        return False
```

## Container Runtime Dependencies

### Docker Engine

**Socket**: `/var/run/docker.sock` or TCP

| Metric | Expected | Degraded | Action |
|--------|----------|----------|--------|
| Container start | < 5s | 5-15s | Log warning |
| Image pull | < 60s | 60-180s | Use cached images |
| API latency | < 100ms | 100-500ms | Log warning |
| Availability | 99.9% | < 99.9% | Queue jobs |

**Fallback Strategy**:
1. Prefer cached images over fresh pulls
2. Queue container jobs during Docker unavailability
3. Implement job timeout and cleanup
4. Alert operators after 3 failed container operations

**Resource Limits**:
```yaml
container_defaults:
  memory_limit: 2g
  cpu_limit: 2.0
  timeout: 300s
  cleanup_on_exit: true
```

## External Repository Dependencies

### Maven Central

**URL**: `https://repo.maven.apache.org/maven2`

| Metric | Expected | Degraded | Action |
|--------|----------|----------|--------|
| Metadata fetch | < 2s | 2-10s | Use cache |
| Artifact download | < 30s | 30-120s | Continue with warning |
| Availability | 99.0% | < 99% | Use local cache |

**Fallback Strategy**:
1. Cache dependency metadata locally (TTL: 24h)
2. Use mirror repositories if primary unavailable
3. Proceed with cached data, flag as potentially stale
4. Alert on metadata older than 7 days

### GitHub API

**URL**: `https://api.github.com`

| Metric | Expected | Degraded | Action |
|--------|----------|----------|--------|
| API latency | < 500ms | 500ms-2s | Log warning |
| Rate limit | 5000/hr | < 1000/hr | Queue requests |
| Availability | 99.5% | < 99.5% | Use cached data |

**Fallback Strategy**:
1. Cache API responses (TTL varies by endpoint)
2. Implement request queuing during rate limiting
3. Fall back to git CLI operations where possible
4. Alert when rate limit below 10%

## Dependency Health Monitoring

### Health Check Endpoints

```
GET /health           # Basic liveness
GET /health/ready     # Full readiness (all deps)
GET /health/deps      # Individual dependency status
```

**Response Format**:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00Z",
  "dependencies": {
    "database": {
      "status": "healthy",
      "latency_ms": 5,
      "last_check": "2024-01-01T00:00:00Z"
    },
    "llm_api": {
      "status": "healthy",
      "latency_ms": 1200,
      "last_check": "2024-01-01T00:00:00Z"
    },
    "docker": {
      "status": "healthy",
      "version": "24.0.7",
      "last_check": "2024-01-01T00:00:00Z"
    }
  }
}
```

### Monitoring Integration

```yaml
# Prometheus metrics for dependency health
metrics:
  - name: dependency_health
    type: gauge
    labels: [service, status]

  - name: dependency_latency_seconds
    type: histogram
    labels: [service]
    buckets: [0.01, 0.05, 0.1, 0.5, 1, 5, 10]

  - name: dependency_errors_total
    type: counter
    labels: [service, error_type]
```

## Degradation Modes

### Mode 1: LLM Unavailable

**Behavior**:
- Queue new analysis requests (up to 5 min)
- Return cached results where available
- Display "analysis pending" status
- Alert operations team

**User Impact**: Delayed analysis results

### Mode 2: Database Unavailable

**Behavior**:
- Serve cached session data
- Queue new sessions in memory
- Disable session persistence temporarily
- Alert with high severity

**User Impact**: Session history unavailable, new sessions delayed

### Mode 3: Docker Unavailable

**Behavior**:
- Queue deployment jobs
- Disable containerized builds
- Fall back to local execution (if safe)
- Alert operations team

**User Impact**: Deployment features unavailable

### Mode 4: Full Degradation

**Behavior**:
- Return health check failure
- Display maintenance page
- Log all requests for replay
- Emergency alert to all stakeholders

**User Impact**: Service temporarily unavailable

## Recovery Procedures

### Automatic Recovery

1. **Connection Retry**: Exponential backoff (0.5s, 1s, 2s, 4s, max 30s)
2. **Circuit Breaker**: Open after 5 failures, half-open after 60s
3. **Health Check**: Every 10 seconds during degradation
4. **Auto-Resume**: When health check passes 3 consecutive times

### Manual Recovery

1. **Force Reconnect**: `POST /admin/reconnect/{service}`
2. **Clear Cache**: `POST /admin/cache/clear`
3. **Reset Circuit Breaker**: `POST /admin/circuit-breaker/reset`
4. **Drain Queue**: `POST /admin/queue/drain`
