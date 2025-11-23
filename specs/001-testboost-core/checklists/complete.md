# Requirements Quality Checklist: TestBoost Core (Complete)

**Purpose**: Self-review complet avant soumission PR - Valider la qualité des requirements
**Created**: 2025-11-23
**Depth**: Standard
**Feature**: [spec.md](../spec.md)

---

## Architecture MCP & Agents

### Completeness

- [ ] CHK001 - Les outils MCP requis pour chaque workflow sont-ils tous listés ? [Completeness, Spec §FR-001]
- [ ] CHK002 - Les inputs/outputs de chaque outil MCP sont-ils documentés ? [Gap, mcp-tools.md]
- [ ] CHK003 - Les dépendances entre serveurs MCP sont-elles explicites ? [Completeness]
- [ ] CHK004 - La configuration DeepAgents (YAML + prompts) est-elle spécifiée pour chaque type d'agent ? [Gap]

### Clarity

- [ ] CHK005 - Le format de la variable MODEL est-il clairement défini ? [Clarity, Spec §FR-008]
- [ ] CHK006 - Les timeouts par catégorie d'outil MCP sont-ils quantifiés ? [Clarity]
- [ ] CHK007 - Le comportement de fallback LLM en cas d'erreur est-il spécifié ? [Gap]

### Consistency

- [ ] CHK008 - Les noms d'outils MCP sont-ils cohérents entre spec et plan ? [Consistency]
- [ ] CHK009 - La température LLM (0.2) est-elle justifiée et cohérente pour tous les agents ? [Consistency]

---

## Workflows

### Completeness

- [ ] CHK010 - Toutes les étapes de chaque workflow sont-elles listées avec leurs transitions ? [Completeness, Spec workflows.md]
- [ ] CHK011 - Les conditions de transition entre étapes sont-elles documentées ? [Gap]
- [ ] CHK012 - Les états finaux (completed, failed, cancelled) sont-ils définis pour chaque workflow ? [Completeness]
- [ ] CHK013 - Les critères de rollback sont-ils spécifiés pour chaque étape modifiant des fichiers ? [Gap, Spec §FR-013]

### Clarity

- [ ] CHK014 - Le nombre max de tentatives d'auto-correction (3) s'applique-t-il à tous les workflows ? [Clarity, Spec default]
- [ ] CHK015 - Le timeout de 5 minutes pour les tests Maven est-il configurable ? [Clarity]
- [ ] CHK016 - La stratégie de "baseline tests" avant maintenance est-elle clairement définie ? [Clarity]

### Edge Cases

- [ ] CHK017 - Le comportement est-il défini quand un projet a des tests flaky ? [Edge Case, Gap]
- [ ] CHK018 - La gestion des dépendances circulaires est-elle adressée ? [Edge Case, Gap]
- [ ] CHK019 - Le comportement lors d'un timeout LLM en cours de génération est-il spécifié ? [Edge Case, Gap]

---

## API & Interfaces

### Completeness

- [ ] CHK020 - Tous les endpoints REST sont-ils documentés avec leurs paramètres ? [Completeness, contracts/openapi.yaml]
- [ ] CHK021 - Les codes d'erreur HTTP sont-ils listés pour chaque endpoint ? [Completeness]
- [ ] CHK022 - Les commandes CLI sont-elles toutes documentées avec leurs options ? [Completeness, Spec §FR-051]
- [ ] CHK023 - Les exit codes CLI sont-ils définis et documentés ? [Gap]

### Clarity

- [ ] CHK024 - Le format de l'API Key (X-API-Key) est-il spécifié ? [Clarity, Spec §FR-052]
- [ ] CHK025 - Les formats de réponse JSON sont-ils définis (Pydantic schemas) ? [Clarity]
- [ ] CHK026 - La pagination des listes (sessions, artifacts) est-elle documentée ? [Clarity]

### Consistency

- [ ] CHK027 - Les noms de champs sont-ils cohérents entre API et CLI ? [Consistency]
- [ ] CHK028 - Les types de session sont-ils identiques dans API et CLI ? [Consistency]

---

## Data Model

### Completeness

- [ ] CHK029 - Toutes les entités du spec sont-elles présentes dans data-model.md ? [Completeness]
- [ ] CHK030 - Les relations entre entités (FK) sont-elles toutes documentées ? [Completeness]
- [ ] CHK031 - Les index de performance sont-ils définis pour les requêtes fréquentes ? [Gap]

### Clarity

- [ ] CHK032 - Les contraintes d'unicité sont-elles explicites pour chaque entité ? [Clarity, data-model.md]
- [ ] CHK033 - Les règles de validation (NOT NULL, CHECK) sont-elles documentées ? [Clarity]
- [ ] CHK034 - La politique de cascade (ON DELETE) est-elle spécifiée pour les FK ? [Gap]

### Lifecycle

- [ ] CHK035 - Les transitions d'état (Session, Step) sont-elles complètes et sans ambiguïté ? [Completeness]
- [ ] CHK036 - Les conditions de purge (1 an) sont-elles définies avec précision ? [Clarity, Spec §FR-044]

---

## Non-Functional Requirements

### Performance

- [ ] CHK037 - Les objectifs de performance sont-ils quantifiés pour toutes les opérations critiques ? [Measurability, Spec §SC-001/002/003]
- [ ] CHK038 - Les seuils de dégradation acceptable sont-ils définis ? [Gap]
- [ ] CHK039 - La performance sous charge (sessions concurrentes) est-elle spécifiée ? [Gap]

### Observability

