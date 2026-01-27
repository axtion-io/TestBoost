# TestBoost Smoke Test Protocol

Quick validation tests to verify basic functionality after deployment or significant changes.
Execute these tests in order - stop if any test fails.

## Prerequisites

- PostgreSQL 15 running on port 5433
- Application started successfully
- Test project available

## Smoke Test Sequence (5-10 minutes)

### Step 1: Health Check (30 seconds)

```bash
# Expected: {"status": "healthy"}
curl -s http://localhost:8000/health | jq .
```

**Pass criteria:** Returns HTTP 200 with `status: healthy`

---

### Step 2: CLI Basic Execution (1 minute)

```bash
# Expected: Help output displayed
python -m src.cli.main --help

# Expected: Version information
python -m src.cli.main --version
```

**Pass criteria:** Both commands execute without errors

---

### Step 3: Database Connectivity (1 minute)

```bash
# Expected: Session created with UUID
curl -X POST http://localhost:8000/api/v2/sessions \
  -H "Content-Type: application/json" \
  -d '{"project_path": "/tmp/test-project"}'
```

**Pass criteria:** Returns HTTP 201 with session ID

---

### Step 4: Session Retrieval (30 seconds)

```bash
# Replace {session_id} with ID from Step 3
curl -s http://localhost:8000/api/v2/sessions/{session_id} | jq .
```

**Pass criteria:** Returns session details with correct project_path

---

### Step 5: CLI-to-API Integration (2 minutes)

```bash
# Run maintenance list (even with no updates expected)
python -m src.cli.main maintenance list test-projects/spring-petclinic-microservices
```

**Pass criteria:** Command executes, shows dependency information or "no updates found"

---

### Step 6: Cleanup (30 seconds)

```bash
# Delete the test session
curl -X DELETE http://localhost:8000/api/v2/sessions/{session_id}
```

**Pass criteria:** Returns HTTP 204

---

## Quick Decision Matrix

| All 6 tests pass | → Smoke test PASSED ✅ |
|------------------|------------------------|
| Any test fails   | → STOP - investigate before proceeding ❌ |

## Automated Smoke Test

Run all smoke tests with a single command:

```bash
# From project root
python scripts/test-utils/smoke_test.py
```

---

## Post-Deployment Checklist

After successful smoke test:

- [ ] Application logs show no errors
- [ ] Database migrations applied (if any)
- [ ] Environment variables correct for target environment
- [ ] External integrations accessible (LLM API, etc.)
