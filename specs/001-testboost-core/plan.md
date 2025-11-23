# Implementation Plan: TestBoost Core

**Branch**: `001-testboost-core` | **Date**: 2025-11-23 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-testboost-core/spec.md`

## Summary

TestBoost automatise la maintenance des applications Java/Spring Boot avec génération de tests multi-couches, maintenance Maven, et déploiement Docker. L'architecture utilise LangGraph pour l'orchestration des workflows, DeepAgents pour la configuration des agents IA, et des serveurs MCP pour exposer les outils de manière traçable et testable.

## Technical Context

**Language/Version**: Python 3.10+ (LangGraph 1.0 requirement)
**Primary Dependencies**:
- LangGraph (orchestration workflows)
- LangChain + DeepAgents (configuration agents)
- FastAPI (REST API)
- MCP SDK (Model Context Protocol servers)
- Pydantic (validation)

**Storage**: PostgreSQL 15+ (sessions, événements, historique)
**Testing**: pytest + pytest-asyncio + pytest-cov
**Target Platform**: Linux server / Windows / macOS (Docker)
**Project Type**: Web application (backend API + CLI)
**Performance Goals**:
- Opérations interactives < 5 secondes
- Analyse projet 200 classes < 30 secondes
- Déploiement Docker < 5 minutes

**Constraints**:
- Rétention données : 1 an
- Verrou exclusif par projet
- Multi-provider LLM (défaut: gemini-2.5-flash-preview-09-2025)

**Scale/Scope**:
- Projets Maven jusqu'à 500 classes
- Sessions concurrentes sur projets différents
- Historique 1 an

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principe | Statut | Implémentation |
|----------|--------|----------------|
| 1. Zéro Complaisance | ✅ PASS | Erreurs explicites, pas de faux positifs, logs réels uniquement |
| 2. Outils via MCP | ✅ PASS | Tous les outils exposés via serveurs MCP dédiés |
| 3. Pas de Mocks Production | ✅ PASS | Mocks réservés aux tests automatisés uniquement |
| 4. Automatisation + Contrôle | ✅ PASS | Modes interactif/autonome, confirmations, rollback |
| 5. Traçabilité Complète | ✅ PASS | Journal immutable, LangSmith, logs structurés JSON |
| 6. Validation Avant Modification | ✅ PASS | Baseline tests, backup pom.xml, vérification état |
| 7. Isolation et Sécurité | ✅ PASS | Branches dédiées, commits atomiques, verrou projet |
| 8. Découplage et Modularité | ✅ PASS | Serveurs MCP indépendants, agents configurables |
| 9. Transparence des Décisions | ✅ PASS | Rapports détaillés, justification recommandations |
| 10. Robustesse | ✅ PASS | Retry avec backoff, gestion timeouts, pas de crash silencieux |
| 11. Performance Raisonnable | ✅ PASS | Objectifs définis, cache intelligent, feedback progression |
| 12. Respect Standards Projet | ✅ PASS | Détection conventions, adaptation style existant |
| 13. Simplicité d'Utilisation | ✅ PASS | CLI + API, valeurs par défaut, config minimale |

**Gate Status**: ✅ ALL PASSED - Proceed to Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/001-testboost-core/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI specs)
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── api/                     # FastAPI REST API
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── routers/
│   │   ├── sessions.py      # /api/v2/sessions
│   │   └── testboost.py     # /api/testboost
│   ├── models/              # Pydantic request/response
│   └── middleware/          # Auth, logging
│
├── core/                    # Domain logic
│   ├── __init__.py
│   ├── session.py           # Session management
│   ├── workflow.py          # Workflow execution
│   └── events.py            # Event sourcing
│
├── workflows/               # LangGraph workflows
│   ├── __init__.py
│   ├── maven_maintenance.py # Maven update workflow
│   ├── test_generation.py   # Test gen workflow
│   └── docker_deployment.py # Docker workflow
│
├── agents/                  # DeepAgents configuration
│   ├── __init__.py
│   ├── loader.py            # YAML/MD loader
│   └── adapter.py           # LangGraph adapter
│
├── mcp_servers/             # MCP tool servers
│   ├── __init__.py
│   ├── test_generator/      # Test generation tools
│   ├── maven_maintenance/   # Maven tools
│   ├── git_maintenance/     # Git tools
│   ├── docker/              # Docker tools
│   └── pit_recommendations/ # PIT analysis tools
│
├── db/                      # Database layer
│   ├── __init__.py
│   ├── models.py            # SQLAlchemy models
│   ├── repository.py        # Data access
│   └── migrations/          # Alembic migrations
│
├── cli/                     # CLI commands
│   ├── __init__.py
│   └── main.py              # Click/Typer CLI
│
└── lib/                     # Shared utilities
    ├── __init__.py
    ├── logging.py           # Structured JSON logging
    └── config.py            # Configuration management

config/
├── agents/                  # DeepAgents YAML configs
│   ├── test_gen_agent.yaml
│   └── deployment_agent.yaml
└── prompts/                 # Agent prompts (Markdown)
    ├── common/
    │   └── java_expert.md
    ├── testing/
    │   ├── unit_test_strategy.md
    │   └── integration_strategy.md
    └── deployment/
        └── docker_guidelines.md

tests/
├── unit/                    # Unit tests
│   ├── test_session.py
│   └── test_workflow.py
├── integration/             # Integration tests
│   ├── test_api.py
│   └── test_mcp_servers.py
└── contract/                # Contract tests
    └── test_api_contracts.py
```

