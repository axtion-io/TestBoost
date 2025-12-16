# Database Schema Reference

**Purpose**: Complete reference for TestBoost database schema
**Version**: 1.0.0
**Database**: PostgreSQL 15+

---

## Overview

TestBoost uses PostgreSQL with SQLAlchemy ORM for data persistence. The schema supports session management, workflow tracking, and artifact storage.

## Entity Relationship Diagram

```mermaid
erDiagram
    SESSION ||--o{ STEP : contains
    SESSION ||--o{ EVENT : logs
    SESSION ||--o{ ARTIFACT : produces
    PROJECT ||--o{ SESSION : has
    PROJECT ||--o| PROJECT_LOCK : may_have

    SESSION {
        uuid id PK
        string session_type
        string status
        string mode
        text project_path
        jsonb config
        jsonb result
        text error_message
        timestamp created_at
        timestamp updated_at
        timestamp completed_at
    }

    STEP {
        uuid id PK
        uuid session_id FK
        string name
        integer sequence
        string status
        jsonb input
        jsonb output
        text error_message
        timestamp started_at
        timestamp completed_at
    }

    EVENT {
        uuid id PK
        uuid session_id FK
        string event_type
        string level
        text message
        jsonb context
        timestamp created_at
    }

    ARTIFACT {
        uuid id PK
        uuid session_id FK
        string artifact_type
        string name
        text content_path
        jsonb metadata
        timestamp created_at
    }

    PROJECT {
        uuid id PK
        text path UK
        string name
        jsonb config
        timestamp created_at
        timestamp updated_at
    }

    PROJECT_LOCK {
        uuid id PK
        uuid project_id FK UK
        uuid session_id FK
        timestamp acquired_at
        timestamp expires_at
    }
```

---

## Tables

### sessions

Stores workflow session information.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Session identifier |
| session_type | VARCHAR(50) | NOT NULL | Type: maven_maintenance, test_generation, docker_deployment |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | Status: pending, in_progress, completed, failed, cancelled |
| mode | VARCHAR(20) | NOT NULL, DEFAULT 'interactive' | Mode: interactive, autonomous, analysis_only, debug |
| project_path | TEXT | NOT NULL | Path to project root |
| config | JSONB | NOT NULL, DEFAULT '{}' | Session configuration |
| result | JSONB | NULL | Execution result data |
| error_message | TEXT | NULL | Error message if failed |
| created_at | TIMESTAMP WITH TZ | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMP WITH TZ | NOT NULL | Last update timestamp |
| completed_at | TIMESTAMP WITH TZ | NULL | Completion timestamp |

**Indexes**:
- `ix_sessions_status` on (status)
- `ix_sessions_project_path` on (project_path)
- `ix_sessions_created_at` on (created_at)

**Constraints**:
- `session_type IN ('maven_maintenance', 'test_generation', 'docker_deployment')`
- `status IN ('pending', 'in_progress', 'paused', 'completed', 'failed', 'cancelled')`
- `mode IN ('interactive', 'autonomous', 'analysis_only', 'debug')`

---

### steps

Stores individual workflow steps.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Step identifier |
| session_id | UUID | NOT NULL, FOREIGN KEY | Parent session |
| name | VARCHAR(100) | NOT NULL | Step name |
| sequence | INTEGER | NOT NULL | Execution order |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'pending' | Step status |
| input | JSONB | NULL | Step input data |
| output | JSONB | NULL | Step output data |
| error_message | TEXT | NULL | Error message if failed |
| started_at | TIMESTAMP WITH TZ | NULL | Start timestamp |
| completed_at | TIMESTAMP WITH TZ | NULL | Completion timestamp |

**Indexes**:
- `ix_steps_session_id` on (session_id)
- `ix_steps_session_sequence` on (session_id, sequence)

**Foreign Keys**:
- `session_id REFERENCES sessions(id) ON DELETE CASCADE`

---

### events

Stores session events and logs.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Event identifier |
| session_id | UUID | NOT NULL, FOREIGN KEY | Parent session |
| event_type | VARCHAR(50) | NOT NULL | Event type |
| level | VARCHAR(10) | NOT NULL | Log level: debug, info, warning, error |
| message | TEXT | NOT NULL | Event message |
| context | JSONB | NOT NULL, DEFAULT '{}' | Additional context |
| created_at | TIMESTAMP WITH TZ | NOT NULL | Event timestamp |

**Indexes**:
- `ix_events_session_id` on (session_id)
- `ix_events_created_at` on (created_at)

**Foreign Keys**:
- `session_id REFERENCES sessions(id) ON DELETE CASCADE`

---

### artifacts

