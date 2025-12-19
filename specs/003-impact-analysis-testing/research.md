# Research: Impact Analysis & Regression Testing

**Date**: 2025-12-19 | **Branch**: `003-impact-analysis-testing`

## Overview

This document captures research findings for implementing impact analysis on git diffs to generate targeted regression tests.

---

## 1. Git Diff Parsing Strategy

### Decision: Use `git diff HEAD` with unified format

**Rationale**:
- `git diff HEAD` captures all uncommitted changes (staged + unstaged) as specified in FR-001
- Unified diff format (`-U3`) provides context lines for better change classification
- Native git command is cross-platform (Windows/Linux) and requires no additional dependencies

**Alternatives Considered**:
- `git diff --cached` - Only staged changes, rejected per clarification (user wants all uncommitted)
- `libgit2` bindings - Additional dependency, overkill for simple diff extraction
- GitHub/GitLab API - Requires remote, not applicable for local workflow

**Implementation**:
```python
# In src/mcp_servers/git_maintenance/tools/diff.py
def get_uncommitted_diff(project_path: str) -> str:
    result = subprocess.run(
        ["git", "diff", "HEAD", "-U3", "--no-color"],
        cwd=project_path,
        capture_output=True,
        text=True
    )
    return result.stdout
```

---

## 2. Change Category Detection

### Decision: Pattern-based file path + AST-aware content analysis

**Rationale**:
- File path patterns reliably identify layer (controller, service, repository, etc.)
- Content analysis catches edge cases (e.g., service logic in controller file)
- LLM assists with ambiguous cases and business rule detection

**Category Mapping** (FR-002):

| File Pattern | Primary Category | Test Type |
|--------------|------------------|-----------|
| `*Controller.java`, `*Resource.java` | endpoint | @WebMvcTest |
| `*Service.java`, `*ServiceImpl.java` | business_rule | Unit test (JUnit) |
| `*Repository.java`, `*Dao.java` | query | @DataJpaTest |
| `*Entity.java`, `*Model.java` | dto | Unit test |
| `**/migration/**`, `*.sql` | migration | @SpringBootTest |
| `*Client.java`, `**/api/**` | api_contract | Contract test (Pact) |
| `application*.yml`, `*Config.java` | configuration | Integration test |

**Alternatives Considered**:
- Pure LLM classification - Too slow, expensive for large diffs
- Java parser (JavaParser) - Added complexity, Python-Java bridge overhead
- Regex only - Misses semantic context

---

## 3. Risk Classification Algorithm

### Decision: Keyword-based scoring with configurable thresholds

**Rationale**:
- Fast evaluation without LLM call for common patterns
- Configurable for project-specific risk domains
- Fallback to LLM for edge cases

**Business-Critical Keywords** (FR-004):
```python
CRITICAL_KEYWORDS = {
    "payment", "billing", "invoice", "transaction", "money", "price",
    "auth", "login", "password", "token", "session", "permission", "role",
    "security", "encrypt", "decrypt", "secret", "credential",
    "order", "checkout", "cart", "purchase"
}
```

**Non-Critical Patterns**:
- Logging changes (`log.`, `logger.`, `LOG.`)
- Comment-only changes
- Formatting/whitespace
- Test file modifications

---

## 4. Test Pyramid Mapping

### Decision: Lowest viable test level per change category

**Rationale** (FR-005):
- Unit tests are fastest, cheapest, most reliable
- Higher levels only when lower level cannot verify behavior
- Follows Martin Fowler's test pyramid principle

**Test Level Selection**:

| Change Type | Preferred Test Level | Why |
|-------------|---------------------|-----|
| Pure business logic | Unit | No dependencies needed |
| Controller validation | @WebMvcTest | Needs HTTP layer, not full app |
| JPA query changes | @DataJpaTest | Needs real DB behavior |
| Service + DB interaction | @SpringBootTest (slice) | Complex wiring required |
| External API changes | Contract test | Verify interface agreement |

---

## 5. Diff Chunking Strategy

### Decision: File-based chunking with 500-line soft limit

**Rationale** (FR-011):
- File boundaries are natural chunk points
- Preserves context within a file
- Progress feedback per chunk

**Algorithm**:
```python
def chunk_diff(diff: str, max_lines: int = 500) -> list[DiffChunk]:
    files = split_by_file(diff)
    chunks = []
    current_chunk = []
    current_lines = 0

    for file_diff in files:
        file_lines = count_lines(file_diff)
        if current_lines + file_lines > max_lines and current_chunk:
            chunks.append(merge(current_chunk))
            current_chunk = []
            current_lines = 0
        current_chunk.append(file_diff)
        current_lines += file_lines

    if current_chunk:
        chunks.append(merge(current_chunk))
    return chunks
```

---

## 6. Impact Report Schema

### Decision: JSON with nested structure for CI parsing

**Rationale** (FR-009):
- JSON is universally parseable by CI tools
- Nested structure groups tests by impact
- Includes metadata for filtering and prioritization

**Schema Preview** (full schema in `/contracts/impact-report.schema.json`):
```json
{
  "version": "1.0",
  "generated_at": "ISO8601",
  "project_path": "/path/to/project",
  "summary": {
    "total_impacts": 5,
    "business_critical": 2,
    "non_critical": 3,
    "tests_generated": 12
  },
  "impacts": [
    {
      "id": "IMP-001",
      "file": "src/main/java/.../PaymentService.java",
      "category": "business_rule",
      "risk_level": "business_critical",
      "changes": ["calculateTotal", "applyDiscount"],
      "tests": [...]
    }
  ]
}
```

---

## 7. Error Handling & Retry

### Decision: Tenacity with exponential backoff

**Rationale** (FR-012):
- Already used in existing `test_generation_agent.py`
- Configurable retry count and delays
- Clean integration with async code

**Configuration**:
```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception_type(LLMError)
)
async def analyze_impact_with_llm(diff_chunk: str) -> list[Impact]:
    ...
```

---

## Summary

All technical decisions leverage existing TestBoost patterns and dependencies. No new external libraries required. The implementation extends the current architecture with:

1. New MCP tool for git diff extraction
2. New workflow for impact analysis
3. Enhanced test generation with impact-aware targeting
4. JSON report output for CI integration