**Structure Decision**: Web application avec backend Python (FastAPI + LangGraph) exposant une API REST et CLI. Les serveurs MCP sont des modules Python indépendants. Les agents sont configurés via YAML/Markdown (DeepAgents pattern).

## Architecture Components

### Workflows (LangGraph)

Trois workflows principaux orchestrés via LangGraph avec état partagé :

1. **Maven Maintenance** (10 étapes)
   - validate_project → check_git_status → analyze_maven → run_baseline_tests → user_validation → create_maintenance_branch → apply_update_batch → validate_changes → commit_changes → finalize

2. **Test Generation** (14 étapes)
   - analyze_project_structure → classify_classes → generate_unit_tests → compile_and_fix_unit → generate_integration_tests → compile_and_fix_integration → generate_snapshot_tests → compile_and_fix_snapshot → deploy_docker → check_app_health → generate_e2e_tests → run_mutation_testing → generate_killer_tests → finalize

3. **Docker Deployment** (8 étapes)
   - analyze_project → generate_dockerfile → generate_docker_compose → build_image → run_container → check_health → validate_endpoints → finalize

### Step Transitions

Conditions de transition entre étapes (appliquées à tous les workflows) :

| Transition | Condition | Action si échec |
|------------|-----------|-----------------|
| → next step | `status == completed` AND `outputs valid` | Reste sur l'étape courante |
| → failed | `retry_count >= 3` OR `error.critical == true` | Workflow → failed |
| → rollback | `error.recoverable == true` AND `backup exists` | Restaure état précédent |
| → user_validation | `mode == interactive` AND `step.requires_confirmation` | Pause workflow |

**États finaux des workflows** :
- `completed` : Toutes les étapes terminées avec succès
- `failed` : Erreur non récupérable ou max retries atteint
- `cancelled` : Annulation utilisateur ou timeout global

### Docker Container Lifecycle

Cycle de vie des containers pour les projets Maven :

1. **Création** : Container créé au démarrage du workflow avec image Java/Maven appropriée
2. **Volume Mounting** :
   - `${PROJECT_PATH}:/workspace` (read-write) - code source
   - `${MAVEN_CACHE}:/root/.m2` (read-write) - cache Maven partagé
3. **Exécution** : Tous les builds/tests Maven s'exécutent dans le container
4. **Destruction** : Container supprimé à la fin du workflow (succès ou échec)
5. **Nettoyage** : Images orphelines purgées périodiquement (cron)

### MCP Servers

| Serveur | Outils | Dépendances |
|---------|--------|-------------|
| Test Generator | analyze-project-context, detect-test-conventions, generate-adaptive-tests, generate-integration-tests, generate-snapshot-tests, run-mutation-testing, analyze-mutants, generate-killer-tests | Gemini API (optionnel) |
| PIT Recommendations | analyze-hard-mutants, recommend-test-improvements, prioritize-test-efforts | Aucune |
| Maven Maintenance | compile-tests, run-tests, package, clean, analyze-dependencies | Maven |
| Git Maintenance | create-maintenance-branch, commit-changes, get-status | Git |
| Docker | create-dockerfile, create-compose, deploy-compose | Docker |

### Agent Configuration (DeepAgents)

```yaml
# config/agents/test_gen_agent.yaml
name: test_gen_agent
description: "Agent spécialisé génération tests Java/Spring Boot"
model: ${MODEL:-google-genai/gemini-2.5-flash-preview-09-2025}
temperature: 0.2
max_iterations: 15

tools:
  - analyze_project_context
  - detect_test_conventions
  - generate_adaptive_tests
  - generate_integration_tests
  - run_mutation_testing

prompts:
  - common/java_expert.md
  - testing/unit_test_strategy.md
  - testing/integration_strategy.md
```

### Observability

- **LangSmith**: Tracing agents et workflows LLM
- **Logs structurés JSON**: Application (FastAPI, MCP servers)
- **PostgreSQL**: Event sourcing pour audit trail

## Complexity Tracking

> No violations detected - all design decisions align with constitution principles.

## Next Steps

1. **Phase 0**: Generate `research.md` with technology decisions
2. **Phase 1**: Generate `data-model.md`, `contracts/`, `quickstart.md`
3. **Phase 2**: Run `/speckit.tasks` to generate implementation tasks
