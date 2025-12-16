# Maven Maintenance Workflow

Documentation for Maven dependency maintenance workflow.

## Overview

The Maven Maintenance workflow analyzes and updates Maven project dependencies with built-in safety validations.

## Circular Dependency Detection (CHK018)

### How Circular Dependencies Are Detected

TestBoost uses `mvn dependency:tree` to detect circular dependencies:

```bash
mvn dependency:tree -DverboseOptional -DoutputType=dot
```

### Detection Algorithm

1. Parse dependency tree output into directed graph
2. Perform depth-first search (DFS) for cycle detection
3. Return all cycles with participating artifacts

### Example Detection Output

```
Circular dependency detected:
  com.example:module-a:1.0.0
    -> com.example:module-b:1.0.0
    -> com.example:module-c:1.0.0
    -> com.example:module-a:1.0.0  [CYCLE]
```

### User Notification Strategy

When circular dependencies are detected:

1. **Immediate Notification**: Display warning in session output
2. **Detailed Report**: Generate dependency graph visualization
3. **Recommendations**: Suggest resolution strategies
   - Extract common interface module
   - Use dependency inversion
   - Restructure module boundaries

### Resolution Approaches

| Approach | When to Use | Complexity |
|----------|-------------|------------|
| Interface extraction | Tight coupling | Medium |
| Dependency inversion | Service dependencies | Low |
| Module merge | Small modules | Low |
| Event-based decoupling | Runtime coupling | High |

## Workflow States

```
┌─────────────┐
│   IDLE      │
└──────┬──────┘
       │ start_session
       ▼
┌─────────────┐
│  ANALYZING  │──────────────┐
└──────┬──────┘              │ error
       │ analysis_complete   │
       ▼                     ▼
┌─────────────┐        ┌─────────────┐
│  PLANNING   │        │   FAILED    │
└──────┬──────┘        └─────────────┘
       │ plan_approved       ▲
       ▼                     │
┌─────────────┐              │
│  UPDATING   │──────────────┘
└──────┬──────┘
       │ update_complete
       ▼
┌─────────────┐
│  TESTING    │──────────────┐
└──────┬──────┘              │ tests_failed
       │ tests_passed        │
       ▼                     ▼
┌─────────────┐        ┌─────────────┐
│ COMPLETED   │        │  ROLLBACK   │
└─────────────┘        └─────────────┘
```

## Dependency Update Strategy

### Safety Rules

1. **One Major Version at a Time**: Never jump multiple major versions
2. **Transitive Impact Check**: Analyze all affected modules
3. **Breaking Change Detection**: Check for API compatibility
4. **Security Priority**: Security updates bypass waiting period

### Update Classification

| Type | Auto-Apply | Requires Review | Example |
|------|------------|-----------------|---------|
| Patch | Yes | No | 1.2.3 -> 1.2.4 |
| Minor | Optional | Yes | 1.2.3 -> 1.3.0 |
| Major | No | Yes | 1.2.3 -> 2.0.0 |
| Security | Yes | No | Any version |

## Test Validation

### Baseline Test Requirement

Before any dependency update is applied:

1. Run full test suite to establish baseline
2. Record passing/failing test counts
3. Identify any pre-existing flaky tests
4. Store baseline results for comparison

### Post-Update Validation

After dependency update:

1. Run identical test suite
2. Compare against baseline
3. Flag any new failures as update-related
4. Automatic rollback if critical tests fail

### Test Result Categories

| Category | Action |
|----------|--------|
| All Pass | Proceed |
| Same Failures | Proceed (pre-existing) |
| New Failures | Rollback or Review |
| Compilation Error | Rollback |

## Configuration

### Agent Configuration

See [config/agents/maven_maintenance_agent.yaml](../config/agents/maven_maintenance_agent.yaml):

```yaml
test_config:
  test_timeout_seconds: 300
  suite_timeout_seconds: 1800
  parallel_tests: true
  fail_fast: false
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAVEN_HOME` | Auto-detect | Maven installation path |
| `MAVEN_OPTS` | `-Xmx1g` | JVM options for Maven |
| `MAVEN_SETTINGS` | `~/.m2/settings.xml` | Custom settings file |

## Error Handling

### Common Errors

| Error | Cause | Resolution |
|-------|-------|------------|
| `dependency:tree failed` | Invalid POM | Fix POM syntax |
| `Connection timeout` | Maven Central slow | Retry or use mirror |
| `Version conflict` | Incompatible versions | Use dependency management |
| `Build failure` | Compilation error | Review dependency changes |

### Retry Strategy

- **Transient errors**: Retry 3 times with exponential backoff
- **Network errors**: Switch to mirror, then retry
- **Build errors**: No retry, report and wait for user input
