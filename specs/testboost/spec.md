# TestBoost - Spécification Fonctionnelle

## Vue d'ensemble

**TestBoost** automatise la maintenance des applications Java/Spring Boot.

### Problème

Les équipes de développement passent 30-40% de leur temps sur des tâches de maintenance :
- Mettre à jour les dépendances
- Écrire et corriger des tests
- Configurer et valider des déploiements
- Gérer les branches Git
- Test complet pour s'assurer des non-régressions

### Solution

Un système qui exécute ces tâches automatiquement tout en :
- Laissant le contrôle à l'utilisateur (modes interactif/autonome)
- Assurant une traçabilité complète
- Validant chaque modification par des tests
- Donnant une bonne confiance sur la couverture des tests techniques et fonctionnelles

### Utilisateurs

- **Développeurs** : automatiser les tâches quotidiennes
- **Tech Leads** : superviser les opérations de maintenance
- **DevOps** : intégrer dans les pipelines CI/CD
- **TestManager** : assurer la qualité de l'application

---

## Fonctionnalités

### 1. Maintenance des dépendances Maven

Analyser et mettre à jour automatiquement les dépendances d'un projet. Donner à l'utilisateur une vue des points oû porter une vigileance particulière pour les risques de regression.

**L'utilisateur peut :**
- Voir les dépendances obsolètes classées par criticité (sécurité, majeure, mineure)
- Choisir les mises à jour à appliquer
- Laisser le système valider par les tests avant de committer

**Le système doit :**
- Créer une branche dédiée pour les modifications
- Sauvegarder le pom.xml avant modification
- Générer un commit avec le détail des modifications
- Donner un rapport sur les composants techniques modifiés qui pourraient changer le comportement de l'application

**Critères de succès :**
- Analyse complète de la release note entre 2 versions de dépendances
- Workflow complet (analyse → commit)

---

### 2. Stratégie de Tests (Non-Régression)

Une maintenance est réussie si l'application se comporte *exactement* comme avant, et les tests automatisés en sont la preuve irréfutable.
La stratégie est centrée sur la **préservation du comportement actuel** (Non-Régression).
Cette stratégie déploie un filet de sécurité complet à travers plusieurs couches de tests pour garantir l'iso-fonctionnalité.

#### 2.1. Tests Unitaires Ciblés
**Objectif :** Figer la logique métier pure dans les zones sensibles.
*   **Périmètre :** Calculs, transformations, règles métier réutilisées, manipulation de dates, formats, sérialisation.
*   **Approche :** Isolation des composants (mocking).

#### 2.2. Tests d’Intégration
**Objectif :** Vérifier le comportement réel de l’application avec ses couches internes.
*   **Exemples de flux :**
    *   Service → Repository → Base de données
    *   API → Service → Base de données
    *   Batch → DB
*   **Couverture :** Transactions, validations, sérialisation JSON/XML, gestion des erreurs.

#### 2.3. Tests de Contrat / API
**Objectif :** Garantir que les interfaces exposées ne changent pas.
*   **Vérifications :** URLs, méthodes HTTP, codes de statut, structure JSON, types de champs, valeurs attendues.
*   **Cas :** Succès nominaux, cas d'erreurs, edge cases.

#### 2.4. Tests End-to-End (E2E)
**Objectif :** Valider les scénarios critiques de bout en bout.
*   **Exemples :**
    *   Création d’un utilisateur → données persistées
    *   Création d’une commande → calcul → base → statut de réponse
    *   Login → autorisation → ressource protégée

#### 2.5. Tests Snapshot / Approval
**Objectif :** Figer l’existant en capturant “ce que l’application renvoie aujourd’hui” (fortement recommandé en migration).
*   **Cas d'usage :** Réponses API complexes (gros JSON, HTML), réponses mail, exports (CSV, XML), génération de rapports.
*   **Mécanisme :**
    1.  Une première exécution produit un fichier de référence.
    2.  Chaque exécution suivante compare le résultat avec ce fichier.
    3.  Toute différence est signalée comme une régression potentielle.

#### 2.6. Tests de Performance (Baseline)
**Objectif :** Éviter une dégradation importante (tests légers mais nécessaires).
*   **Périmètre :** Temps de réponse des endpoints critiques, temps de traitement batch.
*   **Méthode :** Comparaison avant / après avec un volume de données raisonnable.
*   **Seuil :** Tolérance définie (ex: +10% max) selon le contexte.

---

### 3. Approche Projet (Avant / Pendant / Après)

#### 3.1. Avant la maintenance
**Objectif :** Stabiliser l’état actuel.

