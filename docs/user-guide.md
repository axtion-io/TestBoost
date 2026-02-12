# TestBoost - Guide Utilisateur

Ce guide vous accompagne pas à pas dans l'utilisation de TestBoost, un outil d'automatisation de maintenance pour les projets Java/Spring Boot.

## Table des Matières

1. [Installation Rapide](#installation-rapide)
2. [Premier Workflow](#premier-workflow)
3. [Utilisation via l'API REST](#utilisation-via-lapi-rest)
4. [Workflows Disponibles](#workflows-disponibles)
5. [Modes d'Exécution](#modes-dexécution)
6. [Intégration CI/CD](#intégration-cicd)
7. [Troubleshooting](#troubleshooting)

---

## Installation Rapide

### Prérequis

| Composant | Version Minimale | Vérification |
|-----------|-----------------|--------------|
| Python | 3.11+ | `python --version` |
| Docker | 20.10+ | `docker --version` |
| Docker Compose | 2.0+ | `docker compose version` |
| Git | 2.30+ | `git --version` |
| PostgreSQL | 15+ | Via Docker |

### Étape 1 : Cloner le Repository

```bash
git clone https://github.com/axtion-io/TestBoost.git
cd TestBoost
```

### Étape 2 : Installer les Dépendances

```bash
# Installer Poetry si nécessaire
pip install poetry

# Installer les dépendances du projet
poetry install

# Activer l'environnement virtuel
poetry shell
```

### Étape 3 : Configurer l'Environnement

Créez un fichier `.env` à la racine du projet :

```env
# Base de données (PostgreSQL sur port 5433)
DATABASE_URL=postgresql+asyncpg://testboost:testboost@localhost:5433/testboost

# Clé API TestBoost
API_KEY=tb_dev_0123456789abcdef0123456789abcdef

# Provider LLM (choisir un seul)
MODEL=gemini-2.0-flash
GOOGLE_API_KEY=your-google-api-key

# Alternatives :
# MODEL=anthropic/claude-sonnet-4-20250514
# ANTHROPIC_API_KEY=your-anthropic-key

# MODEL=openai/gpt-4o
# OPENAI_API_KEY=your-openai-key

# Optionnel : Observabilité LangSmith
# LANGSMITH_TRACING=true
# LANGSMITH_API_KEY=your-langsmith-key
# LANGSMITH_PROJECT=testboost
```

### Étape 4 : Démarrer la Base de Données

```bash
docker compose up -d postgres
```

### Étape 5 : Appliquer les Migrations

```bash
alembic upgrade head
```

### Étape 6 : Vérifier l'Installation

```bash
# Démarrer l'API
python -m uvicorn src.api.main:app --reload

# Dans un autre terminal, vérifier la santé
curl http://localhost:8000/health
```

Résultat attendu :
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "ok",
    "llm": "ok"
  }
}
```

---

## Premier Workflow

Cet exemple montre comment utiliser TestBoost sur un projet Java/Spring Boot quelconque. Remplacez `<project_path>` par le chemin vers votre projet.

### Préparer votre Projet

Assurez-vous que votre projet Java/Maven est accessible localement :

```bash
# Soit un projet existant déjà cloné
ls <project_path>/pom.xml

# Soit cloner un projet pour tester
git clone <url-de-votre-projet>.git <project_path>
```

### Via la CLI

#### 1. Lancer l'Analyse des Dépendances

```bash
python -m src.cli.main maintenance list <project_path>
```

**Sortie attendue :**

```
TestBoost - Maven Maintenance
=============================

Analyzing project: <project_path>

Dependencies Analysis:
----------------------
[SECURITY] org.example:vulnerable-lib
           Current: 1.2.0 -> Available: 1.3.1
           CVE-XXXX-XXXXX: High severity

[MAJOR] org.example:some-library
        Current: 2.0.0 -> Available: 3.0.0
        Breaking changes: None detected

[MINOR] org.example:utils-lib
        Current: 4.1.0 -> Available: 4.2.0
        Safe upgrade

Summary: 3 updates available (1 security, 1 major, 1 minor)
```

#### 2. Appliquer les Mises à Jour

```bash
# Mode interactif (confirmation avant chaque action)
python -m src.cli.main maintenance run <project_path>

# Mode autonome (CI/CD)
python -m src.cli.main maintenance run <project_path> --mode autonomous
```

#### 3. Interpréter les Résultats

Le workflow génère un rapport dans `logs/` :

```
Maintenance Report
==================
Session ID: abc123-def456
Duration: 2m 34s
Status: SUCCESS

Updates Applied:
- vulnerable-lib: 1.2.0 -> 1.3.1 [OK]
- some-library: 2.0.0 -> 3.0.0 [OK]
- utils-lib: 4.1.0 -> 4.2.0 [OK]

Tests: 45 passed, 0 failed
Branch: maintenance/2024-01-15

Next Steps:
1. Review changes on branch 'maintenance/2024-01-15'
2. Run integration tests manually
3. Create pull request when ready
```

### Via l'API REST

Le même workflow peut être exécuté via l'API. Consultez la section [Utilisation via l'API REST](#utilisation-via-lapi-rest) pour des exemples détaillés.

---

## Utilisation via l'API REST

TestBoost expose une API REST complète qui permet de piloter tous les workflows de manière programmatique. L'API est idéale pour les intégrations CI/CD, les dashboards, ou tout outil tiers.

### Démarrer le Serveur API

```bash
# Via la CLI
python -m src.cli.main serve

# Ou directement avec uvicorn
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Le serveur est accessible sur `http://localhost:8000`. La documentation interactive Swagger est disponible sur `http://localhost:8000/docs`.

### Authentification

Toutes les requêtes API (sauf `/health`, `/metrics`, `/docs`) nécessitent un header `X-API-Key` :

```bash
curl -H "X-API-Key: tb_dev_0123456789abcdef0123456789abcdef" \
  http://localhost:8000/api/v2/sessions
```

La clé API est définie dans votre fichier `.env` via la variable `API_KEY`. Voir [api-authentication.md](./api-authentication.md) pour plus de détails sur le format et la gestion des clés.

### Health Check & Métriques

#### Vérifier la santé du service

```bash
# Health check (pas d'authentification requise)
curl http://localhost:8000/health
```

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "checks": {
    "database": "healthy"
  }
}
```

#### Consulter les métriques

```bash
# Format Prometheus
curl http://localhost:8000/metrics

# Format JSON
curl http://localhost:8000/metrics/json
```

### Gestion des Sessions

Les sessions sont l'objet central de l'API. Chaque workflow (maintenance, tests, deploy) s'exécute dans une session.

#### Créer une session

```bash
curl -X POST http://localhost:8000/api/v2/sessions \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "session_type": "maven_maintenance",
    "project_path": "/path/to/your/project",
    "mode": "autonomous",
    "config": {}
  }'
```

**Types de session** : `maven_maintenance`, `test_generation`, `docker_deployment`

**Modes** : `interactive`, `autonomous`, `analysis_only`

**Réponse** (201 Created) :
```json
{
  "id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "session_type": "maven_maintenance",
  "status": "pending",
  "mode": "autonomous",
  "project_path": "/path/to/your/project",
  "config": {},
  "result": null,
  "error_message": null,
  "created_at": "2025-01-15T10:30:00Z",
  "updated_at": "2025-01-15T10:30:00Z",
  "completed_at": null
}
```

#### Lister les sessions

```bash
# Toutes les sessions (paginé)
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions?page=1&per_page=20"

# Filtrer par statut
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions?status=in_progress"

# Filtrer par type et date
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions?session_type=test_generation&created_after=2025-01-01T00:00:00Z"
```

**Paramètres de filtrage** :
| Paramètre | Type | Description |
|-----------|------|-------------|
| `status` | string | Filtrer par statut (`pending`, `in_progress`, `paused`, `completed`, `failed`, `cancelled`) |
| `session_type` | string | Filtrer par type de session |
| `project_path` | string | Filtrer par chemin de projet (correspondance partielle) |
| `created_after` | datetime | Sessions créées après cette date (ISO 8601) |
| `created_before` | datetime | Sessions créées avant cette date (ISO 8601) |
| `page` | int | Page (1-indexed, défaut: 1) |
| `per_page` | int | Éléments par page (1-100, défaut: 20) |

**Réponse** :
```json
{
  "items": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 42,
    "total_pages": 3,
    "has_next": true,
    "has_prev": false
  }
}
```

#### Récupérer une session

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}
```

#### Mettre à jour une session

```bash
curl -X PATCH http://localhost:8000/api/v2/sessions/{session_id} \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "cancelled",
    "error_message": "Cancelled by user"
  }'
```

#### Supprimer une session

```bash
curl -X DELETE -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}
# Réponse : 204 No Content
```

### Exécution des Steps

Chaque session contient des étapes (steps) qui peuvent être consultées et exécutées individuellement.

#### Lister les étapes d'une session

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}/steps
```

**Réponse** :
```json
{
  "items": [
    {
      "id": "step-uuid",
      "session_id": "session-uuid",
      "code": "analyze",
      "name": "Analyze Dependencies",
      "status": "completed",
      "sequence": 1,
      "inputs": {},
      "outputs": {"dependencies_found": 15},
      "error_message": null,
      "retry_count": 0,
      "started_at": "2025-01-15T10:31:00Z",
      "completed_at": "2025-01-15T10:32:00Z",
      "created_at": "2025-01-15T10:30:00Z"
    }
  ],
  "total": 4
}
```

#### Récupérer une étape spécifique

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}/steps/{step_code}
```

#### Exécuter une étape

```bash
curl -X POST http://localhost:8000/api/v2/sessions/{session_id}/steps/{step_code}/execute \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "inputs": {},
    "run_workflow": true,
    "run_in_background": true
  }'
```

**Réponse** :
```json
{
  "id": "step-uuid",
  "code": "analyze",
  "name": "Analyze Dependencies",
  "status": "in_progress",
  "message": "Step execution started"
}
```

#### Mettre à jour le statut d'une étape

```bash
curl -X PATCH http://localhost:8000/api/v2/sessions/{session_id}/steps/{step_code} \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "completed",
    "outputs": {"result": "success"}
  }'
```

### Pause / Resume

#### Mettre en pause une session

```bash
curl -X POST http://localhost:8000/api/v2/sessions/{session_id}/pause \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Waiting for manual approval"}'
```

**Réponse** :
```json
{
  "session_id": "session-uuid",
  "status": "paused",
  "checkpoint_id": "chk-123",
  "message": "Session paused successfully"
}
```

#### Reprendre une session

```bash
curl -X POST http://localhost:8000/api/v2/sessions/{session_id}/resume \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "checkpoint_id": "chk-123",
    "updated_state": {}
  }'
```

**Réponse** :
```json
{
  "session_id": "session-uuid",
  "status": "in_progress",
  "message": "Session resumed successfully"
}
```

### Artifacts

Les artifacts sont les fichiers générés par les workflows (rapports, code, configs).

#### Lister les artifacts d'une session

```bash
# Tous les artifacts
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}/artifacts

# Filtrer par type ou format
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions/{session_id}/artifacts?artifact_type=test_file&file_format=java"
```

**Réponse** :
```json
{
  "items": [
    {
      "id": "artifact-uuid",
      "session_id": "session-uuid",
      "step_id": "step-uuid",
      "artifact_type": "test_file",
      "file_path": "/path/to/generated/Test.java",
      "content_type": "text/x-java",
      "file_format": "java",
      "metadata": {}
    }
  ],
  "total": 3
}
```

#### Télécharger le contenu d'un artifact

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}/artifacts/{artifact_id}/content \
  -o output_file