- [ ] CHK040 - Les événements à tracer dans LangSmith sont-ils listés ? [Completeness]
- [ ] CHK041 - Le format des logs JSON est-il spécifié (champs requis) ? [Clarity, Spec §FR-046]
- [ ] CHK042 - Les métriques clés à exposer sont-elles définies ? [Gap]

### Security

- [ ] CHK043 - La rotation des API Keys est-elle adressée ? [Gap]
- [ ] CHK044 - Le stockage sécurisé des credentials LLM est-il spécifié ? [Gap]
- [ ] CHK045 - Les données sensibles dans les logs sont-elles masquées ? [Gap]

### Reliability

- [ ] CHK046 - La stratégie de retry avec backoff est-elle quantifiée ? [Clarity, Constitution §10]
- [ ] CHK047 - Les timeouts par type d'opération externe sont-ils définis ? [Clarity]
- [ ] CHK048 - Le comportement en cas de perte de connexion DB est-il spécifié ? [Edge Case, Gap]

---

## Isolation & Environment

### Completeness

- [ ] CHK049 - Les prérequis pour l'environnement TestBoost sont-ils complets ? [Completeness, Spec Prérequis]
- [ ] CHK050 - Les versions minimales (Python, Docker, etc.) sont-elles spécifiées ? [Clarity]
- [ ] CHK051 - La configuration Poetry/virtualenv est-elle documentée ? [Completeness, Spec §FR-010B]

### Clarity

- [ ] CHK052 - L'isolation Docker des projets Maven est-elle clairement décrite ? [Clarity, Spec §FR-010A]
- [ ] CHK053 - Le cycle de vie des containers Docker (création/destruction) est-il spécifié ? [Gap]
- [ ] CHK054 - Le partage de volumes entre host et container est-il documenté ? [Gap]

---

## Test Generation

### Completeness

- [ ] CHK055 - Les types de tests à générer (unit, integration, snapshot, e2e, mutation) sont-ils tous documentés ? [Completeness]
- [ ] CHK056 - Les critères de classification des classes sont-ils exhaustifs ? [Completeness, Spec §FR-020]
- [ ] CHK057 - Le scoring de qualité des tests (0-120) est-il complètement défini ? [Completeness]

### Clarity

- [ ] CHK058 - Le seuil de mutation testing (80%) est-il justifié ? [Clarity, Spec §FR-025]
- [ ] CHK059 - Les critères pour générer des "killer tests" sont-ils clairs ? [Clarity, Spec §FR-026]
- [ ] CHK060 - Le pattern ApprovalTests pour snapshots est-il documenté ? [Clarity]

### Edge Cases

- [ ] CHK061 - Le comportement pour les classes trop complexes (>20 cyclomatic) est-il défini ? [Edge Case, Spec Limitations]
- [ ] CHK062 - La gestion des dépendances externes mockées est-elle spécifiée ? [Edge Case]

---

## Constitution Alignment

### Traceability

- [ ] CHK063 - Chaque FR est-il traçable à au moins un principe de la constitution ? [Traceability]
- [ ] CHK064 - Les violations potentielles sont-elles documentées avec justification ? [Gap]

### Compliance

- [ ] CHK065 - Le principe "Zéro Complaisance" est-il reflété dans les requirements d'erreur ? [Consistency, Constitution §1]
- [ ] CHK066 - Le principe "Outils via MCP" est-il respecté sans exception ? [Consistency, Constitution §2]
- [ ] CHK067 - Le principe "Pas de Mocks Production" est-il clairement appliqué ? [Consistency, Constitution §3]

---

## Dependencies & Assumptions

### Documentation

- [ ] CHK068 - Les dépendances externes (Gemini API, LangSmith, OSV) sont-elles listées ? [Completeness]
- [ ] CHK069 - Les modes de défaillance des dépendances externes sont-ils adressés ? [Gap]
- [ ] CHK070 - Les hypothèses sur la disponibilité des services sont-elles explicites ? [Assumption]

### Validation

- [ ] CHK071 - La compatibilité des versions de dépendances (poetry.lock) est-elle validée ? [Assumption]
- [ ] CHK072 - Les limites de quotas API (LLM providers) sont-elles documentées ? [Gap]

---

## Acceptance Criteria Quality

### Measurability

- [ ] CHK073 - Tous les Success Criteria sont-ils objectivement mesurables ? [Measurability, Spec §SC-*]
- [ ] CHK074 - Les seuils de succès/échec sont-ils quantifiés ? [Clarity]
- [ ] CHK075 - Les critères d'acceptation des User Stories sont-ils testables ? [Measurability]

### Coverage

- [ ] CHK076 - Chaque FR a-t-il au moins un critère d'acceptation associé ? [Coverage]
- [ ] CHK077 - Les scénarios "Given/When/Then" couvrent-ils les cas nominaux ET d'erreur ? [Coverage]

---

## Summary

**Total items**: 77
**Categories**: 10
**Focus**: Complete coverage (Architecture, Workflows, API, Data, NFRs, Constitution)

### Legend

- `[Completeness]` - Requirement présent mais incomplet
- `[Clarity]` - Requirement ambigu ou non quantifié
- `[Consistency]` - Incohérence entre sections
- `[Measurability]` - Critère non testable objectivement
- `[Coverage]` - Scénario/cas manquant
- `[Gap]` - Requirement manquant
- `[Edge Case]` - Cas limite non adressé
- `[Assumption]` - Hypothèse non validée
- `[Traceability]` - Lien manquant avec source

### Next Steps

1. Parcourir chaque item et cocher si le requirement est satisfaisant
2. Pour les items non cochés, créer des issues ou clarifications
3. Re-valider après corrections
