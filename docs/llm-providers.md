# LLM Providers Configuration

TestBoost supporte plusieurs fournisseurs LLM (Large Language Models) pour les workflows d'analyse et de génération. Ce document décrit comment configurer et utiliser chaque provider.

## Providers Supportés

| Provider | Modèle Recommandé | Coût (1M tokens) | Latence Typique | Usage |
|----------|-------------------|------------------|-----------------|-------|
| **Google Gemini** | `gemini-2.0-flash` | $0.075 input / $0.30 output | 1-3s | Défaut recommandé |
| **Anthropic Claude** | `claude-sonnet-4-20250514` | $3.00 input / $15.00 output | 2-5s | Meilleure qualité |
| **OpenAI GPT-4o** | `gpt-4o` | $2.50 input / $10.00 output | 2-4s | Polyvalent |

## Configuration Rapide

### 1. Variables d'Environnement

Créez un fichier `.env` à la racine du projet :

```env
# Provider par défaut (choisir un seul)
MODEL=gemini-2.0-flash

# Clés API (configurer celle du provider choisi)
GOOGLE_API_KEY=your-google-api-key
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key
```

### 2. Changement de Provider

Pour changer de provider, modifiez simplement la variable `MODEL` :

```env
# Pour Gemini (recommandé pour le développement)
MODEL=gemini-2.0-flash

# Pour Claude (meilleure qualité de code)
MODEL=anthropic/claude-sonnet-4-20250514

# Pour GPT-4o
MODEL=openai/gpt-4o
```

**Important** : Redémarrez l'application après modification du `.env`.

## SC-004 : Zero Code Changes

TestBoost respecte le critère **SC-004** : le changement de provider LLM ne nécessite **aucune modification de code**.

- Tous les providers utilisent la même API (`get_llm()`)
- Les artifacts générés ont le même schéma
- Les workflows fonctionnent de manière identique

## Comparaison Détaillée

### Google Gemini (gemini-2.0-flash)

**Avantages** :
- Quota gratuit généreux (1500 req/jour)
- Faible latence
- Bon rapport qualité/prix

**Inconvénients** :
- Moins précis sur le code complexe
- Timeouts occasionnels (504)

**Configuration** :
```env
MODEL=gemini-2.0-flash
GOOGLE_API_KEY=AIza...
```

### Anthropic Claude (claude-sonnet-4-20250514)

**Avantages** :
- Excellente qualité de génération de code
- Meilleur raisonnement sur les architectures
- Très fiable

**Inconvénients** :
- Coût plus élevé
- Latence légèrement supérieure

**Configuration** :
```env
MODEL=anthropic/claude-sonnet-4-20250514
ANTHROPIC_API_KEY=sk-ant-...
```

### OpenAI GPT-4o

**Avantages** :
- Polyvalent
- Bonne documentation officielle
- Large écosystème

**Inconvénients** :
- Coût modéré
- Moins spécialisé en code Java

**Configuration** :
```env
MODEL=openai/gpt-4o
OPENAI_API_KEY=sk-...
```

## Estimation des Coûts

### Par Workflow

| Workflow | Tokens Estimés | Gemini | Claude | GPT-4o |
|----------|----------------|--------|--------|--------|
| Maven Maintenance | ~5K input + 2K output | $0.001 | $0.045 | $0.033 |
| Test Generation | ~20K input + 10K output | $0.005 | $0.21 | $0.15 |
| Docker Deployment | ~8K input + 3K output | $0.002 | $0.069 | $0.05 |
| Impact Analysis | ~15K input + 5K output | $0.003 | $0.12 | $0.088 |

### Par Projet (Estimation Mensuelle)

Pour un projet moyen avec 10 workflows/jour :

| Provider | Coût Mensuel Estimé |
|----------|---------------------|
| Gemini | ~$3 - $10 |
| Claude | ~$50 - $150 |
| GPT-4o | ~$40 - $100 |

## Validation Multi-Provider

Pour valider que tous les providers fonctionnent correctement :

```bash
# Exécuter le script de validation
python scripts/validate_multi_provider.py
```

Ce script teste chaque provider configuré et génère un rapport :
- Latence mesurée
- Tokens utilisés
- Coût estimé
- Validation SC-004

Les résultats sont sauvegardés dans `logs/multi_provider_validation.json`.

## Gestion des Erreurs

### Rate Limit (429)

Si vous dépassez les limites :
```
LLM rate limit exceeded by {provider}. Retry after {duration} seconds.
```

**Solutions** :
- Attendre le délai indiqué
- Réduire la fréquence des appels
- Passer à un provider avec quota plus élevé

### Timeout

Si les requêtes échouent par timeout :
```
LLM request timeout after 120s
```

**Solutions** :
- Vérifier la connexion réseau
- Augmenter `LLM_TIMEOUT` dans `.env`
- Réessayer plus tard (problème provider)

### API Key Invalide

```
API key not configured for provider 'anthropic'
```

**Solutions** :
- Vérifier la variable d'environnement
- Régénérer la clé API si expirée
- S'assurer que le fichier `.env` est chargé

## Recommandations

| Cas d'usage | Provider Recommandé |
|-------------|---------------------|
| Développement local | Gemini (gratuit) |
| CI/CD | Gemini (coût minimal) |
| Production (qualité) | Claude |
| Budget limité | Gemini |
| Grands projets | Claude ou GPT-4o |

## Observabilité

Pour tracer les appels LLM avec LangSmith :

```env
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=testboost
```

Cela permet de visualiser :
- Toutes les invocations LLM
- Les tokens utilisés
- Les latences détaillées
- Les erreurs et retries