```

### Events (Suivi en temps réel)

Les events permettent de suivre la progression d'un workflow en temps réel via un mécanisme de polling.

```bash
# Tous les events d'une session
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions/{session_id}/events?page=1&per_page=50"

# Polling : récupérer uniquement les nouveaux events depuis un timestamp
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions/{session_id}/events?since=2025-01-15T10:35:00Z"

# Filtrer par type d'event
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/sessions/{session_id}/events?event_type=step_completed"
```

**Réponse** :
```json
{
  "items": [
    {
      "id": "event-uuid",
      "session_id": "session-uuid",
      "event_type": "step_completed",
      "timestamp": "2025-01-15T10:35:00Z",
      "data": {"step_code": "analyze", "duration_ms": 12500},
      "severity": "info"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 50,
    "total": 12,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

### Endpoints Testboost (Raccourcis Haut Niveau)

Ces endpoints offrent un accès simplifié aux workflows sans gérer manuellement les sessions et steps.

#### Analyser un projet

```bash
curl -X POST http://localhost:8000/api/testboost/analyze \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/your/project",
    "include_snapshots": false,
    "check_vulnerabilities": true
  }'
```

#### Lancer la maintenance Maven

```bash
curl -X POST http://localhost:8000/api/testboost/maintenance/maven \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/your/project",
    "auto_approve": true,
    "skip_tests": false,
    "dry_run": false
  }'
```

**Suivre la progression** :
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/testboost/maintenance/maven/{session_id}
```

**Récupérer le résultat final** :
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/testboost/maintenance/maven/{session_id}/result
```

#### Générer des tests

```bash
curl -X POST http://localhost:8000/api/testboost/tests/generate \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/your/project",
    "target_mutation_score": 80.0,
    "include_integration": true,
    "include_snapshot": true,
    "max_classes": 20
  }'
```

**Suivre la progression** :
```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/testboost/tests/generate/{session_id}
```

#### Analyser l'impact du code

```bash
curl -X POST http://localhost:8000/api/testboost/tests/impact \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/your/project",
    "verbose": true
  }'
```

### Audit de Sécurité

#### Lancer un scan de vulnérabilités

```bash
curl -X POST http://localhost:8000/api/audit/scan \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/your/project",
    "severity": "high",
    "output_format": "json"
  }'
```

**Réponse** :
```json
{
  "success": true,
  "session_id": "abc123-def456",
  "project_path": "/path/to/your/project",
  "total_vulnerabilities": 2,
  "vulnerabilities": [
    {
      "cve": "CVE-2024-1234",
      "severity": "high",
      "dependency": "org.example:lib:1.0",
      "description": "Remote code execution vulnerability"
    }
  ],
  "summary": {"critical": 0, "high": 2, "medium": 0, "low": 0}
}
```

#### Récupérer le rapport d'audit

```bash
# Format JSON
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/audit/report/{session_id}

# Format HTML
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/audit/report/{session_id}/html
```

### Logs

#### Consulter les logs

```bash
# Tous les logs (paginé)
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/logs?page=1&per_page=100"

# Filtrer par niveau et session
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/logs?level=error&session_id={session_id}"

# Filtrer par catégorie et période
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/logs?category=business&since=2025-01-15T00:00:00Z&until=2025-01-16T00:00:00Z"
```

**Paramètres de filtrage** :
| Paramètre | Type | Description |
|-----------|------|-------------|
| `level` | string | `critical`, `error`, `warn`, `info`, `debug`, `trace` |
| `category` | string | `business`, `access`, `system`, `debug`, `audit` |
| `session_id` | string | UUID de la session |
| `event` | string | Nom de l'event (pattern regex) |
| `since` | datetime | Logs après cette date (ISO 8601) |
| `until` | datetime | Logs avant cette date (ISO 8601) |
| `date` | string | Date du fichier de log (format YYYYMMDD) |
| `page` | int | Page (1-indexed, défaut: 1) |
| `per_page` | int | Éléments par page (1-1000, défaut: 100) |

#### Statistiques des logs

```bash
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/logs/stats
```

**Réponse** :
```json
{
  "date": "20250115",
  "total_lines": 1523,
  "by_level": {"info": 1200, "warn": 200, "error": 100, "debug": 23},
  "by_category": {"business": 800, "system": 500, "access": 200, "debug": 23},
  "top_events": [
    {"event": "session_created", "count": 45},
    {"event": "step_executed", "count": 120}
  ],
  "recent_errors": [
    {
      "timestamp": "2025-01-15T10:35:00Z",
      "event": "llm_error",
      "session_id": "session-uuid",
      "message": "LLM request failed",
      "error": "Timeout after 120s"
    }
  ]
}
```

### Récapitulatif des Endpoints

#### Core (Sessions & Workflows)

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v2/sessions` | Créer une session |
| `GET` | `/api/v2/sessions` | Lister les sessions (paginé, filtrable) |
| `GET` | `/api/v2/sessions/{id}` | Détails d'une session |
| `PATCH` | `/api/v2/sessions/{id}` | Mettre à jour une session |
| `DELETE` | `/api/v2/sessions/{id}` | Supprimer une session |
| `GET` | `/api/v2/sessions/{id}/steps` | Lister les étapes |
| `GET` | `/api/v2/sessions/{id}/steps/{code}` | Détails d'une étape |
| `POST` | `/api/v2/sessions/{id}/steps/{code}/execute` | Exécuter une étape |
| `PATCH` | `/api/v2/sessions/{id}/steps/{code}` | Mettre à jour une étape |
| `POST` | `/api/v2/sessions/{id}/pause` | Mettre en pause |
| `POST` | `/api/v2/sessions/{id}/resume` | Reprendre |
| `GET` | `/api/v2/sessions/{id}/artifacts` | Lister les artifacts |
| `GET` | `/api/v2/sessions/{id}/artifacts/{aid}/content` | Télécharger un artifact |
| `GET` | `/api/v2/sessions/{id}/events` | Events (polling temps réel) |

#### Raccourcis Haut Niveau

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/testboost/analyze` | Analyser un projet |
| `POST` | `/api/testboost/maintenance/maven` | Lancer maintenance Maven |
| `GET` | `/api/testboost/maintenance/maven/{id}` | Statut de la maintenance |
| `GET` | `/api/testboost/maintenance/maven/{id}/result` | Résultat de la maintenance |
| `DELETE` | `/api/testboost/maintenance/maven/{id}` | Annuler la maintenance |
| `POST` | `/api/testboost/tests/generate` | Générer des tests |
| `GET` | `/api/testboost/tests/generate/{id}` | Statut de la génération |
| `GET` | `/api/testboost/tests/generate/{id}/result` | Résultat de la génération |
| `POST` | `/api/testboost/tests/impact` | Analyse d'impact |

#### Audit

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/audit/scan` | Scanner les vulnérabilités |
| `GET` | `/api/audit/report/{id}` | Rapport d'audit (JSON) |
| `GET` | `/api/audit/report/{id}/html` | Rapport d'audit (HTML) |

#### Observabilité

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/health` | Health check (sans auth) |
| `GET` | `/metrics` | Métriques Prometheus (sans auth) |
| `GET` | `/metrics/json` | Métriques JSON (sans auth) |
| `GET` | `/api/v2/logs` | Consulter les logs |
| `GET` | `/api/v2/logs/stats` | Statistiques des logs |

### Gestion des Erreurs API

Toutes les erreurs suivent un format standardisé :

```json
{
  "error_code": "SESSION_NOT_FOUND",
  "message": "Session not found: abc-123",
  "context": {
    "resource_type": "session",
    "resource_id": "abc-123"
  },
  "request_id": "req-xyz-789"
}
```

Voir [api-errors.md](./api-errors.md) pour la liste complète des codes d'erreur et les stratégies de retry.

---

## Workflows Disponibles

### 1. Maven Maintenance

**Objectif** : Mettre à jour les dépendances Maven avec non-régression garantie.

**CLI** :
```bash
# Lister les dépendances obsolètes
python -m src.cli.main maintenance list <project_path>

# Appliquer les mises à jour
python -m src.cli.main maintenance run <project_path> [--mode autonomous]

# Vérifier le statut d'une session
python -m src.cli.main maintenance status <session_id>
```

**API** :
```bash
# Lancer la maintenance
curl -X POST http://localhost:8000/api/testboost/maintenance/maven \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"project_path": "<project_path>", "auto_approve": true}'

# Suivre la progression
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/testboost/maintenance/maven/{session_id}
```

**Options CLI** :
- `--skip-security` : Ignorer les mises à jour de sécurité
- `--skip-major` : Ignorer les mises à jour majeures
- `--dry-run` : Afficher sans appliquer

### 2. Test Generation

**Objectif** : Générer une suite de tests complète pour le code existant.

**CLI** :
```bash
# Générer des tests pour tout le projet
python -m src.cli.main tests generate <project_path>

# Générer pour une classe spécifique
python -m src.cli.main tests generate <project_path> --target src/main/java/com/example/Service.java

# Avec mutation testing
python -m src.cli.main tests generate <project_path> --mutation-score 80
```

**API** :
```bash
# Lancer la génération
curl -X POST http://localhost:8000/api/testboost/tests/generate \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"project_path": "<project_path>", "target_mutation_score": 80.0, "include_integration": true}'

# Suivre la progression
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/testboost/tests/generate/{session_id}
```

**Options CLI** :
- `--include-integration` : Inclure les tests d'intégration
- `--include-snapshot` : Inclure les tests snapshot
- `--output-dir` : Répertoire de sortie
- `--verbose` : Affichage détaillé

### 3. Docker Deployment

**Objectif** : Déployer l'application dans Docker pour validation.

**CLI** :
```bash
# Déployer le projet dans Docker
python -m src.cli.main deploy run <project_path>

# Construire uniquement l'image
python -m src.cli.main deploy build <project_path>

# Collecter les logs des containers
python -m src.cli.main deploy logs <project_path>

# Vérifier le statut des containers
python -m src.cli.main deploy status <project_path>

# Arrêter les containers
python -m src.cli.main deploy stop <project_path>
```

**Options CLI** :
- `--dependency/-d` : Services dépendants (postgres, mysql, redis, mongodb)
- `--endpoint/-e` : Endpoint de health check
- `--skip-health` : Ignorer la validation health check

### 4. Impact Analysis

**Objectif** : Analyser l'impact des modifications de code pour cibler les tests.

**CLI** :
```bash
# Analyser les changements uncommitted
python -m src.cli.main tests impact <project_path>

# Générer rapport JSON pour CI
python -m src.cli.main tests impact <project_path> --output impact-report.json
```

**API** :
```bash
curl -X POST http://localhost:8000/api/testboost/tests/impact \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"project_path": "<project_path>", "verbose": true}'
```

**Sortie** :
```json
{
  "impacts": [
    {
      "file": "src/main/java/com/example/UserService.java",
      "change_category": "business_rule",
      "risk_level": "high",
      "required_tests": ["unit", "integration"],
      "test_requirements": [
        {"type": "nominal", "description": "Test user creation with valid data"},
        {"type": "edge_case", "description": "Test user creation with empty name"}
      ]
    }
  ]
}
```

### 5. Security Audit

**Objectif** : Scanner les dépendances pour détecter les vulnérabilités connues.

**CLI** :
```bash
# Scanner les vulnérabilités
python -m src.cli.main audit scan <project_path>

# Filtrer par sévérité
python -m src.cli.main audit scan <project_path> --severity high

# Exporter en SARIF (pour GitHub Security)
python -m src.cli.main audit scan <project_path> --format sarif --output audit.sarif
```

**API** :
```bash
# Lancer le scan
curl -X POST http://localhost:8000/api/audit/scan \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"project_path": "<project_path>", "severity": "high", "output_format": "json"}'

# Récupérer le rapport
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/audit/report/{session_id}
```

---

## Modes d'Exécution

### Mode Interactif (Défaut)

Le système demande confirmation avant chaque action critique.

```bash
python -m src.cli.main maintenance run <project_path>
```

```
[?] Apply update spring-boot 3.1.0 -> 3.2.1? [Y/n]: y
[*] Updating spring-boot...
[*] Running tests...
[OK] Tests passed (45/45)

[?] Apply update lombok 1.18.24 -> 1.18.30? [Y/n]: n
[*] Skipping lombok update

Continue with remaining updates? [Y/n]: y
```

### Mode Autonome

Pour l'intégration CI/CD, toutes les décisions sont automatiques.

```bash
python -m src.cli.main maintenance run <project_path> --mode autonomous
```

En cas d'erreur, le workflow s'arrête et génère un rapport d'échec.

### Mode Analyse Seule

Aucune modification n'est appliquée au projet.

```bash
python -m src.cli.main maintenance run <project_path> --mode analysis_only
```

### Mode Debug

Logs détaillés pour le troubleshooting.

```bash
python -m src.cli.main maintenance run <project_path> --mode debug
```

### Gestion des Sessions

Les workflows créent des sessions qui peuvent être gérées via CLI ou API.

#### Via CLI

```bash
# Lister les sessions
python -m src.cli.main maintenance sessions
python -m src.cli.main maintenance sessions --status in_progress

# Pause / Resume
python -m src.cli.main maintenance pause <session_id> --reason "Waiting for approval"
python -m src.cli.main maintenance resume <session_id>

# Exécution step-by-step
python -m src.cli.main maintenance steps <session_id>
python -m src.cli.main maintenance step <session_id> analyze

# Artifacts
python -m src.cli.main maintenance artifacts <session_id>
python -m src.cli.main maintenance artifacts <session_id> --output artifacts.json

# Annuler
python -m src.cli.main maintenance cancel <session_id> [--force]
```

#### Via API

```bash
# Pause
curl -X POST http://localhost:8000/api/v2/sessions/{session_id}/pause \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{"reason": "Manual review required"}'

# Resume
curl -X POST http://localhost:8000/api/v2/sessions/{session_id}/resume \
  -H "X-API-Key: $API_KEY" -H "Content-Type: application/json" \
  -d '{}'

# Artifacts
curl -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}/artifacts

# Supprimer
curl -X DELETE -H "X-API-Key: $API_KEY" \
  http://localhost:8000/api/v2/sessions/{session_id}
```

---

## Intégration CI/CD

### GitHub Actions

Créez `.github/workflows/testboost.yml` :

```yaml
name: TestBoost Maintenance

on:
  schedule:
    - cron: '0 6 * * 1'  # Chaque lundi à 6h
  workflow_dispatch:

jobs:
  maintenance:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_USER: testboost
          POSTGRES_PASSWORD: testboost
          POSTGRES_DB: testboost
        ports:
          - 5433:5432

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install TestBoost
        run: |
          pip install poetry
          poetry install

      - name: Run Maintenance
        env:
          DATABASE_URL: postgresql+asyncpg://testboost:testboost@localhost:5433/testboost
          GOOGLE_API_KEY: ${{ secrets.GOOGLE_API_KEY }}
          MODEL: gemini-2.0-flash
        run: |
          poetry run alembic upgrade head
          poetry run python -m src.cli.main maintenance run . --mode autonomous

      - name: Create Pull Request
        if: success()
        uses: peter-evans/create-pull-request@v5
        with:
          title: "[TestBoost] Dependency Updates"
          branch: testboost/maintenance
```

### GitLab CI

Créez `.gitlab-ci.yml` :

```yaml
stages:
  - maintenance

testboost:
  stage: maintenance
  image: python:3.11
  services:
    - postgres:15
  variables:
    POSTGRES_USER: testboost
    POSTGRES_PASSWORD: testboost
    POSTGRES_DB: testboost
    DATABASE_URL: postgresql+asyncpg://testboost:testboost@postgres:5432/testboost
  script:
    - pip install poetry
    - poetry install
    - poetry run alembic upgrade head
    - poetry run python -m src.cli.main maintenance run . --mode autonomous
  rules:
    - if: $CI_PIPELINE_SOURCE == "schedule"
```

### Impact Check (PR Gate)

Bloquer les PR sans tests d'impact :

```yaml
# .github/workflows/impact-check.yml
name: Impact Check

on:
  pull_request:
    paths:
      - '**.java'

jobs:
  impact:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Check Impact Coverage
        run: |
          pip install poetry
          poetry install
          poetry run python -m src.cli.main tests impact . --output impact.json

          # Fail if business-critical impacts are uncovered
          if jq -e '.uncovered_critical | length > 0' impact.json; then
            echo "ERROR: Uncovered business-critical impacts detected"
            exit 1
          fi
```

---

## Troubleshooting

### Erreurs LLM Courantes

#### "API key not configured"

```
LLMProviderError: API key not configured for provider 'google-genai'
```

**Solution** :
1. Vérifiez que `.env` contient la bonne clé
2. Redémarrez l'application
3. Vérifiez la variable : `echo $GOOGLE_API_KEY`

#### "Rate limit exceeded"

```
LLM rate limit exceeded by google-genai. Retry after 60 seconds.
```

**Solution** :
1. Attendre le délai indiqué
2. Passer à un autre provider
3. Réduire la fréquence des appels

#### "LLM request timeout"

```
LLMTimeoutError: Request timed out after 120s
```

**Solution** :
1. Vérifier la connexion internet
2. Augmenter `LLM_TIMEOUT` dans `.env`
3. Réessayer plus tard

### Problèmes de Base de Données

#### "Connection refused"

```
sqlalchemy.exc.OperationalError: connection refused
```

**Solution** :
1. Vérifiez que PostgreSQL est démarré : `docker compose ps`
2. Vérifiez le port : `docker compose logs postgres`
3. Redémarrez : `docker compose restart postgres`

#### "Database does not exist"

```
FATAL: database "testboost" does not exist
```

**Solution** :
```bash
docker compose down -v
docker compose up -d postgres
alembic upgrade head
```

### Problèmes Maven

#### "Maven build failed"

```
ERROR: Maven build failed with exit code 1
```

**Solution** :
1. Vérifiez que le projet compile : `mvn clean compile`
2. Vérifiez la version Java : `java -version`
3. Consultez les logs Maven dans `logs/`

#### "Tests timeout"

```
Maven tests timed out after 300s
```

**Solution** :
1. Augmenter le timeout dans la config de l'agent
2. Exclure les tests lents : `--skip-slow-tests`
3. Vérifier les tests qui bloquent

### Problèmes API

#### "Authentication required" (401)

```json
{"error_code": "AUTHENTICATION_ERROR", "message": "X-API-Key header is required"}
```

**Solution** :
1. Ajoutez le header `X-API-Key` à votre requête
2. Vérifiez que la clé correspond à celle dans `.env`

#### "Session not found" (404)

```json
{"error_code": "SESSION_NOT_FOUND", "message": "Session not found: abc-123"}
```

**Solution** :
1. Vérifiez l'UUID de la session
2. Listez les sessions existantes : `GET /api/v2/sessions`

#### "Project locked" (409)

```json
{"error_code": "PROJECT_LOCKED", "message": "Project is locked by another session"}
```

**Solution** :
1. Attendez la fin de la session en cours
2. Annulez la session bloquante : `DELETE /api/v2/sessions/{id}`

### Codes de Sortie CLI

| Code | Signification | Action |
|------|---------------|--------|
| 0 | Succès | Aucune |
| 1 | Erreur générale | Consulter les logs |
| 2 | Erreur de configuration | Vérifier `.env` |
| 3 | Projet invalide | Vérifier `pom.xml` |
| 4 | Tests échoués | Examiner les tests |
| 5 | Timeout | Augmenter timeout |

### Logs

Les logs sont stockés dans `logs/testboost_YYYYMMDD.log`.

Pour activer le mode debug :

```bash
export LOG_LEVEL=DEBUG
python -m src.cli.main maintenance run <project_path>
```

Pour consulter les logs en temps réel :

```bash
tail -f logs/testboost.log | jq .
```

Les logs sont aussi accessibles via l'API :

```bash
curl -H "X-API-Key: $API_KEY" \
  "http://localhost:8000/api/v2/logs?level=error&per_page=50"
```

---

## Ressources Supplémentaires

- [Documentation API - Authentification](./api-authentication.md)
- [Documentation API - Erreurs](./api-errors.md)
- [Configuration LLM](./llm-providers.md)
- [Référence CLI](./cli-reference.md)
- [Architecture](./workflow-diagrams.md)
- [Monitoring](./operations.md)

## Support

- GitHub Issues : [github.com/axtion-io/TestBoost/issues](https://github.com/axtion-io/TestBoost/issues)
- Documentation : [docs/](../docs/)
