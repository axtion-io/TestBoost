# Docker Isolation

Documentation for Docker container isolation and resource management.

## Container Resource Limits (CHK052)

### Default Resource Limits

All Maven execution containers run with the following default limits:

| Resource | Default | Min | Max |
|----------|---------|-----|-----|
| Memory | 2 GB | 512 MB | 8 GB |
| CPU | 2.0 cores | 0.5 | 4.0 |
| Disk | 10 GB | 1 GB | 50 GB |
| Network | bridge | - | - |
| PIDs | 256 | 64 | 1024 |

### Memory Configuration

```yaml
# In docker-compose or container config
services:
  maven-executor:
    image: maven:3.9-eclipse-temurin-17
    mem_limit: 2g
    mem_reservation: 512m
    memswap_limit: 3g  # Total memory + swap
```

### CPU Configuration

```yaml
services:
  maven-executor:
    cpus: 2.0          # Max CPU cores
    cpu_shares: 1024   # Relative weight
```

### Disk Limits

```yaml
services:
  maven-executor:
    storage_opt:
      size: '10G'
    tmpfs:
      - /tmp:size=512M
```

### Per-Operation Overrides

Operations can request adjusted limits:

| Operation | Memory | CPU | Timeout |
|-----------|--------|-----|---------|
| Compile | 2 GB | 2.0 | 120s |
| Test | 4 GB | 2.0 | 300s |
| Package | 2 GB | 1.0 | 180s |
| Deploy | 1 GB | 1.0 | 300s |

## Container Cleanup Policy (CHK053)

### Lifecycle States

```
Created -> Running -> Exited -> Removed
           |    ^
           v    |
         Paused
```

### Automatic Cleanup Triggers

| Trigger | Condition | Action |
|---------|-----------|--------|
| Success | Exit code 0 | Immediate removal |
| Failure | Exit code != 0 | Preserve 1 hour for debugging |
| Timeout | Exceeds timeout | Force kill, preserve logs |
| Orphan | No session reference | Remove after 15 minutes |
| Stale | Running > 1 hour | Alert, kill if > 2 hours |

### Cleanup Implementation

```python
async def cleanup_container(container_id: str, force: bool = False) -> None:
    """Clean up a container and its resources."""
    container = docker_client.containers.get(container_id)

    # 1. Stop container gracefully (10s timeout)
    if container.status == "running":
        container.stop(timeout=10)

    # 2. Copy logs before removal
    logs = container.logs()
    await save_container_logs(container_id, logs)

    # 3. Remove container
    container.remove(force=force)

    # 4. Clean up volumes if not shared
    for volume in container.attrs['Mounts']:
        if volume['Type'] == 'volume':
            await cleanup_volume_if_orphan(volume['Name'])
```

### Volume Cleanup

```yaml
# Volumes are cleaned up based on policy
volume_policy:
  maven_cache:
    type: shared
    cleanup: never  # Shared across containers

  build_output:
    type: ephemeral
    cleanup: on_container_exit

  logs:
    type: persistent
    cleanup: after_days(7)
```

### Scheduled Cleanup Job

```python
# Runs every 15 minutes
async def scheduled_cleanup() -> CleanupResult:
    """Periodic container cleanup."""
    cleaned = []

    # 1. Find exited containers
    exited = docker_client.containers.list(
        filters={"status": "exited"}
    )

    for container in exited:
        age = datetime.now() - container.attrs['State']['FinishedAt']

        # Successful containers: immediate cleanup
        if container.attrs['State']['ExitCode'] == 0:
            await cleanup_container(container.id)
            cleaned.append(container.id)

        # Failed containers: keep for 1 hour
        elif age > timedelta(hours=1):
            await cleanup_container(container.id)
            cleaned.append(container.id)

    # 2. Find orphan volumes
    volumes = docker_client.volumes.list()
    for volume in volumes:
        if not volume_in_use(volume) and volume_age(volume) > timedelta(hours=1):
            volume.remove()

    return CleanupResult(containers=cleaned)
```

## Security Isolation

### Network Isolation

```yaml
networks:
  testboost-internal:
    driver: bridge
    internal: true  # No external access

  maven-execution:
    driver: bridge
    internal: false  # Needs Maven Central access
    ipam:
      config:
        - subnet: 172.28.0.0/16
```

### Filesystem Isolation

```yaml
services:
  maven-executor:
    read_only: true  # Root filesystem read-only
    volumes:
      - type: tmpfs
        target: /tmp
      - type: bind
        source: ./project
        target: /workspace
        read_only: false  # Project needs write access
      - type: volume
        source: maven-cache
        target: /root/.m2
```

### Capability Restrictions

```yaml
services:
  maven-executor:
    cap_drop:
      - ALL
    cap_add:
      - CHOWN  # Needed for Maven
      - SETUID
      - SETGID
    security_opt:
      - no-new-privileges:true
```

## Resource Monitoring

### Container Metrics

Collected metrics for each container:

| Metric | Description | Alert Threshold |
|--------|-------------|-----------------|
| `cpu_percent` | CPU utilization | > 90% for 1 min |
| `memory_usage` | Memory in bytes | > 90% of limit |
| `memory_percent` | Memory utilization | > 85% |
| `network_rx` | Bytes received | N/A |
| `network_tx` | Bytes transmitted | N/A |
| `pids` | Process count | > 200 |

### Monitoring Integration

```python
async def collect_container_metrics(container_id: str) -> ContainerMetrics:
    """Collect metrics from running container."""
    stats = container.stats(stream=False)

    return ContainerMetrics(
        cpu_percent=calculate_cpu_percent(stats),
        memory_usage=stats['memory_stats']['usage'],
        memory_limit=stats['memory_stats']['limit'],
        network_rx=stats['networks']['eth0']['rx_bytes'],
        network_tx=stats['networks']['eth0']['tx_bytes'],
    )
```

## Error Handling

### OOM (Out of Memory)

```python
async def handle_oom(container_id: str, session_id: str) -> None:
    """Handle container OOM kill."""
    # 1. Record OOM event
    await record_event(session_id, "container_oom", container_id)

    # 2. Suggest increased memory
    recommendation = f"Container killed due to OOM. Consider increasing memory limit."

    # 3. Cleanup container
    await cleanup_container(container_id, force=True)

    # 4. Update session status
    await update_session_status(session_id, "failed", recommendation)
```

### Timeout Handling

```python
async def handle_timeout(container_id: str, timeout_seconds: int) -> None:
    """Handle container execution timeout."""
    # 1. Log timeout with context
    logger.warning("container_timeout", container_id=container_id, timeout=timeout_seconds)

    # 2. Capture final logs
    logs = docker_client.containers.get(container_id).logs(tail=1000)

    # 3. Force kill
    docker_client.containers.get(container_id).kill()

    # 4. Preserve for debugging (30 min)
    # Cleanup job will remove after 30 minutes
```
