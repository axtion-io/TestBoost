# Data Model: Impact Analysis & Regression Testing

**Date**: 2025-12-19 | **Branch**: `003-impact-analysis-testing`

## Overview

This document defines the data entities for impact analysis and test generation targeting.

---

## Entities

### 1. ChangeCategory (Enum)

Classification of code change types per FR-002.

```python
class ChangeCategory(str, Enum):
    BUSINESS_RULE = "business_rule"      # Service logic, domain rules
    ENDPOINT = "endpoint"                 # Controllers, REST resources
    DTO = "dto"                          # Data transfer objects, entities
    QUERY = "query"                      # Repository methods, JPA queries
    MIGRATION = "migration"              # Database migrations, SQL scripts
    API_CONTRACT = "api_contract"        # External API clients, contracts
    CONFIGURATION = "configuration"      # Application config, Spring beans
    TEST = "test"                        # Test file modifications
    OTHER = "other"                      # Unclassified changes
```

### 2. RiskLevel (Enum)

Risk classification per FR-004.

```python
class RiskLevel(str, Enum):
    BUSINESS_CRITICAL = "business_critical"  # Payment, auth, security
    NON_CRITICAL = "non_critical"            # Logging, formatting, docs
```

### 3. TestType (Enum)

Test level selection per FR-005 (test pyramid).

```python
class TestType(str, Enum):
    UNIT = "unit"                    # JUnit, pure logic
    CONTROLLER = "controller"         # @WebMvcTest, MockMvc
    DATA_LAYER = "data_layer"        # @DataJpaTest
    INTEGRATION = "integration"       # @SpringBootTest
    CONTRACT = "contract"            # Pact, Spring Cloud Contract
```

### 4. Impact

Represents a single code change and its effects.

```python
@dataclass
class Impact:
    id: str                          # Unique identifier (e.g., "IMP-001")
    file_path: str                   # Relative path to changed file
    category: ChangeCategory         # Type of change
    risk_level: RiskLevel            # Business criticality
    affected_components: list[str]   # Classes/methods affected
    required_test_type: TestType     # Recommended test level
    change_summary: str              # Human-readable description
    diff_lines: tuple[int, int]      # Start/end lines in diff
    is_bug_fix: bool                 # Detected from commit message/keywords

    # Derived fields
    @property
    def requires_regression_test(self) -> bool:
        return self.is_bug_fix

    @property
    def requires_invariant_test(self) -> bool:
        return (self.category == ChangeCategory.BUSINESS_RULE
                and self.risk_level == RiskLevel.BUSINESS_CRITICAL)
```

**Validation Rules**:
- `id` must be unique within a report
- `file_path` must be relative to project root
- `affected_components` must have at least 1 entry
- `diff_lines[0] <= diff_lines[1]`

### 5. TestRequirement

Specifies a test to be generated for an impact.

```python
@dataclass
class TestRequirement:
    id: str                          # Unique identifier (e.g., "TEST-001")
    impact_id: str                   # Reference to parent Impact
    test_type: TestType              # Kind of test to generate
    scenario_type: ScenarioType      # nominal, edge_case, regression, invariant
    description: str                 # What the test should verify
    priority: int                    # 1 = highest priority
    suggested_test_name: str         # e.g., "shouldCalculateTotalWithDiscount"
    target_class: str                # Class under test
    target_method: str | None        # Method under test (if specific)

class ScenarioType(str, Enum):
    NOMINAL = "nominal"              # Happy path (FR-006)
    EDGE_CASE = "edge_case"          # Boundary conditions (FR-006)
    REGRESSION = "regression"         # Bug fix verification (FR-007)
    INVARIANT = "invariant"          # Business rule assertion (FR-008)
```

**Validation Rules**:
- `impact_id` must reference existing Impact
- `priority` must be 1-5
- Each Impact must have at least 1 NOMINAL test requirement

### 6. ImpactReport

Top-level report linking changes to tests.

```python
@dataclass
class ImpactReport:
    version: str = "1.0"
    generated_at: datetime           # ISO 8601 timestamp
    project_path: str                # Absolute path analyzed
    git_ref: str                     # HEAD commit SHA
    total_lines_changed: int         # Lines in diff
    processing_time_seconds: float   # Analysis duration

    # Collections
    impacts: list[Impact]
    test_requirements: list[TestRequirement]

    # Summary (computed)
    @property
    def summary(self) -> dict:
        return {
            "total_impacts": len(self.impacts),
            "business_critical": sum(1 for i in self.impacts
                                    if i.risk_level == RiskLevel.BUSINESS_CRITICAL),
            "non_critical": sum(1 for i in self.impacts
                               if i.risk_level == RiskLevel.NON_CRITICAL),
            "tests_to_generate": len(self.test_requirements),
            "by_test_type": self._count_by_test_type()
        }

    def _count_by_test_type(self) -> dict[str, int]:
        counts = {}
        for req in self.test_requirements:
            counts[req.test_type.value] = counts.get(req.test_type.value, 0) + 1
        return counts
```

**Validation Rules**:
- `impacts` list can be empty (no changes scenario)
- `test_requirements` must reference valid impacts
- `processing_time_seconds` must be positive

### 7. DiffChunk

Internal entity for processing large diffs (FR-011).

```python
@dataclass
class DiffChunk:
    index: int                       # Chunk sequence number
    total_chunks: int                # Total chunks in diff
    files: list[str]                 # File paths in this chunk
    content: str                     # Raw diff content
    line_count: int                  # Lines in chunk

    @property
    def progress_pct(self) -> float:
        return (self.index + 1) / self.total_chunks * 100
```

---

## Relationships

```
ImpactReport
    │
    ├── 1:N ──► Impact
    │              │
    │              └── 1:N ──► TestRequirement
    │
    └── (internal) DiffChunk[]
```

---

## State Transitions

### Impact Analysis Workflow

```
[No Changes] ──► ImpactReport(impacts=[])
                     │
[Has Changes] ──► [Parse Diff]
                     │
                     ▼
               [Chunk if >500 lines]
                     │
                     ▼
               [For each chunk]
                     │
                     ▼
               [Classify Changes] ──► Impact[]
                     │
                     ▼
               [Assess Risk] ──► Impact.risk_level
                     │
                     ▼
               [Map to Test Type] ──► Impact.required_test_type
                     │
                     ▼
               [Generate Requirements] ──► TestRequirement[]
                     │
                     ▼
               [Build Report] ──► ImpactReport
```

---

## Persistence

These entities are **transient** - they exist only during analysis and in the output JSON report. No database persistence is required for the MVP.

Future enhancement: Store reports in PostgreSQL for historical analysis and trend tracking.