*   Écrire / compléter les tests unitaires sensibles
*   Écrire les tests d’intégration sur les flux critiques
*   Écrire les tests E2E essentiels
*   Générer les snapshots de référence
*   **Validation :** Vérifier que la suite complète est verte.

#### 3.2. Pendant la maintenance
**Objectif :** Monter de version / changer la lib / modifier l’infra.

*   Relancer l’intégralité des tests à chaque étape
*   Examiner les diffs de snapshots
*   **Identifier si les changements sont :**
    *   Voulus (alors on met à jour la référence)
    *   Ou des régressions (à corriger)

#### 3.3. Après la maintenance
**Objectif :** Valider la livraison.

*   S’assurer que tous les tests passent
*   S’assurer d’une non-régression sur les performances
*   S’assurer qu'aucun comportement fonctionnel n’a changé
*   Marquer et livrer la version comme “stabilisée”

---

### 4. Déploiement Docker

Générer la configuration Docker et déployer l'application.

**L'utilisateur peut :**
- Indiquer le projet à déployer
- Voir le statut du déploiement en temps réel
- Consulter les logs en cas d'échec

**Le système doit :**
- Détecter le type de projet (JAR, WAR, JSP)
- Générer Dockerfile et docker-compose adaptés
- Inclure les services dépendants (base de données, cache)
- Vérifier la santé de l'application après démarrage

**Critères de succès :**
- Déploiement complet en moins de 5 minutes
- Health check réussi avant de déclarer le succès
- Logs collectés et accessibles en cas d'échec

---

### 5. Suivi des workflows

Suivre l'exécution des opérations en temps réel.

**L'utilisateur peut :**
- Voir la progression de chaque étape
- Consulter les logs détaillés
- Accéder à l'historique des sessions
- Filtrer par statut et date

**Le système doit :**
- Enregistrer chaque événement (début, fin, erreur)
- Fournir une vue graphique du workflow
- Permettre l'analyse post-mortem

**Critères de succès :**
- Mise à jour en temps réel
- Historique complet accessible
- Erreurs affichées avec contexte suffisant

---

## Modes d'exécution

Le système supporte plusieurs modes selon le besoin :

| Mode | Description | Cas d'usage |
|------|-------------|-------------|
| **Interactif** | Demande confirmation à chaque étape critique | Utilisation manuelle |
| **Autonome** | Exécute sans intervention | CI/CD, cron jobs |
| **Analyse seule** | Génère un rapport sans modifier | Audit, évaluation |
| **Debug** | Pause à chaque étape avec logs détaillés | Diagnostic |

---

## Entités métier

### Session

Une exécution de workflow du début à la fin.

- Identifiant unique
- Projet cible
- Type de workflow
- Statut (en cours, terminé, échoué)
- Dates de début et fin
- Résultats

### Étape

Une unité de travail atomique dans un workflow.

- Position dans le workflow
- Statut (en attente, en cours, réussi, échoué)
- Données d'entrée et de sortie
- Erreur éventuelle

### Projet

Le projet Java analysé et modifié.

- Chemin racine
- Type (JAR, WAR)
- Dépendances
- Classes (avec leur type)
- Tests existants

### Dépendance

Une dépendance Maven.

- Identifiant (groupId, artifactId)
- Version actuelle
- Version disponible
- Type de mise à jour (sécurité, majeure, mineure)
- Vulnérabilités connues

### Modification

Un changement appliqué à un fichier.

- Fichier concerné
- Valeur avant et après
- Validée par les tests

---

## Prérequis

### Environnement d'exécution

- Java 8 ou supérieur
- Maven (wrapper ou système)
- Git
- Docker (pour le déploiement)
- Connexion internet

### Projet cible

- Projet Maven (pom.xml présent)
- Code Java dans src/main/java
- Structure Maven standard
- Le projet doit compiler avant intervention

---

## Comportements par défaut

Ces valeurs s'appliquent si non spécifiées :

- Mode **interactif**
- Branche de maintenance créée automatiquement
- Backup du pom.xml avant modification
- 3 tentatives de correction pour les tests
- Timeout de 5 minutes pour les tests Maven
- Objectif de mutation à 80%

---

## Limitations

### Non supporté

- Projets Gradle ou Ant
- Code Kotlin
- Projets multi-modules (support partiel)
- Déploiement cloud (AWS, GCP, Azure)
- Plugins IDE

### Support partiel

- Dépendances BOM
- Tests avec Spring Security (configuration manuelle)

---

## Hors périmètre

Ces éléments ne font pas partie de cette spécification :

- Support d'autres langages que Java
- Refactoring automatique du code
- Génération de documentation
- Analyse de performance
- Gestion des secrets
