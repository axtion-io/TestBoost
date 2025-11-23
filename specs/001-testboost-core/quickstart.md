# Quickstart: TestBoost

## Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Git
- Java 8+ (pour analyser les projets Maven)
- Maven (ou le projet cible doit avoir mvnw)

## Installation

### 1. Clone et setup

```bash
git clone <repository>
cd TestBoost

# Créer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou .venv\Scripts\activate  # Windows

# Installer les dépendances
pip install poetry
poetry install
```

### 2. Configuration

Copier et éditer le fichier d'environnement :

```bash
cp .env.example .env
```

Variables requises :

```env
# Database
DATABASE_URL=postgresql://testboost:testboost@localhost:5432/testboost_db

# API
API_KEY=your-secure-api-key

# LLM Provider (défaut Gemini)
MODEL=google-genai/gemini-2.5-flash-preview-09-2025
GOOGLE_API_KEY=your-google-api-key

# Optionnel: autres providers
# ANTHROPIC_API_KEY=your-anthropic-key
# OPENAI_API_KEY=your-openai-key

# Observability
LANGSMITH_API_KEY=your-langsmith-key
LANGSMITH_PROJECT=testboost
```

### 3. Base de données

```bash
# Démarrer PostgreSQL via Docker
docker-compose up -d postgres

# Appliquer les migrations
alembic upgrade head
```

### 4. Démarrer les services

```bash
# API (port 8000)
uvicorn src.api.main:app --reload

# Ou via Docker Compose complet
docker-compose up -d
```

## Usage

### CLI

```bash
# Maintenance Maven (via Python module)
python -m src.cli.main maintenance /path/to/maven/project

# Or using the boost command if installed via pip
boost maintenance /path/to/maven/project

# Génération de tests
boost generate /path/to/maven/project --types unit,integration

# Déploiement Docker
boost deploy /path/to/maven/project

# Audit seul (pas de modification)
boost audit /path/to/maven/project

# Check session status
boost status [session_id]
```

### API

```bash
# Health check
curl http://localhost:8000/api/testboost/health

# Créer une session de maintenance
curl -X POST http://localhost:8000/api/v2/sessions \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "project_path": "/path/to/maven/project",
    "project_name": "my-project",
    "session_type": "maven_maintenance",
    "mode": "interactive"
  }'

# Lister les sessions
curl http://localhost:8000/api/v2/sessions \
  -H "X-API-Key: your-api-key"

# Voir le détail d'une session
curl http://localhost:8000/api/v2/sessions/{session_id} \
  -H "X-API-Key: your-api-key"
```

## Modes d'exécution

| Mode | Description | Usage |
|------|-------------|-------|
| `interactive` | Demande confirmation aux étapes critiques | Développement local |
| `autonomous` | Exécute sans intervention | CI/CD |
| `analysis_only` | Génère rapport sans modifier | Audit |
| `debug` | Logs détaillés, pause entre étapes | Diagnostic |

## Structure projet cible

TestBoost attend un projet Maven standard :

```
my-project/
├── pom.xml
├── src/
│   ├── main/java/
│   └── test/java/
└── [mvnw ou Maven système]
```

## Exemples de workflows

### Maintenance Maven complète

```bash
# Mode interactif avec validation utilisateur
boost maintenance --project-path ./my-spring-app --mode interactive

# Mode autonome pour CI/CD
boost maintenance --project-path ./my-spring-app --mode autonomous
```

### Génération de tests multi-couches

```bash
# Tous les types de tests
boost tests --project-path ./my-spring-app --types unit,integration,snapshot,e2e,mutation

# Tests unitaires uniquement
boost tests --project-path ./my-spring-app --types unit
```

## CLI Exit Codes

| Code | Signification | Action recommandée |
|------|---------------|-------------------|
| 0 | Succès | - |
| 1 | Erreur générale | Consulter les logs |
| 2 | Arguments invalides | Vérifier la syntaxe de la commande |
| 3 | Projet non trouvé | Vérifier le chemin du projet |
| 4 | Projet verrouillé | Attendre ou annuler la session existante |
| 5 | Tests baseline échoués | Corriger les tests existants |
| 6 | Erreur LLM | Vérifier les credentials et quotas |
| 7 | Erreur Docker | Vérifier que Docker est démarré |
| 8 | Timeout | Augmenter le timeout ou simplifier l'opération |

## Troubleshooting

### Projet verrouillé

```
Error: Project is locked by session {uuid}
```

Un autre workflow est en cours sur ce projet. Attendez ou annulez la session existante.

### Tests échouent avant maintenance

```
Error: Baseline tests failed - maintenance aborted
```

Le projet doit être stable (tous tests verts) avant maintenance. Corrigez les tests existants.

### LLM timeout

Augmentez le timeout dans la config de l'agent ou utilisez un modèle plus rapide.

## Documentation

- [API Reference](./contracts/openapi.yaml)
- [Data Model](./data-model.md)
- [Architecture](./plan.md)
- [Constitution](../../.specify/memory/constitution.md)
