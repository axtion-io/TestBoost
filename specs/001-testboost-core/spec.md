# Feature Specification: TestBoost Core

**Feature Branch**: `001-testboost-core`
**Created**: 2025-11-23
**Status**: Draft
**Input**: Système d'automatisation de maintenance Java/Spring Boot avec génération de tests multi-couches, maintenance Maven, et déploiement Docker

## Vue d'ensemble

**TestBoost** automatise la maintenance des applications Java/Spring Boot en garantissant une **iso-fonctionnalité totale** (Non-Régression).

### Problème

Les équipes de développement passent 30-40% de leur temps sur des tâches de maintenance :
- Mettre à jour les dépendances
- Écrire et corriger des tests
- Configurer et valider des déploiements
- Gérer les branches Git
- Tests complets pour s'assurer des non-régressions

### Solution

Un système qui exécute ces tâches automatiquement via des agents MCP tout en :
- Laissant le contrôle à l'utilisateur (modes interactif/autonome)
- Assurant une traçabilité complète
- Validant chaque modification par des tests
- Donnant une bonne confiance sur la couverture des tests techniques et fonctionnels

### Utilisateurs cibles

- **Développeurs** : automatiser les tâches quotidiennes
- **Tech Leads** : superviser les opérations de maintenance
- **DevOps** : intégrer dans les pipelines CI/CD
- **Test Managers** : assurer la qualité de l'application

---

## Clarifications

### Session 2025-11-23

