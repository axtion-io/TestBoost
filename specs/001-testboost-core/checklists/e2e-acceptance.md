# End-to-End Acceptance Testing Checklist: TestBoost Core

**Purpose**: Tests d'acceptation réels avec agents LLM sur les 3 projets Java de test
**Created**: 2025-11-28
**Updated**: 2025-11-28
**Depth**: Comprehensive
**Feature**: [spec.md](../spec.md)

**STATUS**: 🔴 **BLOQUÉ** - En attente de [002-deepagents-integration](../../002-deepagents-integration/spec.md)

**IMPORTANT**: Ces tests doivent être exécutés **en réel** avec de vrais agents LLM configurés. L'application **doit planter** si les agents ne sont pas disponibles (principe Zéro Complaisance).

---

## ⚠️ PRÉREQUIS BLOQUANT - Agent LLM Integration

**PROBLÈME IDENTIFIÉ** (2025-11-28): L'implémentation actuelle de TestBoost **ne respecte pas les exigences de cette checklist** car les workflows LangGraph appellent directement les outils MCP sans utiliser d'agents LLM. Cela viole le principe constitutionnel "Zéro Complaisance".

**ANALYSE COMPLÈTE**: Voir [specs/001-testboost-core/analysis-deepagents-integration.md](../analysis-deepagents-integration.md) (si créé)

### Checks Bloqués (9 items critiques)

Les tests suivants **NE PEUVENT PAS PASSER** tant que 002-deepagents-integration n'est pas implémenté :

**Agent LLM Execution:**
- [ ] ~~CHK020~~ - Absence agent LLM → échec explicite ❌ *Workflows s'exécutent sans agents*
- [ ] ~~CHK036~~ - Release Notes analysées par agent LLM ❌ *Pas d'appels LLM*
- [ ] ~~CHK082~~ - Décisions agents documentées ❌ *Pas d'agents*
- [ ] ~~CHK084~~ - LangSmith tracing appels LLM ❌ *0 appels LLM à tracer*
- [ ] ~~CHK090~~ - Échec LLM sans fallback silencieux ❌ *Pas d'appels LLM*
- [ ] ~~CHK095~~ - Agents DeepAgents chargés depuis YAML ❌ *AgentLoader jamais appelé*
- [ ] ~~CHK096~~ - Prompts Markdown injectés dans agents ❌ *Prompts jamais chargés*
- [ ] ~~CHK097~~ - Vrais appels LLM (pas simulation) ❌ **0 appels LLM constatés**
- [ ] ~~CHK098~~ - Erreurs LLM provoquent échecs explicites ❌ *Pas d'appels LLM*

**Impact**: 🔴 **9 checks bloqués** / 118 total (8%)

### Conditions de Déblocage

✅ **Feature 002-deepagents-integration doit être complétée** avec :

1. **P1 - LLM Connectivity Check** : Application plante au startup si LLM indisponible
2. **P2 - Maven Maintenance Agent** : Workflow utilise `create_deep_agent()` avec MCP tools
3. **P3 - Agent Configuration** : Chargement YAML + Markdown prompts

**Validation déblocage** :
- CHK020 ✅ : App plante si GOOGLE_API_KEY manquante
- CHK097 ✅ : LangSmith montre traces LLM avec tool calls
- CHK095 ✅ : Logs montrent "agent_loaded" avec config YAML

### Tests Possibles Maintenant (Sans Agents)

**Partiellement testables** (ne valident pas les exigences complètes) :

✅ **CHK001-011**: Configuration & Infrastructure
- CHK001 ✅ : API keys configurées dans .env
- CHK005 ✅ : PostgreSQL sur port 5433
- CHK006 ✅ : Migrations Alembic appliquées
- CHK007 ✅ : API health check fonctionne
- CHK009-011 ✅ : Projets Java compilent

