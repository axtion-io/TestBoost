# Feature: Améliorer la couverture de tests de 28% à 50%

## Contexte

La couverture de tests actuelle est de **28.48%** avec 343 tests passants. L'objectif est d'atteindre **50%** de couverture.

## Zones bien couvertes (>50%)

| Module | Couverture |
|--------|------------|
| `src/lib/` | 70-95% |
| `src/api/` | 60-80% |
| `src/models/` | 62-79% |
| `src/db/` | 55-80% |

## Zones à améliorer (<15%)

| Module | Couverture | Priorité |
|--------|------------|----------|
| `src/workflows/impact_analysis.py` | **0%** | P1 |
| `src/mcp_servers/maven_maintenance/tools/` | 7-11% | P2 |
| `src/mcp_servers/docker/tools/` | 5-8% | P2 |
| `src/mcp_servers/test_generator/tools/` | 3-12% | P2 |
| `src/mcp_servers/git_maintenance/tools/` | 9-11% | P3 |
| `src/mcp_servers/pit_recommendations/tools/` | 7-8% | P3 |
| `src/workflows/test_generation_agent.py` | 12% | P2 |

## Stratégie recommandée

### Phase 1: Impact Analysis (0% → 50%)
- Mocker les appels Git et file system
- Tester les cas: changements détectés, aucun changement, erreurs

### Phase 2: MCP Server Tools (5-15% → 40%)
- Créer des fixtures pour les sorties Maven/Docker/Git
- Mocker `subprocess.run` pour simuler les commandes externes
- Tester les parsing de résultats (POM, logs, diffs)

### Phase 3: Test Generation Workflow (12% → 40%)
- Mocker les appels LLM
- Tester les différents modes (unit, integration, snapshot)
- Tester le fallback template

## Critères d'acceptation

- [ ] Couverture globale ≥ 50%
- [ ] Aucun module critique à 0%
- [ ] Tests unitaires pour tous les MCP tools
- [ ] CI passe avec le nouveau seuil (50%)

## Notes techniques

- Les MCP tools exécutent des commandes externes (Maven, Docker, Git)
- Utiliser `unittest.mock.patch` pour `subprocess.run`
- Les fixtures existantes dans `tests/fixtures/` peuvent être étendues

## Estimation

- Phase 1: ~20 tests à ajouter
- Phase 2: ~50 tests à ajouter (10 par module MCP)
- Phase 3: ~15 tests à ajouter

**Total estimé**: ~85 nouveaux tests
