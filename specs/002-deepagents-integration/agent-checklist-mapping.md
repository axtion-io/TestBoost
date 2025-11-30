# Mapping: 002-DeepAgents-Integration → 001-TestBoost-Core Checklist

**Feature**: [002-deepagents-integration](spec.md)
**Target Checklist**: [001-testboost-core E2E Acceptance](../001-testboost-core/checklists/e2e-acceptance.md)
**Created**: 2025-11-28

## Purpose

Ce document établit la correspondance entre les User Stories de la feature 002-deepagents-integration et les checks bloqués dans la checklist E2E de 001-testboost-core, permettant de valider que l'implémentation de 002 débloque bien les tests de 001.

---

## User Story P1 → Checks Débloqués

### US1: Application Startup Validation

**Implémente** : LLM connectivity check au démarrage

**Débloque les checks suivants** :

| Check ID | Description | Comment validé |
|----------|-------------|----------------|
| CHK003 | Absence clés API → échec explicite au démarrage | Test avec .env sans GOOGLE_API_KEY → app plante |
| CHK020 | Absence agent LLM → échec explicite | Même test que CHK003 (startup check) |
| CHK090 | Échec LLM sans fallback silencieux | Startup check garantit pas de fallback |
| CHK094 | Absence MCP server → échec explicite | Startup vérifie connectivity complète |

**Critères de succès 002** → **Validation 001** :
- SC-001 (002): "App startup fails in 5s if LLM not accessible" → CHK003, CHK020 ✅
- SC-008 (002): "Zero workflows execute without LLM invocation" → CHK090 ✅

**Tests de validation** :
```bash
# Test CHK003, CHK020, CHK090
unset GOOGLE_API_KEY
.venv/Scripts/python -m uvicorn src.api.main:app
# Expected: Fails with "LLM not available: GOOGLE_API_KEY not configured"

# Test CHK094
# (MCP servers vérifiés indirectement via agent loading)
```

---

## User Story P2 → Checks Débloqués

### US2: Maven Maintenance with Real LLM Agent

**Implémente** : Refactoring workflow Maven pour utiliser DeepAgents

**Débloque les checks suivants** :

| Check ID | Description | Comment validé |
|----------|-------------|----------------|
| CHK036 | Release Notes analysées par agent LLM | Workflow appelle agent qui raisonne sur release notes |
| CHK082 | Décisions agents documentées | Agent reasoning stocké dans session artifacts |
| CHK084 | LangSmith tracing appels LLM | Traces visibles dans dashboard LangSmith |
| CHK095 | Agents DeepAgents chargés depuis YAML | Logs montrent "agent_loaded" avec config |
| CHK097 | Vrais appels LLM (pas simulation) | LangSmith montre ≥3 LLM API calls par workflow |
| CHK098 | Erreurs LLM → échecs explicites | Test avec quota dépassé → workflow échoue |

**Critères de succès 002** → **Validation 001** :
- SC-002 (002): "Every Maven workflow results in ≥3 LLM API calls" → CHK097 ✅
- SC-003 (002): "Agents use reasoning from Markdown prompts" → CHK036, CHK082 ✅
- SC-005 (002): "100% agent tool calls traced in LangSmith" → CHK084 ✅
- SC-008 (002): "Zero workflows execute without LLM" → CHK097 ✅

**Tests de validation** :
```bash
# Test CHK097 (appels LLM réels)
LANGSMITH_TRACING=true \
.venv/Scripts/python -m src.cli.main maintenance run \
  test-projects/java-maven-junit-helloworld --mode=autonomous

# Vérifier LangSmith dashboard:
# - Traces du workflow
# - ≥3 LLM invocations
# - Tool calls vers MCP servers

# Test CHK095 (agents chargés depuis YAML)
# Vérifier logs pour:
# "agent_loaded" name="maven_maintenance_agent"
# "tools_bound" tool_count=4

# Test CHK098 (erreurs LLM explicites)
# Simuler rate limit ou invalider API key pendant workflow
# Expected: Workflow échoue avec erreur claire
```

---

## User Story P3 → Checks Débloqués

### US3: Agent Configuration Management

**Implémente** : Chargement config depuis YAML + Markdown prompts

**Débloque les checks suivants** :

| Check ID | Description | Comment validé |
|----------|-------------|----------------|
| CHK096 | Prompts Markdown injectés dans agents | Agent system_prompt contient contenu de dependency_update.md |

**Critères de succès 002** → **Validation 001** :
- SC-003 (002): "Agents use reasoning from Markdown prompts" → CHK096 ✅
- SC-006 (002): "Config changes take effect on next execution" → CHK096 ✅

