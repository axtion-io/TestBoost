# TestBoost - Guide Utilisateur

Ce guide vous accompagne pas à pas dans l'utilisation de TestBoost, un outil d'automatisation de maintenance pour les projets Java/Spring Boot.

## Table des Matières

1. [Installation Rapide](#installation-rapide)
2. [Premier Workflow](#premier-workflow)
3. [Workflows Disponibles](#workflows-disponibles)
4. [Modes d'Exécution](#modes-dexécution)
5. [Intégration CI/CD](#intégration-cicd)
6. [Troubleshooting](#troubleshooting)

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
git clone https://github.com/cheche71/TestBoost.git
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

### Exemple : Maintenance Maven sur spring-petclinic

#### 1. Cloner un Projet de Test

```bash
git clone https://github.com/spring-projects/spring-petclinic.git test-projects/spring-petclinic
```

#### 2. Lancer l'Analyse

```bash
python -m src.cli.main maintenance list test-projects/spring-petclinic
```

**Sortie attendue :**

```
TestBoost - Maven Maintenance
=============================

Analyzing project: test-projects/spring-petclinic

Dependencies Analysis:
----------------------
[SECURITY] org.springframework.boot:spring-boot-starter-web
           Current: 3.1.0 -> Available: 3.2.1
           CVE-2023-XXXXX: High severity

[MAJOR] org.projectlombok:lombok
        Current: 1.18.24 -> Available: 1.18.30
        Breaking changes: None detected

[MINOR] com.h2database:h2
        Current: 2.1.214 -> Available: 2.2.220
        Safe upgrade

Summary: 3 updates available (1 security, 1 major, 1 minor)
```

#### 3. Appliquer les Mises à Jour

```bash
# Mode interactif (confirmation avant chaque action)
python -m src.cli.main maintenance run test-projects/spring-petclinic

# Mode autonome (CI/CD)
python -m src.cli.main maintenance run test-projects/spring-petclinic --mode autonomous
```

#### 4. Interpréter les Résultats

Le workflow génère un rapport dans `logs/` :

```
Maintenance Report
==================
Session ID: abc123-def456
Duration: 2m 34s
Status: SUCCESS

Updates Applied:
- spring-boot-starter-web: 3.1.0 -> 3.2.1 [OK]
- lombok: 1.18.24 -> 1.18.30 [OK]
- h2: 2.1.214 -> 2.2.220 [OK]

Tests: 45 passed, 0 failed
Branch: maintenance/2024-01-15

Next Steps:
1. Review changes on branch 'maintenance/2024-01-15'
2. Run integration tests manually
3. Create pull request when ready
```

---

## Workflows Disponibles

### 1. Maven Maintenance

**Objectif** : Mettre à jour les dépendances Maven avec non-régression garantie.

```bash
# Lister les dépendances obsolètes
python -m src.cli.main maintenance list <project_path>

# Appliquer les mises à jour
python -m src.cli.main maintenance run <project_path> [--mode autonomous]

# Vérifier le statut d'une session
python -m src.cli.main maintenance status <session_id>
```

**Options** :
- `--skip-security` : Ignorer les mises à jour de sécurité
- `--skip-major` : Ignorer les mises à jour majeures
- `--dry-run` : Afficher sans appliquer

### 2. Test Generation

**Objectif** : Générer une suite de tests complète pour le code existant.

```bash
# Générer des tests pour tout le projet
python -m src.cli.main tests generate <project_path>

# Générer pour un fichier spécifique
python -m src.cli.main tests generate <project_path> --target src/main/java/com/example/Service.java

# Avec mutation testing
python -m src.cli.main tests generate <project_path> --mutation-score 80
```

**Options** :
- `--include-integration` : Inclure les tests d'intégration
- `--include-snapshot` : Inclure les tests snapshot
- `--output-dir` : Répertoire de sortie
- `--verbose` : Affichage détaillé

### 3. Docker Deployment

**Objectif** : Déployer l'application dans Docker pour validation.

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

**Options** :
- `--dependency/-d` : Services dépendants (postgres, mysql, redis, mongodb)
- `--endpoint/-e` : Endpoint de health check
- `--skip-health` : Ignorer la validation health check

### 4. Impact Analysis

**Objectif** : Analyser l'impact des modifications de code pour cibler les tests.

```bash
# Analyser les changements uncommitted
python -m src.cli.main tests impact <project_path>

# Générer rapport JSON pour CI
python -m src.cli.main tests impact <project_path> --output impact-report.json
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

---

## Ressources Supplémentaires

- [Documentation API](./api-authentication.md)
- [Configuration LLM](./llm-providers.md)
- [Référence CLI](./cli-reference.md)
- [Architecture](./workflow-diagrams.md)
- [Monitoring](./operations.md)

## Support

- GitHub Issues : [github.com/cheche71/TestBoost/issues](https://github.com/cheche71/TestBoost/issues)
- Documentation : [docs/](../docs/)