⚠️ **CHK012-015**: Maven list (utilise MCP direct, pas d'agent)
⚠️ **CHK073-080**: Session tracking basique (sans agents)

**Note**: Ces tests partiels ne garantissent PAS que l'application respecte la spec complète.

---

## Configuration & Prerequisites

### LLM Provider Configuration

- [ ] CHK001 - Les clés API LLM sont-elles correctement configurées dans .env ? [Configuration, Spec §FR-008]
- [ ] CHK002 - Le provider par défaut (gemini-2.5-flash) est-il accessible et fonctionnel ? [Configuration]
- [ ] CHK003 - L'absence de clés API provoque-t-elle un échec explicite au démarrage ? [Zéro Complaisance, Constitution §1]
- [ ] CHK004 - Les quotas API disponibles sont-ils suffisants pour les 3 projets de test ? [Prerequisites, research.md]

### Database & Infrastructure

- [ ] CHK005 - PostgreSQL est-il démarré sur le port 5433 ? [Infrastructure]
- [ ] CHK006 - Les migrations Alembic ont-elles été appliquées avec succès ? [Infrastructure]
- [ ] CHK007 - L'API FastAPI répond-elle au health check `/health` ? [Infrastructure]

### Test Projects Availability

- [ ] CHK008 - Les 3 projets Java sont-ils présents dans `test-projects/` ? [Prerequisites]
- [ ] CHK009 - Le projet `java-maven-junit-helloworld` compile-t-il sans erreur ? [Prerequisites]
- [ ] CHK010 - Le projet `spring-petclinic-reactjs` compile-t-il sans erreur ? [Prerequisites]
- [ ] CHK011 - Le projet `spring-petclinic-microservices` compile-t-il sans erreur ? [Prerequisites]

---

## Project 1: java-maven-junit-helloworld (Simple Project)

### Test Scenario 1A: Maven Dependency Analysis

- [ ] CHK012 - La commande `maintenance list` identifie-t-elle les dépendances du projet ? [Spec US1, Acceptance 1]
- [ ] CHK013 - Les dépendances sont-elles classées par criticité (sécurité, majeure, mineure) ? [Spec US1, Acceptance 1]
- [ ] CHK014 - Le temps d'exécution est-il < 30 secondes pour ce projet de 1 classe ? [Spec §SC-003]
- [ ] CHK015 - La sortie JSON est-elle bien formée et parsable ? [API Contract]

### Test Scenario 1B: Maintenance Workflow (Dry-Run)

- [ ] CHK016 - Le workflow de maintenance démarre-t-il en mode dry-run sans erreur ? [Spec US1]
- [ ] CHK017 - Le workflow crée-t-il une session trackée en base de données ? [Spec §FR-042]
- [ ] CHK018 - Les étapes du workflow (analyze_maven, fetch_release_notes) sont-elles tracées ? [Spec §FR-041]
- [ ] CHK019 - Le workflow se termine-t-il gracieusement si aucune mise à jour n'est disponible ? [plan.md Bug Fix #4]
- [ ] CHK020 - L'absence d'agent LLM provoque-t-elle un échec explicite avec message clair ? [Zéro Complaisance]

### Test Scenario 1C: Test Generation

- [ ] CHK021 - La génération de tests identifie-t-elle la classe `HelloWorld` ? [Spec US2, Acceptance 1]
- [ ] CHK022 - Le système classifie-t-il correctement `HelloWorld` (type: Component) ? [Spec §FR-020]
- [ ] CHK023 - Des tests unitaires sont-ils générés pour les méthodes publiques ? [Spec §FR-021]
- [ ] CHK024 - Les tests générés compilent-ils sans erreur après 3 tentatives max ? [Spec §FR-024]
- [ ] CHK025 - Le score de mutation atteint-il >= 80% après génération des killer tests ? [Spec §FR-025, SC-011]

### Test Scenario 1D: Docker Deployment

- [ ] CHK026 - Le système détecte-t-il le type de projet (JAR, Java 8+) ? [Spec US3, Acceptance 1]
- [ ] CHK027 - Un Dockerfile est-il généré et valide (syntaxe Docker correcte) ? [Spec §FR-031]
- [ ] CHK028 - Le build Docker s'exécute-t-il sans erreur en < 5 minutes ? [Spec §SC-002]
- [ ] CHK029 - Le conteneur démarre-t-il et passe-t-il le health check ? [Spec §FR-033]

---

## Project 2: spring-petclinic-reactjs (Medium Project)

### Test Scenario 2A: Maven Dependency Analysis (Spring Boot Context)

- [ ] CHK030 - Le système identifie-t-il les dépendances Spring Boot et React ? [Spec US1]
- [ ] CHK031 - Les dépendances transitives Spring sont-elles analysées via `mvn dependency:tree` ? [Spec §FR-015]
- [ ] CHK032 - Les vulnérabilités CVE sont-elles détectées et reportées ? [Spec §SC-021]
- [ ] CHK033 - Le temps d'analyse est-il < 30 secondes pour ce projet de ~50 classes ? [Spec §SC-003]

### Test Scenario 2B: Maintenance Workflow with Real Updates

- [ ] CHK034 - Le workflow crée-t-il une branche Git dédiée pour les modifications ? [Spec US1, Acceptance 2]
- [ ] CHK035 - Le pom.xml est-il sauvegardé avant modification (backup automatique) ? [Spec §FR-004, §FR-014]
- [ ] CHK036 - Les Release Notes sont-elles analysées par l'agent LLM ? [Spec §FR-012]
- [ ] CHK037 - Les points de vigilance sont-ils identifiés dans le rapport ? [Spec US1, Acceptance 4]
- [ ] CHK038 - Si une mise à jour casse les tests, le rollback est-il effectué automatiquement ? [Spec §FR-013, US1 Acceptance 3]
- [ ] CHK039 - Le workflow respecte-t-il le formatage et commentaires existants du pom.xml ? [Spec §FR-014]

### Test Scenario 2C: Multi-Layer Test Generation

- [ ] CHK040 - Le système classifie-t-il correctement Controllers, Services, Repositories ? [Spec US2, Acceptance 1]
- [ ] CHK041 - Des tests unitaires avec Mockito sont-ils générés pour les Services ? [Spec §FR-021]
- [ ] CHK042 - Des tests d'intégration avec contexte Spring sont-ils générés pour Controllers ? [Spec §FR-022]
- [ ] CHK043 - Des tests d'intégration sont-ils générés pour les Repositories avec @DataJpaTest ? [Spec §FR-022]
- [ ] CHK044 - Des tests Snapshot sont-ils générés pour les réponses API complexes ? [Spec §FR-023]
- [ ] CHK045 - Le taux de compilation des tests générés est-il > 80% ? [Spec §SC-010]
- [ ] CHK046 - Le score de mutation atteint-il >= 80% après correction des tests ? [Spec §SC-011]
- [ ] CHK047 - Chaque test contient-il au moins 2 assertions non-triviales ? [Spec §SC-012]

### Test Scenario 2D: Docker Deployment (Multi-Service)

- [ ] CHK048 - Le système détecte-t-il les services dépendants (PostgreSQL) ? [Spec US3, Acceptance 2]
- [ ] CHK049 - Un docker-compose.yaml est-il généré incluant PostgreSQL ? [Spec §FR-032]
- [ ] CHK050 - Les variables d'environnement sont-elles correctement configurées ? [Spec §FR-032]
- [ ] CHK051 - Le health check Spring Actuator est-il utilisé pour valider le déploiement ? [Spec §FR-033]
- [ ] CHK052 - En cas d'échec, les logs sont-ils collectés et présentés avec contexte ? [Spec US3, Acceptance 4]

---

## Project 3: spring-petclinic-microservices (Large Project)

### Test Scenario 3A: Maven Dependency Analysis (Microservices Context)

- [ ] CHK053 - Le système analyse-t-il les dépendances de multiples modules Maven ? [Spec Limitations, Support Partiel]
- [ ] CHK054 - Les dépendances BOM (Spring Cloud) sont-elles détectées ? [Spec §FR-015, Limitations]
- [ ] CHK055 - Les conflits de versions transitives sont-ils identifiés ? [Spec Edge Case: Dependency Hell]
- [ ] CHK056 - Des suggestions d'exclusions sont-elles proposées pour résoudre les conflits ? [Spec Edge Case]
- [ ] CHK057 - Le temps d'analyse reste-t-il < 1 minute pour ce projet de ~200 classes ? [Spec §SC-003]

### Test Scenario 3B: Maintenance Workflow (Complex Architecture)

- [ ] CHK058 - Le workflow gère-t-il les projets multi-modules Maven ? [Spec Limitations, Support Partiel]
- [ ] CHK059 - Les mises à jour de dépendances respectent-elles les contraintes BOM ? [Spec §FR-015]
- [ ] CHK060 - Le workflow détecte-t-il les services dépendants entre microservices ? [Architecture]
- [ ] CHK061 - Les tests de tous les modules sont-ils exécutés avant validation ? [Spec US1, Acceptance 3]
- [ ] CHK062 - Le rapport final détaille-t-il les modifications par module ? [Spec US1, Acceptance 4]

### Test Scenario 3C: Test Generation (Microservices Patterns)

- [ ] CHK063 - Le système classifie-t-il les classes de microservices (Gateway, Config, Discovery) ? [Spec §FR-020]
- [ ] CHK064 - Des tests d'intégration inter-services sont-ils générés ? [Spec §FR-022]
- [ ] CHK065 - Les tests utilisent-ils @SpringBootTest avec contexte complet ? [Spec §FR-022]
- [ ] CHK066 - Les dépendances externes (Eureka, Config Server) sont-elles mockées ? [Spec Limitations]
- [ ] CHK067 - Le système génère-t-il des tests pour les fallbacks Hystrix/Resilience4j ? [Spec Limitations, Async]

### Test Scenario 3D: Docker Deployment (Orchestration)

- [ ] CHK068 - Un docker-compose.yaml est-il généré avec tous les microservices ? [Spec §FR-032]
- [ ] CHK069 - Les services sont-ils démarrés dans le bon ordre (Config → Discovery → Services) ? [Orchestration]
- [ ] CHK070 - Les health checks sont-ils configurés pour chaque service ? [Spec §FR-033]
- [ ] CHK071 - Le déploiement complet se termine-t-il en < 10 minutes ? [Scalability]
- [ ] CHK072 - En cas d'échec partiel, les logs de tous les services sont-ils collectés ? [Spec US3, Acceptance 4]

---

## Workflow State Management & Observability

### Session Tracking

- [ ] CHK073 - Chaque workflow crée-t-il une Session avec identifiant unique ? [Spec §FR-040]
- [ ] CHK074 - Les sessions sont-elles persistées en base PostgreSQL ? [Spec §FR-042]
- [ ] CHK075 - Le statut de session est-il mis à jour en temps réel ? [Spec US4, Acceptance 1]
- [ ] CHK076 - L'historique des sessions est-il accessible via l'API ? [Spec US4, Acceptance 3]

### Step Execution Tracking

- [ ] CHK077 - Chaque étape de workflow est-elle trackée individuellement ? [Spec §FR-041]
- [ ] CHK078 - Les données d'entrée/sortie de chaque Step sont-elles enregistrées ? [Spec Key Entity: Step]
- [ ] CHK079 - En cas d'erreur, le contexte complet est-il capturé ? [Spec US4, Acceptance 2]
- [ ] CHK080 - Les étapes échouées permettent-elles une reprise de workflow ? [Spec §FR-043]

### Event Logging & Audit Trail

- [ ] CHK081 - Tous les événements sont-ils enregistrés dans un journal immutable ? [Spec §FR-003]
- [ ] CHK082 - Les décisions automatiques des agents LLM sont-elles documentées ? [Spec US4, Acceptance 4]
- [ ] CHK083 - Les logs sont-ils structurés en JSON avec masquage des données sensibles ? [Spec §FR-046, FR-046A]
- [ ] CHK084 - L'intégration LangSmith trace-t-elle les appels LLM ? [Spec §FR-045]

### Pause/Resume Capabilities

- [ ] CHK085 - Un workflow peut-il être mis en pause via l'API ? [Spec US4]
- [ ] CHK086 - Un workflow en pause peut-il être repris depuis la dernière étape ? [Spec §FR-043]
- [ ] CHK087 - Les workflows interrompus (crash) peuvent-ils être repris ? [Spec §FR-043]

---

## Agent Behavior & Error Handling

### LLM Provider Resilience

- [ ] CHK088 - Si Gemini atteint le quota, l'erreur est-elle explicite ? [Spec §FR-009A, Quotas]
- [ ] CHK089 - Le système retry-t-il 3 fois avant d'échouer ? [Spec §FR-009A, Constitution §10]
- [ ] CHK090 - L'échec LLM est-il reporté sans fallback silencieux ? [Zéro Complaisance, Constitution §1]
- [ ] CHK091 - Les logs incluent-ils les détails de l'erreur LLM (rate limit, timeout, etc.) ? [Spec §FR-046]

### MCP Server Behavior

- [ ] CHK092 - Tous les outils sont-ils accessibles uniquement via MCP ? [Constitution §2, Spec §FR-001]
- [ ] CHK093 - Les appels MCP sont-ils tracés et auditables ? [Constitution §2]
- [ ] CHK094 - L'absence d'un MCP server provoque-t-elle un échec explicite ? [Zéro Complaisance]

### Real Agent Execution (Not Mocked)

- [ ] CHK095 - Les agents DeepAgents sont-ils chargés depuis les fichiers YAML ? [Spec §FR-007]
- [ ] CHK096 - Les prompts Markdown sont-ils injectés correctement dans les agents ? [Spec §FR-007]
- [ ] CHK097 - Les agents effectuent-ils de vrais appels LLM (pas de simulation) ? [Constitution §3]
- [ ] CHK098 - Les erreurs LLM (429, 503, timeout) provoquent-elles des échecs explicites ? [Zéro Complaisance]

---

## User Experience & Modes

### Interactive Mode

- [ ] CHK099 - Le mode interactif demande-t-il confirmation avant actions critiques ? [Spec US5, Acceptance 1]
- [ ] CHK100 - Les confirmations sont-elles claires sur les actions à effectuer ? [Spec §FR-040]
- [ ] CHK101 - L'utilisateur peut-il refuser une action et reprendre le workflow ? [Spec US5]

### Autonomous Mode

- [ ] CHK102 - Le mode autonome exécute-t-il sans confirmation utilisateur ? [Spec US5, Acceptance 2]
- [ ] CHK103 - En cas d'erreur bloquante, le workflow s'arrête-t-il avec rapport ? [Spec US5, Acceptance 2]
- [ ] CHK104 - Le rapport d'échec contient-il suffisamment de contexte pour debugging ? [Spec §SC-032]

### Analyze-Only Mode

- [ ] CHK105 - Le mode analyse n'applique-t-il aucune modification au projet ? [Spec US5, Acceptance 3]
- [ ] CHK106 - Le rapport contient-il toutes les analyses sans exécution d'actions ? [Spec US5, Acceptance 3]

---

## Performance & Scalability

### Response Times

- [ ] CHK107 - Les opérations interactives se complètent-elles en < 5 secondes ? [Spec §SC-001]
- [ ] CHK108 - Le déploiement Docker complet se termine-t-il en < 5 minutes ? [Spec §SC-002]
- [ ] CHK109 - L'analyse d'un projet de 200 classes se termine-t-elle en < 30 secondes ? [Spec §SC-003]

### Concurrent Execution

- [ ] CHK110 - Le verrou exclusif par projet empêche-t-il les exécutions concurrentes ? [Spec §FR-047]
- [ ] CHK111 - Un second workflow sur le même projet est-il mis en file d'attente ? [Spec §FR-048]
- [ ] CHK112 - Le verrou est-il libéré automatiquement après timeout (1h) ? [research.md, SESSION_RETENTION]

---

## Data Integrity & Rollback

### Backup & Restore

- [ ] CHK113 - Un backup du pom.xml est-il créé avant modification ? [Spec §FR-004]
- [ ] CHK114 - En cas d'échec, le pom.xml est-il restauré à l'identique ? [Spec §SC-022]
- [ ] CHK115 - Le formatage et les commentaires du pom.xml sont-ils préservés ? [Spec §FR-014]

### Git Integration

- [ ] CHK116 - Une branche dédiée est-elle créée pour les modifications ? [Spec §FR-011]
- [ ] CHK117 - Les commits sont-ils atomiques et descriptifs ? [Constitution §7]
- [ ] CHK118 - Aucune modification n'est faite sur main/master sans autorisation ? [Constitution §7]

---

## Summary

**Total items**: 118
**Categories**: 12 (Configuration, 3 Projects × 4 Scenarios, Workflow, Agents, UX, Performance, Data)
**Focus**: Real end-to-end acceptance tests with live LLM agents

### Execution Strategy

1. **Phase 1 - Configuration Validation** (CHK001-CHK011): Vérifier que l'environnement est prêt
2. **Phase 2 - Simple Project Tests** (CHK012-CHK029): Valider sur java-maven-junit-helloworld
3. **Phase 3 - Medium Project Tests** (CHK030-CHK052): Valider sur spring-petclinic-reactjs
4. **Phase 4 - Complex Project Tests** (CHK053-CHK072): Valider sur spring-petclinic-microservices
5. **Phase 5 - Cross-Cutting Concerns** (CHK073-CHK118): Valider workflow, observability, performance

### Expected Behavior

- ✅ **Successes**: Workflows complètent avec agents LLM fonctionnels
- ❌ **Failures explicites**: Erreurs claires si agents indisponibles (pas de complaisance)
- 📊 **Traceability**: Tous les événements tracés en base de données
- 🔒 **Data Integrity**: Rollback automatique en cas d'échec

### Critical Success Factors

- **Real LLM agents** configured and accessible (no mocks)
- **Database** persistent and healthy
- **Test projects** available and compilable
- **Quotas API** sufficient for all tests

---

**Last Updated**: 2025-11-28
**Status**: Ready for execution
**Prerequisites**: `.env` configured with real LLM API keys