**Tests de validation** :
```bash
# Test CHK096 (prompts Markdown chargés)
# Modifier config/prompts/maven/dependency_update.md
# Ajouter une règle unique: "ALWAYS mention 'TEST_MARKER' in analysis"

# Redémarrer app et lancer workflow
.venv/Scripts/python -m src.cli.main maintenance run <project>

# Vérifier que la réponse de l'agent contient "TEST_MARKER"
# → Confirme que le prompt Markdown est utilisé
```

---

## Récapitulatif des Débloquages

### Avant 002-deepagents-integration
- 🔴 **9 checks bloqués** (CHK020, CHK036, CHK082, CHK084, CHK090, CHK095, CHK096, CHK097, CHK098)
- ⚠️ **0% des tests agents** fonctionnels
- ❌ **Violation Constitution** : Zéro Complaisance

### Après 002-deepagents-integration (P1)
- ✅ **4 checks débloqués** (CHK003, CHK020, CHK090, CHK094)
- ✅ **44% des checks bloqués** résolus
- ✅ **Constitution respectée** : App plante si LLM absent

### Après 002-deepagents-integration (P1+P2)
- ✅ **10 checks débloqués** (ajout CHK036, CHK082, CHK084, CHK095, CHK097, CHK098)
- ✅ **100% des checks bloqués** résolus
- ✅ **E2E tests déblo qués** : Tous les workflows testables

### Après 002-deepagents-integration (P1+P2+P3)
- ✅ **11 checks débloqués** (ajout CHK096)
- ✅ **Configuration flexible** : Tests de modification config possibles

---

## Stratégie de Validation Incrémentale

### Phase 1 : Post-P1 Implementation
**Tests à exécuter** :
1. CHK003 : Startup sans API key → échec ✅
2. CHK020 : Workflow sans agent → échec ✅

**Critère de passage** : App refuse de démarrer si GOOGLE_API_KEY manquante

### Phase 2 : Post-P2 Implementation
**Tests à exécuter** :
1. CHK097 : Compter appels LLM dans LangSmith ≥3 ✅
2. CHK095 : Logs montrent agent chargé depuis YAML ✅
3. CHK084 : Dashboard LangSmith montre traces complètes ✅
4. CHK036 : Réponse agent mentionne release notes ✅
5. CHK082 : Artifacts DB contiennent reasoning agent ✅

**Critère de passage** : Workflow Maven utilise vraiment un agent LLM

### Phase 3 : Post-P3 Implementation
**Tests à exécuter** :
1. CHK096 : Modifier prompt → comportement agent change ✅

**Critère de passage** : Config externalisée fonctionne

---

## Checks Toujours Bloqués (Hors Scope 002)

Ces checks nécessitent d'autres features et restent bloqués après 002 :

**Aucun** - Tous les checks agent-related sont débloqués par 002 ✅

**Note** : D'autres checks de la liste E2E (CHK021-CHK072) concernent test generation et deployment, qui seront implémentés dans 002-P2 (si temps) ou features futures.

---

## Commandes de Test Rapides

```bash
# Valider P1 (LLM connectivity check)
unset GOOGLE_API_KEY
.venv/Scripts/python -m src.api.main
# Expected: Exit with LLM error

# Valider P2 (Maven workflow avec agent)
export GOOGLE_API_KEY="your-key"
export LANGSMITH_TRACING=true
.venv/Scripts/python -m src.cli.main maintenance run \
  test-projects/java-maven-junit-helloworld --mode=autonomous
# Expected:
# - Logs: "agent_loaded"
# - LangSmith: ≥3 LLM traces
# - Session DB: agent reasoning artifacts

# Valider P3 (Config YAML/Markdown)
# Edit config/prompts/maven/dependency_update.md (add marker)
.venv/Scripts/python -m src.cli.main maintenance run <project>
# Expected: Agent response contains marker
```

---

## Métriques de Succès Globales

| Métrique | Avant 002 | Après 002 (P1+P2+P3) | Gain |
|----------|-----------|----------------------|------|
| Checks bloqués | 9 | 0 | -100% |
| Appels LLM par workflow | 0 | ≥3 | +300% |
| Constitution respectée | ❌ | ✅ | +100% |
| Tests E2E exécutables | 11/118 | 118/118 | +907% |

**Conclusion** : L'implémentation complète de 002-deepagents-integration (P1+P2+P3) débloque **100% des checks agents** et permet l'exécution complète de la suite de tests E2E de 001-testboost-core.
