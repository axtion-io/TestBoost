# Research: TestBoost Core

**Date**: 2025-11-23
**Feature**: 001-testboost-core

## Technology Decisions

### 1. Orchestration Framework

**Decision**: LangGraph
**Rationale**: Framework natif LangChain pour orchestrer des workflows d'agents avec état partagé. Support natif des graphes conditionnels, checkpointing, et human-in-the-loop.
**Alternatives considered**:
- CrewAI: Plus haut niveau mais moins de contrôle sur le flow
- Orchestration directe Python: Plus de code boilerplate, pas de checkpointing natif
- Temporal.io: Over-engineering pour ce use case

### 2. Agent Configuration

**Decision**: DeepAgents (YAML + Markdown prompts)
**Rationale**: Pattern config-first permettant d'itérer sur le comportement des agents sans recompiler. Séparation claire entre configuration (YAML) et expertise (Markdown prompts).
**Alternatives considered**:
- Agents codés en dur: Moins flexible, nécessite redéploiement pour chaque changement
- JSON config: Moins lisible que YAML pour les prompts multi-lignes

### 3. LLM Provider

**Decision**: Multi-provider avec défaut Gemini 2.5 Flash
**Rationale**: Flexibilité pour choisir le meilleur modèle selon le use case. Gemini offre bon rapport qualité/prix pour génération de code.
**Alternatives considered**:
- Provider unique: Vendor lock-in, pas de fallback
- OpenAI uniquement: Plus cher, quotas plus restrictifs

**Providers supportés**:
- `google-genai/gemini-2.5-flash-preview-09-2025` (défaut)
- `anthropic/claude-4.5-sonnet`
- `google-genai/gemini-3-pro`
- `openai/gpt-4o`

### 4. API Framework

**Decision**: FastAPI
**Rationale**: Performance async native, validation Pydantic intégrée, documentation OpenAPI automatique, écosystème Python riche.
**Alternatives considered**:
- Flask: Pas async natif
- Django REST: Over-engineering pour une API
- Starlette: FastAPI est basé dessus avec plus de features

### 5. Database

**Decision**: PostgreSQL 15+
**Rationale**: Robuste, support JSON natif pour event sourcing, extensions utiles (uuid-ossp, pg_trgm), excellente performance.
**Alternatives considered**:
- SQLite: Pas de concurrence multi-process
- MongoDB: Over-engineering pour le schéma relationnel des sessions
- MySQL: Moins de features que PostgreSQL

### 6. ORM

**Decision**: SQLAlchemy 2.0 + Alembic
**Rationale**: Standard Python, support async, migrations robustes, mapping objet-relationnel mature.
**Alternatives considered**:
- Raw SQL: Plus de code, pas de migrations
- Tortoise ORM: Moins mature
- Prisma Python: Beta, moins d'écosystème

### 7. CLI Framework

**Decision**: Typer
**Rationale**: Basé sur Click avec type hints Python, auto-complétion, documentation automatique.
**Alternatives considered**:
- Click: Plus verbeux
- argparse: Primitif
- Fire: Moins de contrôle sur l'interface

### 8. Observability

**Decision**: LangSmith + Logs structurés JSON
**Rationale**: LangSmith est la solution native LangChain pour tracer les agents. Logs JSON permettent l'agrégation dans n'importe quel système.
**Alternatives considered**:
- OpenTelemetry complet: Over-engineering pour le MVP
- Logs texte: Pas d'agrégation facile

### 9. MCP Implementation

**Decision**: mcp Python SDK
**Rationale**: SDK officiel pour Model Context Protocol, intégration native avec LangChain.
**Alternatives considered**:
- Implémentation custom: Maintenance supplémentaire
- REST endpoints: Pas le standard MCP

### 10. Testing Framework

**Decision**: pytest + pytest-asyncio + pytest-cov
**Rationale**: Standard Python, support async, plugins riches, intégration CI/CD.
**Alternatives considered**:
- unittest: Plus verbeux
- nose2: Moins d'écosystème

## Best Practices Applied

### LangGraph Workflows
- Utiliser `StateGraph` pour l'état partagé entre nodes
- Implémenter checkpointing pour reprise après interruption
- Définir des edges conditionnels pour branching
- Utiliser `interrupt_before` pour human-in-the-loop

### DeepAgents Pattern
- Un fichier YAML par agent
- Prompts séparés en Markdown pour réutilisation
- Variables d'environnement pour config runtime (MODEL)
- Temperature basse (0.2) pour génération de code déterministe

### MCP Servers
- Un serveur par domaine fonctionnel
- Outils atomiques et composables
- Validation Pydantic des inputs/outputs
- Timeouts explicites par catégorie d'outil

### FastAPI Best Practices
- Routers séparés par domaine
- Dependency injection pour DB/auth
- Middleware pour logging/CORS
- Health check endpoint

### PostgreSQL Event Sourcing
- Table events append-only
- Snapshots pour performance
- Index sur session_id et timestamp
- Retention policy via partition ou scheduled job

## Dependencies Versions

**Updated**: 2025-11-23 (latest stable versions)

```toml
[tool.poetry.dependencies]
python = "^3.10"  # Required by LangGraph/LangChain 1.0
fastapi = "^0.121"
uvicorn = "^0.38"
sqlalchemy = "^2.0"  # Latest: 2.0.44
alembic = "^1.17"
asyncpg = "^0.30"
pydantic = "^2.12"
pydantic-settings = "^2.7"
langgraph = "^1.0"  # Major v1.0 release
langchain = "^1.0"  # Major v1.0 release
langchain-core = "^1.1"
langchain-google-genai = "^2.1"
langchain-anthropic = "^1.1"
langchain-openai = "^1.0"
mcp = "^1.22"  # MCP SDK from Anthropic
typer = "^0.20"
httpx = "^0.28"
structlog = "^25.5"

[tool.poetry.group.dev.dependencies]
pytest = "^9.0"
pytest-asyncio = "^0.24"
pytest-cov = "^6.0"
black = "^24.10"
ruff = "^0.8"
mypy = "^1.13"
```

### Notable Version Changes

| Package | Old | New | Notes |
|---------|-----|-----|-------|
| langgraph | 0.0.40 | 1.0.3 | Major v1.0 release - API stable |
| langchain | 0.1 | 1.0.8 | Major v1.0 release - focus on agent loop |
| mcp | 0.1 | 1.22 | MCP SDK matured significantly |
| Python | 3.11 | 3.10+ | LangGraph 1.0 dropped Python 3.9 |

## Open Questions Resolved

| Question | Resolution |
|----------|------------|
| Source données CVE | OSV (Open Source Vulnerabilities) via API gratuite |
| Format snapshots tests | JSON + ApprovalTests pattern (fichiers .approved) |
| Stratégie cache | In-memory LRU pour contexte projet (durée session) |
| Queue verrou projet | Redis ou PostgreSQL SKIP LOCKED (à décider en implem) |
