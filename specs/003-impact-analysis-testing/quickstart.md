# Quickstart: Impact Analysis & Regression Testing

**Date**: 2025-12-19 | **Branch**: `003-impact-analysis-testing`

## Overview

This guide explains how to use TestBoost's impact analysis feature to generate targeted regression tests based on your code changes.

---

## Prerequisites

- TestBoost installed (`pip install testboost` or poetry install)
- Git repository with uncommitted changes
- Java project with Maven or Gradle

---

## Basic Usage

### 1. Analyze Impact of Your Changes

From your project root, run:

```bash
boost tests impact /path/to/java-project
```

This will:
1. Detect uncommitted changes in your working directory
2. Classify each change by category and risk level
3. Generate an impact report

### 2. View the Impact Report

The command outputs a JSON report to stdout:

```json
{
  "version": "1.0",
  "summary": {
    "total_impacts": 3,
    "business_critical": 1,
    "non_critical": 2,
    "tests_to_generate": 7
  },
  "impacts": [...]
}
```

Save to file:
```bash
boost tests impact /path/to/project > impact-report.json
```

### 3. Generate Tests from Impact Report

Generate tests targeting the identified impacts:

```bash
boost tests generate /path/to/project --impact-report impact-report.json
```

---

## Command Options

```bash
boost tests impact [OPTIONS] PROJECT_PATH

Options:
  --output, -o PATH      Save report to file (default: stdout)
  --format [json|pretty] Output format (default: json)
  --verbose, -v          Show progress and debug info
  --chunk-size INT       Max lines per chunk (default: 500)
  --help                 Show this help message
```

---

## Example Workflow

### Scenario: You modified a PaymentService

1. Make your changes:
   ```java
   // PaymentService.java
   public BigDecimal calculateTotal(Order order) {
       // Your changes here
   }
   ```

2. Run impact analysis:
   ```bash
   boost tests impact . --verbose
   ```

3. Output shows:
   ```
   📊 Impact Analysis
   ─────────────────────────────────────
   Files analyzed: 1
   Impacts found: 1 (1 business-critical)

   🔴 IMP-001: PaymentService.calculateTotal
      Category: business_rule
      Risk: business_critical
      Tests needed:
        - TEST-001: Unit test (nominal)
        - TEST-002: Unit test (edge case: zero amount)
        - TEST-003: Invariant test (total >= 0)
   ```

4. Generate the tests:
   ```bash
   boost tests generate . --impact-report impact-report.json
   ```

---

## CI Integration

Add to your GitHub Actions workflow:

```yaml
- name: Analyze Impact
  run: |
    boost tests impact . -o impact-report.json

- name: Check Coverage
  run: |
    # Fail if business-critical impacts have no tests
    jq '.summary.business_critical' impact-report.json | \
      xargs -I {} test {} -eq 0 || \
      echo "::warning::Business-critical changes detected"
```

---

## Risk Classification

| Risk Level | Examples | Action |
|------------|----------|--------|
| `business_critical` | Payment, auth, security | Must have tests |
| `non_critical` | Logging, formatting | Optional tests |

---

## Test Types Generated

| Change Category | Test Type | Spring Annotation |
|-----------------|-----------|-------------------|
| business_rule | Unit test | None (plain JUnit) |
| endpoint | Controller test | @WebMvcTest |
| query | Data layer test | @DataJpaTest |
| api_contract | Contract test | @SpringBootTest |

---

## Troubleshooting

### "No impacts detected"

- Ensure you have uncommitted changes: `git status`
- Changes to test files are intentionally excluded

### "Chunk timeout"

For very large diffs, reduce chunk size:
```bash
boost tests impact . --chunk-size 300
```

### "LLM API error"

The system automatically retries 3 times with exponential backoff. If it still fails:
- Check your API key configuration
- Verify network connectivity
