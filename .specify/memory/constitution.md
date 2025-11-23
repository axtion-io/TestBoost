# Constitution - TestBoost

## Principes Non-Négociables

Ce document établit les principes fondamentaux qui guident toutes les décisions de conception et d'implémentation de TestBoost. Ces principes ne sont pas négociables et doivent être respectés dans toutes les fonctionnalités.

---

## 1. Zéro Complaisance

**Principe**: "Mieux vaut aucun log que des logs mensongers"

- JAMAIS de résultats OK de complaisance
- JAMAIS de logs synthétiques mensongers
- JAMAIS de faux positifs pour rassurer
- Si une fonctionnalité ne fonctionne pas → le dire clairement
- Si des logs sont vides → afficher "Aucun log disponible" (pas d'invention)
- Si une opération échoue → reporter l'échec exact, pas un succès partiel
- Pas de simulation de résultats pour "faire joli"

---

## 2. Outils via MCP Exclusivement

**Principe**: Toute utilisation d'outil par un agent doit passer par un serveur MCP.

- Les agents n'appellent JAMAIS directement des commandes système
- Chaque outil est exposé via un serveur MCP dédié
- Les appels d'outils sont tracés et auditables
- Pas de contournement du protocole MCP
- Permet le remplacement et le test des outils

---

## 3. Pas de Mocks en Production Utilisateur

**Principe**: Lors des tests par l'utilisateur, aucun mock ou code stub pour ne pas tromper.

- L'utilisateur teste toujours le système réel
- Pas de données factices présentées comme réelles
- Pas de services simulés masqués
- Si un service externe est indisponible → erreur explicite (pas de fallback silencieux)
- Les mocks sont réservés aux tests automatisés du développement, jamais à l'utilisateur

---

## 4. Automatisation avec Contrôle Utilisateur

**Principe**: Le système automatise les tâches répétitives tout en laissant le contrôle final à l'utilisateur.

- L'utilisateur peut toujours choisir entre mode autonome et mode interactif
- Toute modification irréversible requiert une confirmation (sauf en mode autonome explicite)
- Les décisions critiques sont toujours documentées et traçables
- Possibilité de rollback sur toutes les opérations destructives

---

## 5. Traçabilité Complète

**Principe**: Chaque action, décision et résultat est enregistré et auditable.

- Journal immutable de tous les événements
- Historique complet des modifications de fichiers
- Traçabilité des décisions automatiques et manuelles
- Audit trail accessible pour analyse post-mortem

---

## 6. Validation Avant Modification

**Principe**: Le système valide les prérequis avant toute modification.

- Vérification de l'état du projet avant intervention
- Détection des conflits potentiels
- Backup automatique avant modifications
- Tests de validation après modifications

---

## 7. Isolation et Sécurité

**Principe**: Les modifications sont isolées et réversibles.

- Modifications sur branche dédiée (jamais sur main/master sans autorisation)
- Commits atomiques et descriptifs
- Pas de suppression de données sans confirmation
- Protection contre les modifications accidentelles

---

## 8. Découplage et Modularité

**Principe**: Les composants sont indépendants et interchangeables.

- Chaque fonctionnalité peut être utilisée indépendamment
- Les composants communiquent via interfaces définies
- Pas de dépendances circulaires
- Facilité d'extension sans modification du core

---

## 9. Transparence des Décisions

**Principe**: L'utilisateur comprend pourquoi le système agit de cette façon.

- Messages d'erreur explicatifs et actionnables
- Rapports détaillés des analyses effectuées
- Justification des recommandations
- Documentation des hypothèses et limitations

---

## 10. Robustesse et Tolérance aux Erreurs

**Principe**: Le système gère les erreurs gracieusement sans perte de données.

- Gestion des timeouts et erreurs réseau
- Retry automatique avec backoff exponentiel pour erreurs temporaires
- Dégradation gracieuse si fonctionnalité non disponible
- Jamais de crash silencieux

---

## 11. Performance Raisonnable

**Principe**: Le système répond dans des délais acceptables pour l'usage prévu.

- Opérations interactives < 5 secondes
- Workflows complets avec feedback de progression
- Cache intelligent pour éviter répétitions coûteuses
- Optimisation des appels externes

---

## 12. Respect des Standards du Projet Cible

**Principe**: Le système respecte les conventions existantes du projet analysé.

- Détection automatique des conventions de nommage
- Adaptation au style de code existant
- Respect de la structure de répertoires
- Compatibilité avec les outils existants (Maven, Git, Docker)

---

## 13. Simplicité d'Utilisation

**Principe**: L'utilisateur peut accomplir ses tâches avec un minimum d'effort.

- Configuration minimale requise pour démarrer
- Valeurs par défaut raisonnables
- Interface unifiée (CLI et Web)
- Documentation intégrée et accessible

---

## Governance

Cette constitution supersède toutes les autres pratiques. Toute modification requiert documentation et approbation.

**Version**: 1.0.0 | **Ratified**: 2025-11-23 | **Last Amended**: 2025-11-23
