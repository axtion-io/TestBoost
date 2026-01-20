# Data Model: Test Plan for TestBoost

**Feature**: 004-test-plan-documentation
**Date**: 2026-01-04

## Overview

This document defines the data entities, fixtures, and test contracts for the TestBoost test infrastructure.

---

## 1. Test Entities

### TestCase

Represents a single test execution result.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | string | Full test name (module::class::method) | Required, unique per run |
| `category` | enum | `unit`, `integration`, `e2e` | Required |
| `status` | enum | `passed`, `failed`, `skipped`, `error` | Required |
| `duration_ms` | integer | Execution time in milliseconds | >= 0 |
| `error_message` | string | Failure reason if status != passed | Optional |
| `file_path` | string | Path to test file | Required |
| `line_number` | integer | Line number in test file | >= 1 |

### TestSuite

A collection of related test cases.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | string | Suite identifier (e.g., `api_tests`) | Required |
| `tests` | TestCase[] | List of test cases | >= 0 items |
| `total` | integer | Total tests in suite | >= 0 |
| `passed` | integer | Passed tests count | >= 0 |
| `failed` | integer | Failed tests count | >= 0 |
| `skipped` | integer | Skipped tests count | >= 0 |
| `duration_ms` | integer | Total suite execution time | >= 0 |

### TestReport

Aggregated results from a test run.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `run_id` | uuid | Unique run identifier | Required |
| `timestamp` | datetime | When tests were executed | Required |
| `suites` | TestSuite[] | All test suites | >= 1 |
| `coverage` | CoverageReport | Coverage metrics | Optional |
| `environment` | Environment | Execution environment | Required |

### CoverageReport

Coverage metrics from pytest-cov.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `line_coverage` | float | Line coverage percentage | 0.0 - 100.0 |
| `branch_coverage` | float | Branch coverage percentage | 0.0 - 100.0 |
| `uncovered_lines` | UncoveredLine[] | Lines not covered | >= 0 items |

### Environment

Test execution environment details.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `python_version` | string | Python version (e.g., `3.11.4`) | Required |
| `platform` | string | OS platform (e.g., `ubuntu-latest`) | Required |
| `ci` | boolean | Running in CI environment | Required |
| `parallel_workers` | integer | Number of xdist workers | >= 1 |

---

## 2. Fixture Entities

### LLMFixture

Pre-recorded LLM responses for mocking.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `provider` | enum | `gemini`, `claude`, `openai` | Required |
| `operation` | string | Operation type (e.g., `analyze_class`) | Required |
| `input_hash` | string | Hash of input for matching | Required |
| `response` | object | Mocked response payload | Required |
| `tokens_used` | integer | Simulated token count | >= 0 |

### DatabaseFixture

Test data for database operations.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `table` | string | Target table name | Required |
| `records` | object[] | Records to insert | >= 0 items |
| `cleanup_after` | boolean | Delete after test | Default: true |

### MavenProjectFixture

Sample Maven project data for testing.

| Field | Type | Description | Validation |
|-------|------|-------------|------------|
| `name` | string | Project name | Required |
| `pom_xml` | string | pom.xml content | Required |
| `dependencies` | Dependency[] | Expected dependencies | >= 0 items |
| `modules` | string[] | Multi-module children | >= 0 items |

---

## 3. State Transitions

### Test Execution State Machine

```
[PENDING] -> [RUNNING] -> [PASSED]
                       -> [FAILED]
                       -> [SKIPPED]
                       -> [ERROR]
```

| Transition | Trigger | Validation |
|------------|---------|------------|
| PENDING -> RUNNING | Test starts | None |
| RUNNING -> PASSED | All assertions pass | duration_ms > 0 |
| RUNNING -> FAILED | Assertion fails | error_message required |
| RUNNING -> SKIPPED | Skip marker or condition | reason optional |
| RUNNING -> ERROR | Exception thrown | error_message required |

### Fixture Lifecycle

```
[CREATED] -> [LOADED] -> [ACTIVE] -> [CLEANUP] -> [DESTROYED]
```

| State | Description |
|-------|-------------|
| CREATED | Fixture file exists |
| LOADED | Fixture parsed into memory |
| ACTIVE | Fixture available to test |
| CLEANUP | Post-test cleanup in progress |
| DESTROYED | Fixture resources released |

---

## 4. Relationships

```
TestReport (1) ──────> (N) TestSuite
TestSuite (1) ──────> (N) TestCase
TestReport (1) ──────> (1) CoverageReport
TestReport (1) ──────> (1) Environment

LLMFixture (N) ──────> (1) tests/fixtures/llm_responses/
DatabaseFixture (N) ──────> (1) conftest.py
MavenProjectFixture (N) ──────> (1) tests/fixtures/test_projects/
```

---

## 5. Validation Rules

### Test Timing
- Unit tests: max 100ms each
- Integration tests: max 5000ms each
- Total suite: max 5 minutes (300,000ms)

### Coverage Thresholds
- Line coverage: >= 70%
- Branch coverage: >= 60%
- Fail CI if below threshold

### Fixture Constraints
- LLM fixtures: JSON format, < 1MB each
- Database fixtures: YAML format, < 100 records
- Maven fixtures: Valid XML, < 10KB

---

## 6. Example Records

### TestCase Example
```json
{
  "name": "tests/unit/api/test_health.py::test_health_endpoint_returns_200",
  "category": "unit",
  "status": "passed",
  "duration_ms": 45,
  "file_path": "tests/unit/api/test_health.py",
  "line_number": 12
}
```

### LLMFixture Example
```json
{
  "provider": "gemini",
  "operation": "analyze_class",
  "input_hash": "abc123...",
  "response": {
    "class_name": "com.example.UserService",
    "methods": ["createUser", "getUser"],
    "complexity": 5
  },
  "tokens_used": 150
}
```

### TestReport Example
```json
{
  "run_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-01-04T10:30:00Z",
  "suites": [...],
  "coverage": {
    "line_coverage": 75.5,
    "branch_coverage": 62.3
  },
  "environment": {
    "python_version": "3.11.4",
    "platform": "ubuntu-latest",
    "ci": true,
    "parallel_workers": 2
  }
}
```
