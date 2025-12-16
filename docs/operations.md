# Operations Guide

Operations documentation for TestBoost production deployment.

## Performance Thresholds (CHK038)

### Response Time SLOs

| Operation | Target | Degraded | Critical |
|-----------|--------|----------|----------|
| Interactive operations | < 5s | 5-10s | > 10s |
| Docker deployment | < 5 min | 5-8 min | > 8 min |
| 200-class analysis | < 30s | 30-60s | > 60s |
| API response (p95) | < 200ms | 200-500ms | > 500ms |
| Session creation | < 1s | 1-3s | > 3s |

### Resource Thresholds

| Resource | Normal | Warning | Critical |
|----------|--------|---------|----------|
| CPU usage | < 70% | 70-85% | > 85% |
| Memory usage | < 80% | 80-90% | > 90% |
| DB connections | < 80% pool | 80-90% | > 90% |
| Disk usage | < 70% | 70-85% | > 85% |

### Alerting Configuration

```yaml
# Example Prometheus alerting rules
groups:
  - name: testboost-performance
    rules:
      - alert: HighResponseLatency
        expr: http_request_duration_seconds{quantile="0.95"} > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High API latency detected"

      - alert: CriticalResponseLatency
        expr: http_request_duration_seconds{quantile="0.95"} > 1.0
        for: 2m
        labels:
          severity: critical

      - alert: WorkflowTimeout
        expr: workflow_duration_seconds > 300
        for: 1m
        labels:
          severity: warning

      - alert: HighMemoryUsage
        expr: process_resident_memory_bytes / 1024^3 > 4
        for: 10m
        labels:
          severity: warning
```

## Load Testing Requirements (CHK039)

### Concurrent User Expectations

| Tier | Concurrent Sessions | API Requests/sec | DB Connections |
|------|---------------------|------------------|----------------|
| Small | 10 | 50 | 20 |
| Medium | 50 | 200 | 50 |
| Large | 200 | 500 | 100 |
| Enterprise | 500+ | 1000+ | 200+ |

### Resource Requirements by Scale

#### Small Deployment (10 concurrent sessions)

```yaml
api:
  replicas: 1
  resources:
    cpu: 1 core
    memory: 2 GB

database:
  pool_size: 20
  max_overflow: 10

workers:
  count: 2
  memory_per_worker: 1 GB
```

#### Medium Deployment (50 concurrent sessions)

```yaml
api:
  replicas: 2
  resources:
    cpu: 2 cores
    memory: 4 GB

database:
  pool_size: 50
  max_overflow: 25

workers:
  count: 4
  memory_per_worker: 2 GB
```

#### Large Deployment (200 concurrent sessions)

```yaml
api:
  replicas: 4
  resources:
    cpu: 4 cores
    memory: 8 GB

database:
  pool_size: 100
  max_overflow: 50

workers:
  count: 8
  memory_per_worker: 2 GB
```

### Load Test Scenarios

#### 1. Baseline Load Test

```bash
# Run with k6 or locust
# Target: 10 concurrent users for 10 minutes
k6 run --vus 10 --duration 10m tests/load/baseline.js
```

Expected results:
- p95 latency < 500ms
- Error rate < 0.1%
- No memory leaks

#### 2. Stress Test

```bash
# Ramp up to find breaking point
k6 run --stage 1m:10,5m:50,5m:100,5m:200 tests/load/stress.js
```

Expected results:
- System degrades gracefully
- No data corruption
- Recovery within 5 minutes after load reduction

#### 3. Endurance Test

```bash
# Sustained load for 4 hours
k6 run --vus 20 --duration 4h tests/load/endurance.js
```

Expected results:
- Memory stable (no leaks)
- Consistent response times
- No connection pool exhaustion

### Monitoring During Load Tests

Key metrics to monitor:

1. **Application Metrics**
   - `http_request_duration_seconds` - API latency
   - `workflow_duration_seconds` - Workflow execution time
   - `active_sessions` - Concurrent session count
   - `llm_calls_total` - LLM API usage

2. **System Metrics**
   - CPU utilization
   - Memory usage (RSS and heap)
   - Network I/O
   - Disk I/O

3. **Database Metrics**
   - Connection pool utilization
   - Query latency
   - Lock contention
   - Deadlock count

## Scheduled Jobs

### Session Purge Job

- **Schedule**: Daily at 2:00 AM UTC
- **Retention**: 365 days
- **Expected Duration**: < 5 minutes
- **Alert Threshold**: > 10 minutes

### Database Maintenance

- **VACUUM ANALYZE**: Weekly, Sunday 3:00 AM UTC
- **Index Rebuild**: Monthly, first Sunday 4:00 AM UTC
- **Statistics Update**: Daily at 3:00 AM UTC

## Incident Response

### Performance Degradation Playbook

1. **Check recent changes**
   - Review deployments in last 24h
   - Check configuration changes

2. **Identify bottleneck**
   - Check Prometheus metrics
   - Review slow query logs
   - Check external service status

3. **Immediate mitigation**
   - Scale horizontally if resource-constrained
   - Enable rate limiting if overloaded
   - Disable non-critical features

4. **Root cause analysis**
   - Collect logs and metrics
   - Reproduce in staging
   - Document findings

### Escalation Matrix

| Severity | Response Time | Escalation |
|----------|---------------|------------|
| Critical | 15 minutes | On-call + Team Lead |
| High | 1 hour | On-call |
| Medium | 4 hours | Next business day |
| Low | 24 hours | Sprint backlog |
