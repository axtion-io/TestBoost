# Data Model: TestBoost Core

**Date**: 2025-11-23
**Feature**: 001-testboost-core

## Entity Relationship Diagram

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Session   │────<│    Step     │     │   Project   │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │                   │                   │
       ▼                   ▼                   ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Event    │     │  Artifact   │     │ Dependency  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                                        ┌─────────────┐
                                        │Modification │
                                        └─────────────┘
```

## Entities

### Session

Représente une exécution complète d'un workflow.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| project_path | VARCHAR(500) | NOT NULL | Chemin absolu du projet |
| project_name | VARCHAR(100) | NOT NULL | Nom du projet |
| session_type | ENUM | NOT NULL | maven_maintenance, test_generation, docker_deployment, audit |
| status | ENUM | NOT NULL | pending, running, paused, completed, failed, cancelled |
| mode | ENUM | NOT NULL | interactive, autonomous, analysis_only, debug |
| config | JSONB | | Configuration spécifique au workflow |
| metadata | JSONB | | Métadonnées additionnelles |
| started_at | TIMESTAMP | | Début d'exécution |
| completed_at | TIMESTAMP | | Fin d'exécution |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |
| updated_at | TIMESTAMP | NOT NULL | Dernière mise à jour |

**Indexes**:
- `idx_session_status` ON (status)
- `idx_session_type` ON (session_type)
- `idx_session_created` ON (created_at DESC)
- `idx_session_project` ON (project_path)

### Step

Représente une étape atomique dans un workflow.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| session_id | UUID | FK -> Session, NOT NULL | Session parente |
| step_code | VARCHAR(50) | NOT NULL | Code de l'étape (ex: validate_project) |
| step_name | VARCHAR(100) | NOT NULL | Nom lisible |
| position | INTEGER | NOT NULL | Ordre dans le workflow |
| status | ENUM | NOT NULL | pending, running, completed, failed, skipped |
| inputs | JSONB | | Données d'entrée |
| outputs | JSONB | | Données de sortie |
| error | TEXT | | Message d'erreur si échec |
| started_at | TIMESTAMP | | Début d'exécution |
| completed_at | TIMESTAMP | | Fin d'exécution |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

**Indexes**:
- `idx_step_session` ON (session_id)
- `idx_step_status` ON (status)
- `idx_step_position` ON (session_id, position)

**Unique**: (session_id, step_code)

### Event

Journal immutable des événements (event sourcing).

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | BIGSERIAL | PK | Identifiant séquentiel |
| session_id | UUID | FK -> Session, NOT NULL | Session concernée |
| step_id | UUID | FK -> Step | Étape concernée (optionnel) |
| event_type | VARCHAR(50) | NOT NULL | Type d'événement |
| event_data | JSONB | NOT NULL | Payload de l'événement |
| timestamp | TIMESTAMP | NOT NULL, DEFAULT NOW() | Horodatage |

**Indexes**:
- `idx_event_session` ON (session_id)
- `idx_event_timestamp` ON (timestamp DESC)
- `idx_event_type` ON (event_type)

**Event Types**:
- `session.created`, `session.started`, `session.completed`, `session.failed`
- `step.started`, `step.completed`, `step.failed`, `step.skipped`
- `decision.made`, `rollback.performed`, `user.confirmed`

### Artifact

Fichier ou résultat produit par un workflow.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| session_id | UUID | FK -> Session, NOT NULL | Session parente |
| step_id | UUID | FK -> Step | Étape productrice |
| artifact_type | VARCHAR(50) | NOT NULL | Type (test_file, report, dockerfile, etc.) |
| name | VARCHAR(200) | NOT NULL | Nom du fichier/artifact |
| path | VARCHAR(500) | | Chemin sur disque |
| content | TEXT | | Contenu (si stocké en DB) |
| metadata | JSONB | | Métadonnées (taille, hash, etc.) |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

**Indexes**:
- `idx_artifact_session` ON (session_id)
- `idx_artifact_type` ON (artifact_type)

### Project (Cache)

Cache des informations projet analysées.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| path | VARCHAR(500) | UNIQUE, NOT NULL | Chemin absolu |
| name | VARCHAR(100) | NOT NULL | Nom du projet |
| project_type | VARCHAR(20) | NOT NULL | jar, war |
| java_version | VARCHAR(10) | | Version Java détectée |
| spring_boot_version | VARCHAR(20) | | Version Spring Boot |
| analysis_data | JSONB | | Données d'analyse complètes |
| analyzed_at | TIMESTAMP | NOT NULL | Date de dernière analyse |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

**Indexes**:
- `idx_project_path` ON (path)

### Dependency

Dépendance Maven avec versions.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| project_id | UUID | FK -> Project, NOT NULL | Projet parent |
| group_id | VARCHAR(200) | NOT NULL | Maven groupId |
| artifact_id | VARCHAR(200) | NOT NULL | Maven artifactId |
| current_version | VARCHAR(50) | NOT NULL | Version actuelle |
| latest_version | VARCHAR(50) | | Dernière version disponible |
| update_type | ENUM | | security, major, minor, patch |
| cve_ids | VARCHAR[] | | Liste des CVE |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

**Indexes**:
- `idx_dependency_project` ON (project_id)
- `idx_dependency_update` ON (update_type)

**Unique**: (project_id, group_id, artifact_id)

### Modification

Changement appliqué à un fichier.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| session_id | UUID | FK -> Session, NOT NULL | Session parente |
| dependency_id | UUID | FK -> Dependency | Dépendance concernée |
| file_path | VARCHAR(500) | NOT NULL | Fichier modifié |
| old_value | TEXT | | Valeur avant |
| new_value | TEXT | | Valeur après |
| validated | BOOLEAN | DEFAULT FALSE | Validé par tests |
| created_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date de création |

**Indexes**:
- `idx_modification_session` ON (session_id)

### ProjectLock

Verrou exclusif par projet.

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Identifiant unique |
| project_path | VARCHAR(500) | UNIQUE, NOT NULL | Chemin du projet |
| session_id | UUID | FK -> Session, NOT NULL | Session détenant le verrou |
| acquired_at | TIMESTAMP | NOT NULL, DEFAULT NOW() | Date d'acquisition |
| expires_at | TIMESTAMP | NOT NULL | Expiration (sécurité) |

**Indexes**:
- `idx_lock_project` ON (project_path)
- `idx_lock_expires` ON (expires_at)

## State Transitions

### Session Status

```
pending -> running -> completed
                  \-> failed
                  \-> cancelled
running -> paused -> running
```

### Step Status

```
pending -> running -> completed
                  \-> failed
                  \-> skipped
```

## Validation Rules

1. **Session**
   - `project_path` doit être un chemin absolu existant
   - `completed_at` >= `started_at` si définis
   - `status` = 'completed' implique `completed_at` NOT NULL

2. **Step**
   - `position` unique par session
   - `step_code` unique par session
   - `completed_at` >= `started_at` si définis

3. **Event**
   - `event_data` doit être JSON valide
   - `timestamp` automatique, non modifiable

4. **ProjectLock**
   - Un seul verrou actif par `project_path`
   - `expires_at` dans le futur lors de l'acquisition

## Data Retention

- **Sessions & Events**: 1 an, puis purge automatique
- **Project cache**: Invalidé après 24h ou sur changement détecté
- **Artifacts**: Liés à la session, purgés avec elle

## PostgreSQL Extensions Required

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";  -- UUID generation
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- Text search
```
