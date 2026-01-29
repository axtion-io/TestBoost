# TestBoost Manual Test Checklist

This document provides a structured checklist for manual testing of TestBoost features.
Use this checklist before releases and for QA validation.

## Pre-Test Setup

- [ ] PostgreSQL 15 running on port 5433
- [ ] Environment variables configured (see `.env.example`)
- [ ] Python 3.11+ virtual environment activated
- [ ] Dependencies installed (`pip install -e ".[dev]"`)
- [ ] Test project available (spring-petclinic-microservices recommended)

---

## 1. CLI Commands Testing

### 1.1 Maintenance Commands

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| CLI-M01 | List outdated dependencies | `python -m src.cli.main maintenance list <project-path>` | Shows list of Maven dependencies with update status | ☐ |
| CLI-M02 | Run maintenance with dry-run | `python -m src.cli.main maintenance run <project-path> --dry-run` | Shows what would be updated without making changes | ☐ |
| CLI-M03 | Run maintenance (actual) | `python -m src.cli.main maintenance run <project-path>` | Updates pom.xml files with newer versions | ☐ |
| CLI-M04 | Invalid project path | `python -m src.cli.main maintenance list /nonexistent` | Shows clear error message | ☐ |
| CLI-M05 | Non-Maven project | `python -m src.cli.main maintenance list <non-maven-project>` | Shows "no pom.xml found" message | ☐ |

### 1.2 Test Generation Commands

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| CLI-T01 | Analyze test coverage | `python -m src.cli.main tests analyze <project-path>` | Shows coverage metrics and untested classes | ☐ |
| CLI-T02 | Generate tests (LLM mode) | `python -m src.cli.main tests generate <project-path>` | Generates JUnit tests using LLM | ☐ |
| CLI-T03 | Generate tests (template mode) | `python -m src.cli.main tests generate <project-path> --no-llm` | Generates template-based tests | ☐ |
| CLI-T04 | Verbose output | `python -m src.cli.main tests generate <project-path> --verbose` | Shows detailed generation progress | ☐ |
| CLI-T05 | Specific class targeting | `python -m src.cli.main tests generate <project-path> --class com.example.Service` | Generates tests only for specified class | ☐ |

### 1.3 Deploy Commands

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| CLI-D01 | Docker build | `python -m src.cli.main deploy docker <project-path>` | Builds Docker image for the project | ☐ |
| CLI-D02 | Docker dry-run | `python -m src.cli.main deploy docker <project-path> --dry-run` | Shows build commands without executing | ☐ |
| CLI-D03 | Missing Dockerfile | Run deploy on project without Dockerfile | Shows helpful error message | ☐ |

---

## 2. API Endpoint Testing

### 2.1 Health & Status

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| API-H01 | Health check | `GET /health` | Returns `{"status": "healthy"}` with 200 | ☐ |
| API-H02 | API version | `GET /api/v2/version` | Returns version info | ☐ |

### 2.2 Sessions API

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| API-S01 | Create session | `POST /api/v2/sessions` with valid body | Returns 201 with session ID | ☐ |
| API-S02 | Get session | `GET /api/v2/sessions/{id}` | Returns session details | ☐ |
| API-S03 | List sessions | `GET /api/v2/sessions` | Returns paginated list | ☐ |
| API-S04 | Delete session | `DELETE /api/v2/sessions/{id}` | Returns 204 on success | ☐ |
| API-S05 | Invalid session ID | `GET /api/v2/sessions/invalid-uuid` | Returns 404 with error message | ☐ |

### 2.3 Steps API

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| API-ST01 | Get steps for session | `GET /api/v2/sessions/{id}/steps` | Returns list of steps | ☐ |
| API-ST02 | Get specific step | `GET /api/v2/sessions/{id}/steps/{step_id}` | Returns step details | ☐ |
| API-ST03 | Steps for nonexistent session | `GET /api/v2/sessions/fake-id/steps` | Returns 404 | ☐ |

### 2.4 Artifacts API

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| API-A01 | Get artifacts | `GET /api/v2/sessions/{id}/artifacts` | Returns artifact list | ☐ |
| API-A02 | Download artifact | `GET /api/v2/sessions/{id}/artifacts/{aid}/download` | Returns file content | ☐ |
| API-A03 | Invalid artifact | `GET /api/v2/sessions/{id}/artifacts/fake-id` | Returns 404 | ☐ |

---

## 3. Workflow Testing

### 3.1 Maven Maintenance Workflow

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| WF-M01 | Full maintenance cycle | Start session → run maintenance → verify artifacts | Workflow completes with updated POMs | ☐ |
| WF-M02 | Workflow interruption | Stop workflow mid-process | Graceful shutdown, no partial writes | ☐ |
| WF-M03 | Concurrent sessions | Run 2 maintenance sessions simultaneously | Both complete without interference | ☐ |

### 3.2 Test Generation Workflow

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| WF-T01 | Full generation cycle | Analyze → Generate → Verify tests | Valid JUnit tests created | ☐ |
| WF-T02 | LLM fallback | Disconnect LLM mid-generation | Falls back to template mode | ☐ |
| WF-T03 | Large project handling | Generate tests for 50+ classes | Completes with batching | ☐ |

---

## 4. Database Operations

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| DB-01 | Connection handling | Start app with valid DB credentials | Connects successfully | ☐ |
| DB-02 | Connection failure | Start app with wrong credentials | Shows clear error, doesn't crash | ☐ |
| DB-03 | Session persistence | Create session, restart app, retrieve session | Session data preserved | ☐ |
| DB-04 | Transaction rollback | Create session with error mid-process | No partial data in DB | ☐ |

---

## 5. Error Handling

| Test ID | Test Case | Steps | Expected Result | Status |
|---------|-----------|-------|-----------------|--------|
| ERR-01 | Invalid JSON payload | Send malformed JSON to API | Returns 400 with error details | ☐ |
| ERR-02 | Missing required fields | POST session without project_path | Returns 422 with field errors | ☐ |
| ERR-03 | Rate limiting | Send 100+ requests in 1 second | Returns 429 after threshold | ☐ |
| ERR-04 | Large payload | Send >10MB request body | Returns 413 | ☐ |

---

## Test Execution Log

| Date | Tester | Environment | Tests Run | Pass | Fail | Notes |
|------|--------|-------------|-----------|------|------|-------|
| | | | | | | |

---

## Sign-Off

- [ ] All critical tests (P1) passed
- [ ] No blocking issues found
- [ ] Performance acceptable on standard hardware
- [ ] Documentation reflects current behavior

**Tested by:** _______________
**Date:** _______________
**Version:** _______________
