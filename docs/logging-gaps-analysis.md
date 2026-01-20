# Analyse des Gaps de Logging - TestBoost

## Résumé Exécutif

Plusieurs catégories d'erreurs métier et techniques ne sont **pas loggées de manière structurée** ou **pas loggées du tout**.

---

## 🔴 Problèmes Critiques

### 1. HTTPException Non Loggées (50+ occurrences)

**Impact**: Aucune trace des erreurs client (400, 404, 409, etc.) dans les logs structurés.

**Fichiers concernés**:
- `src/api/routers/sessions.py` - 35+ HTTPException
- `src/api/routers/testboost.py` - 10+ HTTPException
- `src/api/routers/audit.py` - 5+ HTTPException

**Exemples**:
```python
# sessions.py:212
if request.session_type not in valid_types:
    raise HTTPException(  # ❌ PAS DE LOG
        status_code=400,
        detail=f"Invalid session type: {request.session_type}"
    )

# sessions.py:306
if not session:
    raise HTTPException(  # ❌ PAS DE LOG
        status_code=404,
        detail=f"Session not found: {session_id}"
    )

# sessions.py:526
if session.status not in [SessionStatus.PENDING.value, ...]:
    raise HTTPException(  # ❌ PAS DE LOG
        status_code=400,
        detail=f"Cannot execute: session is {session.status}"
    )
```

**Problème**: Ces exceptions sont capturées par FastAPI mais ne génèrent aucun log structuré, donc:
- Impossible de tracker les erreurs utilisateurs
- Pas de métriques sur les erreurs 400/404
- Debugging difficile

---

### 2. Exceptions Unhandled Non Structurées

**Exemple trouvé dans `logs/testboost_20260111.log:44-72`**:

```
Exception terminating connection <AdaptedConnection <asyncpg.connection.Connection...>>
Traceback (most recent call last):
  File "...sqlalchemy/pool/base.py", line 372, in _close_connection
    self._dialect.do_terminate(connection)
  ...
RuntimeError: Event loop is closed
```

**Problème**: Cette exception SQLAlchemy n'est pas capturée par structlog:
- Traceback brut dans les logs (pas de JSON)
- Pas de champ `event`, `level`, `logger`
- Impossible de filtrer/parser automatiquement

**Cause**: L'exception se produit pendant le shutdown, probablement hors du contexte de la requête HTTP.

---

### 3. Request ID Toujours "unknown"

**Observations dans les logs**:
```json
{"request_id": "unknown", "method": "GET", "path": "/health", ...}
{"request_id": "unknown", "method": "GET", "path": "/api/v2/sessions", ...}
```

**Cause**: L'ordre des middlewares dans `src/api/main.py` est incorrect:

```python
# main.py:90-97
app.add_middleware(RequestIDMiddleware)       # ✅ Ajoute request_id
app.add_middleware(ErrorHandlerMiddleware)    # ⚠️ N'a pas accès au request_id
app.middleware("http")(request_logging_middleware)  # ⚠️ Exécuté AVANT les middlewares
app.middleware("http")(api_key_auth_middleware)
```

**Ordre d'exécution réel** (LIFO pour `app.middleware("http")`):
1. `api_key_auth_middleware`
2. `request_logging_middleware` ← Log le request_id = "unknown"
3. `ErrorHandlerMiddleware`
4. `RequestIDMiddleware` ← Ajoute request_id trop tard

**Impact**: Impossible de tracer les requêtes individuellement dans les logs.

---

## 🟠 Problèmes Importants

### 4. Validations Pydantic Non Loggées

Les erreurs de validation Pydantic (FastAPI) ne sont pas loggées de manière structurée:

```python
# sessions.py - CreateSessionRequest
class CreateSessionRequest(BaseModel):
    project_path: str  # ❌ Si invalide, pas de log métier
    session_type: str  # ❌ Si invalide, pas de log métier
    mode: str = "interactive"
```

**Problème**: FastAPI retourne automatiquement une 422, mais on ne voit pas:
- Quel champ a échoué
- Quelle valeur était fournie
- Combien d'erreurs de validation on a par jour

---

### 5. Erreurs de Transition de Statut Non Loggées

**Exemple** `sessions.py:686`:
```python
if request.status not in allowed_transitions[current_status]:
    raise HTTPException(  # ❌ PAS DE LOG
        status_code=400,
        detail=f"Invalid transition from {current_status} to {request.status}"
    )
```

**Impact métier**: Impossible de savoir:
- Si des clients tentent des transitions invalides
- Si la machine à états est mal comprise
- Si c'est un bug dans le frontend

---

### 6. Timeouts Partiellement Loggés

**Loggé**:
```python
# test_generation_agent.py:1399
except subprocess.TimeoutExpired:
    logger.error("maven_tests_timeout", module=module, timeout=TEST_TIMEOUT_SECONDS)
```

**Non loggé**:
```python
# workflows/test_generation_agent.py:507
except TimeoutError as e:
    logger.warning("agent_invoke_timeout", error=str(e))
    raise  # Will retry
```

Mais les retry ne sont pas comptés ni loggés.

---

### 7. Format Inconsistant en Dev vs Prod

**Configuration** `src/lib/logging.py:63-88`:

