# GitHub Actions CI/CD

Ce dossier contient les workflows GitHub Actions pour l'intégration continue (CI) de TestBoost.

## Workflows Disponibles

### `ci.yml` - Continuous Integration

**Déclenchement automatique:**
- Push sur les branches: `main`, `develop`, `002-deepagents-integration`
- Pull requests vers: `main`, `develop`
- Déclenchement manuel via l'interface GitHub (workflow_dispatch)

**Jobs exécutés:**

#### 1. `test` - Tests Automatisés
Matrice Python: 3.11, 3.12

**Tests exécutés:**
- ✅ **Unit Tests** - Tests unitaires avec coverage
- ✅ **Integration Tests** - Tests d'intégration (sans LLM réel)
- ✅ **Regression Tests** (T097a) - Validation compatibilité backward
- ✅ **Security Audit** (T101a) - Vérification absence de clés API hardcodées
- ✅ **Documentation Tests** (T103b-e) - Validation documentation complète
- ✅ **Edge Case Tests** (T105b-f) - Tests cas limites (rate limits, retry, etc.)

**Coverage:**
- Rapports de couverture uploadés vers Codecov
- Coverage badge disponible dans README.md

#### 2. `lint` - Qualité de Code
- **Ruff** - Linter Python moderne (formatage, style, erreurs)
- **mypy** - Vérification de typage statique

#### 3. `e2e-manual` - Tests E2E avec LLM Réel
**⚠️ Déclenchement manuel uniquement** (coûts API LLM)

**Prérequis:**
- Secrets GitHub configurés:
  - `GOOGLE_API_KEY` - Clé API Google Gemini
  - `LANGSMITH_API_KEY` - Clé API LangSmith (tracing)

**Tests exécutés:**
- Tests E2E Maven maintenance workflow
- Tests E2E Test generation workflow
- Tests E2E Docker deployment workflow

## Configuration des Secrets

**⚠️ Note Importante**: Les tests E2E avec LLM réel ne sont **PAS exécutés dans GitHub Actions** pour les raisons suivantes:
- Coûts API (Google Gemini, LangSmith)
- Sécurité (pas de clés API stockées dans GitHub)
- Fiabilité (dépendance externe aux services LLM)

**Les tests E2E sont exécutés manuellement en local** par les développeurs avant les merges importants.

## Tests Exclus du CI Automatique

Les tests suivants nécessitent des ressources externes et sont exclus:

- **E2E tests avec LLM réel** - Coûts API (manuel uniquement)
- **Performance tests** (T098) - Nécessitent infrastructure dédiée
- **Provider switching tests** (T102a-e) - Nécessitent multiples API keys

## Exécution Locale

Pour reproduire les tests CI localement:

```bash
# Tous les tests (sans E2E LLM)
poetry run pytest tests/unit/ tests/integration/ tests/regression/ tests/security/ tests/e2e/test_edge_cases.py -v

# Avec coverage
poetry run pytest tests/unit/ --cov=src --cov-report=html

# Tests E2E avec LLM (nécessite GOOGLE_API_KEY)
export GOOGLE_API_KEY=your_key
poetry run pytest tests/e2e/test_real_llm_invocation.py -v
```

## Badges de Statut

Ajoutez ces badges dans votre README.md:

```markdown
![CI Status](https://github.com/YOUR_ORG/TestBoost/workflows/CI%20-%20TestBoost%20Tests/badge.svg)
![Coverage](https://codecov.io/gh/YOUR_ORG/TestBoost/branch/main/graph/badge.svg)
```

## Maintenance

### Ajout d'un nouveau test au CI

1. Créer le test dans `tests/`
2. Le workflow détectera automatiquement les nouveaux tests
3. Pour ajouter un groupe de tests spécifique, modifier [ci.yml](workflows/ci.yml)

### Mise à jour des dépendances Python

Le cache pip est automatiquement géré via `actions/cache@v4` basé sur `pyproject.toml`.

### Troubleshooting

**Problème**: Tests échouent en CI mais passent en local
- Vérifier les versions Python (CI utilise 3.11 et 3.12)
- Vérifier les variables d'environnement manquantes
- Consulter les logs détaillés dans l'onglet Actions

**Problème**: Coverage non uploadé vers Codecov
- Vérifier que le token Codecov est configuré (secret `CODECOV_TOKEN`)
- Le job continue même si l'upload échoue (`continue-on-error: true`)

## Références

- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Poetry Documentation](https://python-poetry.org/docs/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Codecov Documentation](https://docs.codecov.com/)
