# E2E Acceptance Checklist: TestBoost Core

**Purpose**: Validation end-to-end des composants critiques
**Created**: 2025-12-04
**Feature**: [spec.md](../spec.md)

---

## DeepAgents Integration

| Status | Check | Description | Validated |
|--------|-------|-------------|-----------|
| [x] PASSING | LLM connectivity check | Connexion aux providers LLM (OpenAI/Anthropic) validée | 2025-12-04 @ `0707350` |
| [x] PASSING | Agent config validation | Configuration YAML DeepAgents validée | 2025-12-04 @ `0707350` |
| [x] PASSING | MCP tool binding | Liaison des outils MCP aux agents fonctionnelle | 2025-12-04 @ `0707350` |

---

## Workflow E2E

| Status | Check | Description | Validated |
|--------|-------|-------------|-----------|
| [ ] PENDING | Maven maintenance workflow | Workflow complet sur projet test |  |
| [ ] PENDING | Test generation workflow | Génération de tests avec mutation score ≥80% |  |
| [ ] PENDING | Docker deployment workflow | Déploiement conteneurisé fonctionnel |  |

---

## API E2E

| Status | Check | Description | Validated |
|--------|-------|-------------|-----------|
| [ ] PENDING | Session lifecycle | Création/exécution/completion d'une session |  |
| [ ] PENDING | Event streaming | SSE events en temps réel |  |
| [ ] PENDING | API authentication | X-API-Key validation |  |

---

## CLI E2E

| Status | Check | Description | Validated |
|--------|-------|-------------|-----------|
| [ ] PENDING | boost maintenance | Commande maintenance fonctionnelle |  |
| [ ] PENDING | boost tests | Commande test generation fonctionnelle |  |
| [ ] PENDING | boost deploy | Commande deployment fonctionnelle |  |

---

## Notes

- Validation DeepAgents effectuée le 2025-12-04
- Commit de référence: `0707350` (chore: Update .gitignore for test projects and docker cache)