Stores workflow artifacts (generated files, reports).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Artifact identifier |
| session_id | UUID | NOT NULL, FOREIGN KEY | Parent session |
| artifact_type | VARCHAR(50) | NOT NULL | Type: test_file, report, diff, backup |
| name | VARCHAR(255) | NOT NULL | Artifact name |
| content_path | TEXT | NOT NULL | Path to artifact content |
| metadata | JSONB | NOT NULL, DEFAULT '{}' | Additional metadata |
| created_at | TIMESTAMP WITH TZ | NOT NULL | Creation timestamp |

**Indexes**:
- `ix_artifacts_session_id` on (session_id)
- `ix_artifacts_type` on (artifact_type)

**Foreign Keys**:
- `session_id REFERENCES sessions(id) ON DELETE CASCADE`

---

### projects

Stores project metadata.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Project identifier |
| path | TEXT | NOT NULL, UNIQUE | Canonical project path |
| name | VARCHAR(255) | NULL | Project display name |
| config | JSONB | NOT NULL, DEFAULT '{}' | Project-specific config |
| created_at | TIMESTAMP WITH TZ | NOT NULL | First seen timestamp |
| updated_at | TIMESTAMP WITH TZ | NOT NULL | Last activity timestamp |

**Indexes**:
- `ix_projects_path` on (path) UNIQUE

---

### project_locks

Implements pessimistic locking for projects.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | UUID | PRIMARY KEY | Lock identifier |
| project_id | UUID | NOT NULL, UNIQUE, FOREIGN KEY | Locked project |
| session_id | UUID | NOT NULL, FOREIGN KEY | Owning session |
| acquired_at | TIMESTAMP WITH TZ | NOT NULL | Lock acquisition time |
| expires_at | TIMESTAMP WITH TZ | NOT NULL | Lock expiration time |

**Indexes**:
- `ix_project_locks_project_id` on (project_id) UNIQUE
- `ix_project_locks_expires_at` on (expires_at)

**Foreign Keys**:
- `project_id REFERENCES projects(id) ON DELETE CASCADE`
- `session_id REFERENCES sessions(id) ON DELETE CASCADE`

---

## CASCADE Policies

| Parent | Child | Policy | Rationale |
|--------|-------|--------|-----------|
| sessions | steps | CASCADE | Steps are part of session |
| sessions | events | CASCADE | Events belong to session |
| sessions | artifacts | CASCADE | Artifacts belong to session |
| projects | sessions | RESTRICT | Preserve history |
| projects | project_locks | CASCADE | Lock tied to project |

---

## Data Retention

### Purge Policy

Sessions and related data older than 1 year (365 days) are automatically purged.

**Purge criteria**:
- `sessions.created_at < NOW() - INTERVAL '365 days'`
- `sessions.status IN ('completed', 'failed', 'cancelled')`

**Purge order** (respects foreign keys):
1. DELETE artifacts WHERE session_id IN (...)
2. DELETE events WHERE session_id IN (...)
3. DELETE steps WHERE session_id IN (...)
4. DELETE sessions WHERE id IN (...)

**Purge schedule**: Daily at 2:00 AM UTC

---

## Performance Indexes

### Query Optimization

| Index | Query Pattern |
|-------|---------------|
| `ix_sessions_status` | Filter by status |
| `ix_sessions_project_path` | Find sessions for project |
| `ix_sessions_created_at` | Sort by date, purge queries |
| `ix_steps_session_sequence` | Get steps in order |
| `ix_events_session_id` | Get session events |
| `ix_project_locks_expires_at` | Find expired locks |

### Recommended Additional Indexes

For high-volume deployments:
```sql
-- Composite index for session listing
CREATE INDEX ix_sessions_status_created
ON sessions (status, created_at DESC);

-- Partial index for active sessions
CREATE INDEX ix_sessions_active
ON sessions (id)
WHERE status IN ('pending', 'in_progress');
```

---

## JSONB Schema

### sessions.config

```json
{
  "mode": "interactive",
  "timeout_seconds": 300,
  "skip_tests": false,
  "dry_run": false,
  "llm_model": "claude-sonnet-4-5-20250929"
}
```

### sessions.result

```json
{
  "dependencies_updated": 3,
  "tests_generated": 15,
  "coverage_achieved": 0.85,
  "duration_seconds": 125.4,
  "llm_calls": 12
}
```

### steps.input / steps.output

Flexible schema varies by step type. Example for analysis step:

```json
{
  "project_path": "/path/to/project",
  "analysis_type": "dependencies",
  "result": {
    "total": 45,
    "outdated": 3
  }
}
```

---

## Migration Management

Migrations are managed with Alembic.

```bash
# Generate new migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head

# Rollback one step
alembic downgrade -1
```

Migration files location: `src/db/migrations/versions/`