```python
is_development = sys.stderr.isatty()

if is_development:
    processors = [
        *shared_processors,
        structlog.dev.ConsoleRenderer(colors=True),  # ✅ Lisible
    ]
else:
    processors = [
        *shared_processors,
        structlog.processors.format_exc_info,  # ⚠️ Seulement en prod!
        structlog.processors.JSONRenderer(),
    ]
```

**Problème**:
- En **dev**: Les stack traces ne sont pas dans le JSON structuré
- En **prod**: Les stack traces sont dans le champ `exception`
- **Inconsistance** rend le debugging difficile selon l'environnement

---

## 🟡 Problèmes Mineurs

### 8. Erreurs LLM Rate Limit Loggées Mais Pas Métriquées

```python
# test_generation_agent.py:513
if "429" in error_msg or "rate limit" in error_msg.lower():
    logger.error("agent_invoke_rate_limit", error=error_msg)
    # ⚠️ Pas de métrique exposée
```

**Besoin**: Métriques Prometheus pour suivre les rate limits par provider.

---

### 9. Artifacts Content Errors Peu Détaillés

```python
# sessions.py:810
if artifact.size_bytes > MAX_CONTENT_SIZE_BYTES:
    raise HTTPException(  # ❌ Pas de log avec la taille demandée
        status_code=413,
        detail=f"Content too large (max {MAX_CONTENT_SIZE_BYTES} bytes)"
    )
```

**Amélioration possible**: Logger la taille demandée vs limite.

---

## 📋 Recommandations

### Priorité 1 (Critique)

1. **Ajouter logging pour toutes les HTTPException**
   ```python
   # Avant
   if not session:
       raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

   # Après
   if not session:
       logger.warning("session_not_found", session_id=str(session_id), path=request.url.path)
       raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
   ```

2. **Corriger l'ordre des middlewares**
   ```python
   # main.py - Ordre correct
   app.add_middleware(RequestIDMiddleware)  # 1. Ajouter request_id en premier

   # app.middleware("http") s'exécute dans l'ordre inverse (LIFO)
   app.middleware("http")(api_key_auth_middleware)      # 4. Auth
   app.middleware("http")(request_logging_middleware)   # 3. Log (avec request_id)

   app.add_middleware(ErrorHandlerMiddleware)  # 2. Errors (avec request_id)
   ```

3. **Capturer les exceptions SQLAlchemy/asyncio**
   - Ajouter un exception handler pour `RuntimeError` dans le context manager du pool DB
   - Logger proprement les erreurs de connection cleanup

### Priorité 2 (Important)

4. **Logger les validations Pydantic**
   - Créer un exception handler pour `RequestValidationError`
   ```python
   from fastapi.exceptions import RequestValidationError

   @app.exception_handler(RequestValidationError)
   async def validation_exception_handler(request: Request, exc: RequestValidationError):
       logger.warning("validation_error",
           errors=exc.errors(),
           body=exc.body,
           path=request.url.path
       )
       return JSONResponse(status_code=422, content={"detail": exc.errors()})
   ```

5. **Unifier le format dev/prod**
   - Toujours utiliser `format_exc_info` même en dev
   - Ajouter une variable d'environnement pour forcer le mode JSON

6. **Ajouter des métriques pour les rate limits**
   - Exposer `testboost_llm_rate_limit_total{provider="google-genai"}` dans `/metrics`

### Priorité 3 (Nice-to-have)

7. **Logger les retry avec compteur**
   ```python
   logger.warning("agent_invoke_timeout_retry",
       error=str(e),
       attempt=attempt_number,
       max_attempts=MAX_RETRIES
   )
   ```

8. **Enrichir les logs d'erreurs métier**
   - Ajouter context pour chaque HTTPException
   - Logger les valeurs invalides (session_type, status, etc.)

---

## Catégories d'Erreurs Non Loggées

| Catégorie | Exemple | Fichier | Criticité |
|-----------|---------|---------|-----------|
| **Validation request** | Invalid session_type | `sessions.py:212` | 🔴 Critique |
| **Not found** | Session not found | `sessions.py:306` | 🔴 Critique |
| **Invalid transitions** | Cannot execute step | `sessions.py:526` | 🟠 Important |
| **Size limits** | Content too large | `sessions.py:810` | 🟡 Mineur |
| **Binary content** | Unsupported binary | `sessions.py:834` | 🟡 Mineur |
| **Pydantic validation** | Field validation errors | FastAPI auto | 🟠 Important |
| **SQLAlchemy cleanup** | Event loop closed | DB pool | 🔴 Critique |
| **Rate limits** | LLM 429 errors | `test_generation_agent.py:513` | 🟠 Important |

---

## Métriques de Complétude des Logs

- **HTTPException loggées**: 0% (0/50+)
- **Request ID valide**: 0% ("unknown" partout)
- **Exceptions structurées**: 80% (sauf SQLAlchemy cleanup)
- **Format dev/prod**: Inconsistant (format_exc_info seulement en prod)
- **Validation errors**: Non loggées (FastAPI auto-handle)

---

## Prochaines Étapes

1. ✅ Créer ce document d'analyse
2. ⬜ Créer une feature spec pour corriger les gaps critiques
3. ⬜ Implémenter le logging des HTTPException
4. ⬜ Corriger l'ordre des middlewares
5. ⬜ Ajouter les exception handlers Pydantic
6. ⬜ Créer des tests pour vérifier la complétude des logs