- Q: Stratégie d'orchestration des agents MCP → A: LangGraph avec DeepAgents pour la configuration des agents
- Q: Fournisseur LLM pour les agents → A: Multi-provider configurable (défaut: gemini-2.5-flash-preview-09-2025, support: Claude 4.5 Sonnet, Gemini 3 Pro, GPT-4o)
- Q: Rétention des données de session → A: 1 an
- Q: Stratégie d'observabilité → A: LangSmith pour agents + logs structurés JSON pour application
- Q: Gestion de la concurrence → A: Verrou exclusif par projet (file d'attente)
- Q: Isolation des environnements → A: Poetry/virtualenv pour TestBoost + Container Docker pour projets Maven cibles

---

## User Scenarios & Testing

### User Story 1 - Maintenance Maven avec Non-Régression (Priority: P1)

En tant que développeur, je veux mettre à jour les dépendances de mon projet Maven automatiquement tout en garantissant qu'aucune régression n'est introduite.

**Why this priority**: La maintenance des dépendances est la tâche la plus fréquente et la plus risquée. Une mise à jour qui casse l'application peut coûter des jours de debugging.

**Independent Test**: Peut être testé en exécutant le workflow sur un projet Maven avec des dépendances obsolètes et en vérifiant que tous les tests passent après mise à jour.

**Acceptance Scenarios**:

1. **Given** un projet Maven avec des dépendances obsolètes, **When** je lance le workflow de maintenance, **Then** je vois la liste des mises à jour disponibles classées par criticité (sécurité, majeure, mineure)
2. **Given** des mises à jour identifiées, **When** le système les applique, **Then** il crée une branche dédiée et sauvegarde le pom.xml avant modification
3. **Given** une mise à jour appliquée, **When** les tests échouent, **Then** le système effectue un rollback automatique de cette mise à jour
4. **Given** toutes les mises à jour validées, **When** le workflow termine, **Then** un rapport détaille les modifications avec les points de vigilance (Release Notes analysées)

---

### User Story 2 - Génération de Tests Multi-Couches (Priority: P1)

En tant que développeur, je veux générer automatiquement une suite de tests complète couvrant toutes les couches de mon application pour garantir la non-régression.

**Why this priority**: Les tests sont la preuve irréfutable que l'application fonctionne correctement. Sans eux, aucune maintenance n'est sécurisée.

**Independent Test**: Peut être testé en générant des tests pour un projet existant et en vérifiant le taux de compilation et le score de mutation.

**Acceptance Scenarios**:

1. **Given** un projet Java/Spring Boot, **When** je lance la génération de tests, **Then** le système analyse la structure et classifie les classes (Controller, Service, Repository, etc.)
2. **Given** des classes classifiées, **When** les tests sont générés, **Then** ils respectent les conventions existantes du projet (naming, assertions, mocking)
3. **Given** des tests générés avec erreurs de compilation, **When** le système détecte les erreurs, **Then** il tente une auto-correction (max 3 tentatives)
4. **Given** des tests qui passent, **When** le mutation testing s'exécute, **Then** le score doit atteindre au moins 80%
5. **Given** un score de mutation < 80%, **When** des mutants survivent, **Then** le système génère des "killer tests" ciblés

---

### User Story 3 - Déploiement Docker Automatisé (Priority: P2)

En tant que développeur, je veux déployer mon application dans Docker automatiquement pour valider son fonctionnement en environnement conteneurisé.

**Why this priority**: Le déploiement Docker est nécessaire pour les tests E2E et valide l'intégration complète de l'application.

**Independent Test**: Peut être testé en déployant un projet et en vérifiant le health check.

**Acceptance Scenarios**:

1. **Given** un projet Maven packagé, **When** je lance le déploiement Docker, **Then** le système détecte le type de projet (JAR, WAR, JSP) et génère un Dockerfile adapté
2. **Given** un Dockerfile généré, **When** le système déploie, **Then** il inclut les services dépendants (PostgreSQL, etc.) via docker-compose
3. **Given** les conteneurs démarrés, **When** le système vérifie la santé, **Then** il attend le health check OK avant de déclarer le succès
4. **Given** un échec de déploiement, **When** les logs sont disponibles, **Then** ils sont collectés et présentés avec le contexte de l'erreur

---

### User Story 4 - Suivi des Workflows en Temps Réel (Priority: P2)

En tant que tech lead, je veux suivre l'exécution des workflows en temps réel pour comprendre ce qui se passe et intervenir si nécessaire.

**Why this priority**: La visibilité sur les opérations est essentielle pour la confiance et le debugging.

**Independent Test**: Peut être testé en lançant un workflow et en vérifiant la mise à jour en temps réel de la progression.

**Acceptance Scenarios**:

1. **Given** un workflow en cours, **When** je consulte le tableau de bord, **Then** je vois la progression de chaque étape en temps réel
2. **Given** une étape échouée, **When** je consulte les détails, **Then** je vois les logs et le contexte de l'erreur
3. **Given** des workflows passés, **When** j'accède à l'historique, **Then** je peux filtrer par statut, date et type
4. **Given** un workflow avec décisions automatiques, **When** je consulte l'audit trail, **Then** je comprends pourquoi le système a agi ainsi

---

### User Story 5 - Mode Interactif vs Autonome (Priority: P3)

En tant qu'utilisateur, je veux choisir entre un mode interactif (avec confirmations) et un mode autonome (pour CI/CD) selon mon contexte.

**Why this priority**: La flexibilité d'exécution permet l'utilisation en développement local et en pipelines automatisés.

**Independent Test**: Peut être testé en exécutant le même workflow dans les deux modes et en vérifiant le comportement.

**Acceptance Scenarios**:

1. **Given** le mode interactif, **When** une action critique est requise, **Then** le système demande confirmation avant de procéder
2. **Given** le mode autonome, **When** une erreur bloquante survient, **Then** le système arrête le workflow et génère un rapport d'échec
3. **Given** le mode analyse seule, **When** le workflow termine, **Then** aucune modification n'est appliquée au projet

---

### Edge Cases

- **Projet instable** : Si le projet ne compile pas avant la maintenance, la maintenance est refusée jusqu'à correction
- **Dependency Hell** : Les conflits de versions transitives sont détectés via `mvn dependency:tree` avec suggestions d'exclusions
- **Service externe indisponible** : Erreur explicite, pas de fallback silencieux (Principe Zéro Complaisance)
- **Spring Security** : Support partiel, configuration manuelle peut être nécessaire
- **Docker non démarré** : Erreur explicite avec instructions de résolution
- **Port occupé** : Identification du processus conflictuel et proposition de port alternatif

---

## Requirements

### Functional Requirements

#### Architecture et Principes

- **FR-001**: Le système DOIT exposer tous les outils via des serveurs MCP (Model Context Protocol)
- **FR-002**: Les agents NE DOIVENT JAMAIS appeler directement des commandes système
- **FR-003**: Le système DOIT enregistrer chaque action, décision et résultat dans un journal immutable
- **FR-004**: Le système DOIT créer un backup automatique avant toute modification
- **FR-005**: Le système DOIT respecter les conventions existantes du projet cible (nommage, structure)
- **FR-006**: Le système DOIT orchestrer les workflows via LangGraph avec état partagé
- **FR-007**: Les agents DOIVENT être configurés via DeepAgents (fichiers YAML + prompts Markdown)
- **FR-008**: Le système DOIT supporter plusieurs fournisseurs LLM (Gemini, Claude, GPT-4o) via variable MODEL
- **FR-009**: Le modèle par défaut DOIT être `google-genai/gemini-2.5-flash-preview-09-2025`
- **FR-009A**: En cas d'erreur LLM, le système DOIT retry 3x puis échouer explicitement (pas de fallback automatique vers autre provider)
- **FR-010A**: Le système DOIT exécuter les builds/tests Maven dans des containers Docker isolés
- **FR-010B**: TestBoost DOIT s'exécuter dans un environnement virtuel Python (Poetry/virtualenv)

#### Maintenance Maven

- **FR-010**: Le système DOIT analyser les dépendances obsolètes et les classer par criticité (sécurité, majeure, mineure)
- **FR-011**: Le système DOIT créer une branche dédiée pour les modifications
- **FR-012**: Le système DOIT analyser les Release Notes entre versions pour identifier les points de vigilance
- **FR-013**: Le système DOIT effectuer un rollback si une mise à jour casse les tests
- **FR-014**: Le système DOIT respecter le formatage et les commentaires existants du pom.xml
- **FR-015**: Le système DOIT gérer les propriétés centralisées et les BOM

#### Génération de Tests

- **FR-020**: Le système DOIT classifier automatiquement les classes (Controller, Service, Repository, Component, DTO)
- **FR-021**: Le système DOIT générer des tests unitaires pour les Services et Components avec isolation Mockito
- **FR-022**: Le système DOIT générer des tests d'intégration pour les Controllers et Repositories avec contexte Spring
- **FR-023**: Le système DOIT générer des tests Snapshot pour les réponses API complexes
- **FR-024**: Le système DOIT tenter l'auto-correction des tests en erreur (max 3 tentatives)
- **FR-025**: Le système DOIT exécuter le mutation testing et atteindre un score cible de 80%
- **FR-026**: Le système DOIT générer des "killer tests" si des mutants survivent

#### Déploiement Docker

- **FR-030**: Le système DOIT détecter le type de projet (JAR, WAR, JSP) et la version Java
- **FR-031**: Le système DOIT générer un Dockerfile optimisé selon le type de projet
- **FR-032**: Le système DOIT générer un docker-compose incluant les services dépendants
- **FR-033**: Le système DOIT vérifier la santé de l'application via health check avant de déclarer le succès
- **FR-034**: Le système DOIT collecter et exposer les logs en cas d'échec

#### Workflows et Suivi

- **FR-040**: Le système DOIT supporter les modes : Interactif, Autonome, Analyse seule, Debug
- **FR-041**: Le système DOIT mettre à jour la progression en temps réel
- **FR-042**: Le système DOIT conserver l'historique complet des sessions pendant 1 an
- **FR-043**: Le système DOIT permettre la reprise d'un workflow interrompu
- **FR-044**: Le système DOIT purger automatiquement les sessions de plus de 1 an
- **FR-045**: Le système DOIT intégrer LangSmith pour le tracing des agents et workflows LLM
- **FR-046**: Le système DOIT produire des logs structurés JSON pour l'application (API, MCP servers)
- **FR-046A**: Le système DOIT masquer automatiquement les données sensibles dans les logs (clés API, tokens, credentials)
- **FR-047**: Le système DOIT implémenter un verrou exclusif par projet pour éviter les conflits
- **FR-048**: Le système DOIT mettre en file d'attente les workflows sur un projet déjà verrouillé

#### Interfaces

- **FR-050**: Le système DOIT exposer une API REST (FastAPI sur port 8000)
- **FR-051**: Le système DOIT fournir une CLI pour l'exécution des workflows
- **FR-052**: Le système DOIT authentifier les requêtes API via X-API-Key

### Key Entities

- **Session** : Une exécution de workflow du début à la fin
  - Identifiant unique, projet cible, type de workflow, statut, dates, résultats

- **Étape** : Une unité de travail atomique dans un workflow
  - Position, statut, données d'entrée/sortie, erreur éventuelle

- **Projet** : Le projet Java analysé et modifié
  - Chemin racine, type (JAR/WAR), dépendances, classes, tests existants

- **Dépendance** : Une dépendance Maven
  - Identifiant (groupId, artifactId), versions actuelle/disponible, type de mise à jour, CVE

- **Modification** : Un changement appliqué à un fichier
  - Fichier concerné, valeur avant/après, validée par les tests

---

## Success Criteria

### Measurable Outcomes

#### Performance

- **SC-001**: Les opérations interactives se complètent en moins de 5 secondes
- **SC-002**: Le déploiement Docker complet se termine en moins de 5 minutes
- **SC-003**: L'analyse d'un projet de 200 classes se termine en moins de 30 secondes

#### Qualité des Tests

- **SC-010**: Le taux de compilation des tests générés est supérieur à 80%
- **SC-011**: Le score de mutation atteint au moins 80%
- **SC-012**: Chaque test contient au moins 2 assertions non-triviales

#### Fiabilité Maintenance

- **SC-020**: 100% des tests passent après une maintenance réussie
- **SC-021**: Le système détecte et reporte toutes les vulnérabilités (CVE) connues
- **SC-022**: Aucune perte de données en cas d'erreur (rollback complet)

#### Traçabilité

- **SC-030**: Chaque décision automatique est documentée avec sa justification
- **SC-031**: L'historique complet est accessible pour analyse post-mortem
- **SC-032**: Les erreurs sont affichées avec un contexte suffisant pour le debugging

#### Utilisabilité

- **SC-040**: Un développeur peut lancer une maintenance complète en moins de 3 commandes
- **SC-041**: Les rapports générés sont compréhensibles sans documentation supplémentaire
- **SC-042**: Le système s'intègre dans un pipeline CI/CD sans configuration spéciale

---

## Prérequis

### Environnement d'exécution TestBoost

- Python 3.10+ (requis par LangGraph 1.0)
- Poetry (gestion des dépendances avec virtualenv)
- Docker & Docker Compose
- Git
- Connexion internet

### Environnement projet cible

- Java 8 ou supérieur (dans le container Docker)
- Maven (wrapper ou système)
- Les builds/tests Maven s'exécutent dans des containers Docker isolés

### Projet cible

- Projet Maven (pom.xml présent)
- Code Java dans src/main/java
- Structure Maven standard
- Le projet doit compiler avant intervention

---

## Limitations

### Non supporté

- Projets Gradle ou Ant
- Code Kotlin
- Projets multi-modules (support partiel)
- Déploiement cloud (AWS, GCP, Azure)
- Tests d'interface graphique (Selenium/Cypress)

### Support partiel

- Dépendances BOM
- Tests avec Spring Security (configuration manuelle)
- Asynchronisme complexe (`@Async`, `CompletableFuture`)

---

## Comportements par défaut

- Mode **interactif** par défaut
- Branche de maintenance créée automatiquement
- Backup du pom.xml avant modification
- 3 tentatives de correction pour les tests
- Timeout de 5 minutes pour les tests Maven
- Objectif de mutation à 80%

---

## Quotas et Limites LLM

Les utilisateurs doivent être conscients des limites de quotas des providers LLM :

| Provider | Quota Free Tier | Limite Tokens/min | Notes |
|----------|-----------------|-------------------|-------|
| Gemini | 1500 req/jour | 32k tokens | Défaut recommandé |
| Claude | Selon plan | Variable | Nécessite compte Anthropic |
| GPT-4o | Selon plan | Variable | Nécessite compte OpenAI |

**Important** :
- Le système NE gère PAS les quotas automatiquement
- En cas de quota dépassé → erreur explicite avec message clair
- L'utilisateur est responsable de surveiller sa consommation
- Recommandation : utiliser le provider avec le quota le plus adapté à la taille du projet
