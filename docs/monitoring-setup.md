# Monitoring Setup Guide

Ce guide explique comment configurer le stack de monitoring Prometheus + Grafana pour TestBoost en production.

## Architecture

```
                    ┌─────────────────┐
                    │   Alertmanager  │
                    │   (Port 9093)   │
                    └────────┬────────┘
                             │ alerts
                             │
┌─────────────────┐   ┌──────┴────────┐   ┌─────────────────┐
│  TestBoost API  │───│   Prometheus  │───│     Grafana     │
│  (Port 8000)    │   │   (Port 9090) │   │   (Port 3000)   │
│    /metrics     │   │               │   │                 │
└─────────────────┘   └───────────────┘   └─────────────────┘
```

## Prérequis

- Docker et Docker Compose installés
- TestBoost API en cours d'exécution
- Ports 3000, 9090, 9093 disponibles

## Installation Rapide

### 1. Créer le Réseau Docker

```bash
docker network create testboost-network
```

### 2. Démarrer le Stack Monitoring

```bash
# Depuis la racine du projet TestBoost
docker compose -f docker-compose.yaml -f docker-compose.monitoring.yaml up -d
```

### 3. Vérifier les Services

```bash
docker compose -f docker-compose.yaml -f docker-compose.monitoring.yaml ps
```

Tous les services doivent être `running` :
- `testboost-prometheus` sur port 9090
- `testboost-grafana` sur port 3000
- `testboost-alertmanager` sur port 9093

### 4. Accéder aux Interfaces

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3000 | admin / testboost |
| Prometheus | http://localhost:9090 | - |
| Alertmanager | http://localhost:9093 | - |

## Configuration

### Prometheus

Le fichier de configuration se trouve dans `config/prometheus/prometheus.yml`.

**Scrape Targets** :
- TestBoost API : `http://host.docker.internal:8000/metrics`
- Prometheus lui-même : `http://localhost:9090`

Pour ajouter des targets supplémentaires :

```yaml
scrape_configs:
  - job_name: 'my-service'
    static_configs:
      - targets: ['my-service:8080']
```

### Alertes

Les règles d'alertes sont définies dans `config/prometheus/alerts.yml`.

**Alertes Préconfigurées** :

| Alerte | Seuil | Sévérité |
|--------|-------|----------|
| HighLLMErrorRate | > 5% | critical |
| SlowWorkflowExecution | > 5min (p95) | warning |
| DBConnectionPoolExhausted | > 90% | warning |
| TooManyActiveSessions | > 50 | warning |
| SlowAPIResponse | > 5s (p95) | warning |
| HealthCheckFailed | API down | critical |
| LLMRateLimitHit | > 10/hour | warning |

### Alertmanager

Configurez les notifications dans `config/alertmanager/alertmanager.yml`.

**Email** (décommenter et configurer) :
```yaml
receivers:
  - name: 'critical-receiver'
    email_configs:
      - to: 'team@example.com'
        from: 'alertmanager@testboost.local'
        smarthost: 'smtp.example.com:587'
```

**Slack** (décommenter et configurer) :
```yaml
receivers:
  - name: 'critical-receiver'
    slack_configs:
      - api_url: 'https://hooks.slack.com/services/XXX/YYY/ZZZ'
        channel: '#testboost-alerts'
```

**PagerDuty** (décommenter et configurer) :
```yaml
receivers:
  - name: 'critical-receiver'
    pagerduty_configs:
      - service_key: 'your-pagerduty-key'
```

### Grafana

#### Dashboards Préconfigurés

Le dashboard "TestBoost Overview" est automatiquement provisionné et inclut :

1. **Active Sessions** : Nombre de sessions en cours
2. **LLM Error Rate** : Taux d'erreur LLM (seuil 5%)
3. **LLM Calls (24h)** : Total des appels LLM sur 24h
4. **Workflow Duration (p95)** : Durée des workflows (95e percentile)
5. **LLM Calls by Provider** : Graphe temporel par provider
6. **Workflow Duration by Type** : Durée par type de workflow
7. **Database Connection Pool** : Utilisation du pool de connexions
8. **API Response Time** : Temps de réponse API (p50, p95, p99)

#### Ajouter un Dashboard

1. Créez un fichier JSON dans `config/grafana/dashboards/`
2. Redémarrez Grafana ou attendez 30 secondes (auto-reload)

## Métriques Exposées par TestBoost

L'API TestBoost expose les métriques suivantes sur `/metrics` :

### Counters

| Métrique | Labels | Description |
|----------|--------|-------------|
| `testboost_llm_calls_total` | provider, model | Nombre total d'appels LLM |
| `testboost_llm_errors_total` | provider, error_type | Nombre d'erreurs LLM |
| `testboost_llm_rate_limit_total` | provider | Rate limits rencontrés |
| `testboost_workflow_total` | workflow_type, status | Nombre de workflows exécutés |

### Gauges

| Métrique | Description |
|----------|-------------|
| `testboost_active_sessions` | Sessions actuellement actives |
| `testboost_db_connection_pool_size` | Connexions DB actives |
| `testboost_db_connection_pool_max` | Taille max du pool |

### Histograms

| Métrique | Labels | Description |
|----------|--------|-------------|
| `testboost_workflow_duration_seconds` | workflow_type | Durée des workflows |
| `testboost_llm_request_duration_seconds` | provider | Latence LLM |
| `testboost_http_request_duration_seconds` | method, path | Latence API |

## Troubleshooting

### Prometheus ne collecte pas les métriques

1. Vérifiez que TestBoost est accessible :
   ```bash
   curl http://localhost:8000/metrics
   ```

2. Vérifiez les targets dans Prometheus :
   - Accédez à http://localhost:9090/targets
   - Le target `testboost-api` doit être `UP`

3. Si Docker Desktop (Windows/Mac), utilisez `host.docker.internal` :
   ```yaml
   static_configs:
     - targets: ['host.docker.internal:8000']
   ```

### Grafana ne montre pas de données

1. Vérifiez la datasource Prometheus :
   - Allez dans Configuration > Data Sources
   - Testez la connexion

2. Vérifiez que Prometheus collecte des données :
   - Exécutez une requête directe : http://localhost:9090/graph
   - Testez : `testboost_active_sessions`

### Alertes non reçues

1. Vérifiez l'état des alertes dans Alertmanager :
   - http://localhost:9093/#/alerts

2. Vérifiez les logs :
   ```bash
   docker logs testboost-alertmanager
   ```

3. Vérifiez la configuration des receivers

## Maintenance

### Backup des Données

```bash
# Backup Prometheus data
docker cp testboost-prometheus:/prometheus ./prometheus-backup

# Backup Grafana data
docker cp testboost-grafana:/var/lib/grafana ./grafana-backup
```

### Mise à Jour

```bash
# Pull latest images
docker compose -f docker-compose.yaml -f docker-compose.monitoring.yaml pull

# Recreate containers
docker compose -f docker-compose.yaml -f docker-compose.monitoring.yaml up -d
```

### Arrêt du Stack

```bash
docker compose -f docker-compose.yaml -f docker-compose.monitoring.yaml down
```

### Suppression Complète (avec données)

```bash
docker compose -f docker-compose.yaml -f docker-compose.monitoring.yaml down -v
```

## Ressources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)
- [Alertmanager Documentation](https://prometheus.io/docs/alerting/latest/alertmanager/)

