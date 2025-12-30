"""Impact analysis data models (T002-T005).

Defines the core entities for representing code change impacts,
risk classification, and test requirements.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChangeCategory(str, Enum):
    """Classification of code change types per FR-002."""

    BUSINESS_RULE = "business_rule"  # Service logic, domain rules
    ENDPOINT = "endpoint"  # Controllers, REST resources
    DTO = "dto"  # Data transfer objects, entities
    QUERY = "query"  # Repository methods, JPA queries
    MIGRATION = "migration"  # Database migrations, SQL scripts
    API_CONTRACT = "api_contract"  # External API clients, contracts
    CONFIGURATION = "configuration"  # Application config, Spring beans
    TEST = "test"  # Test file modifications
    OTHER = "other"  # Unclassified changes


class RiskLevel(str, Enum):
    """Risk classification per FR-004."""

    BUSINESS_CRITICAL = "business_critical"  # Payment, auth, security
    NON_CRITICAL = "non_critical"  # Logging, formatting, docs


class TestType(str, Enum):
    """Test level selection per FR-005 (test pyramid)."""

    UNIT = "unit"  # JUnit, pure logic
    CONTROLLER = "controller"  # @WebMvcTest, MockMvc
    DATA_LAYER = "data_layer"  # @DataJpaTest
    INTEGRATION = "integration"  # @SpringBootTest
    CONTRACT = "contract"  # Pact, Spring Cloud Contract


class ScenarioType(str, Enum):
    """Test scenario classification per FR-006/007/008."""

    NOMINAL = "nominal"  # Happy path (FR-006)
    EDGE_CASE = "edge_case"  # Boundary conditions (FR-006)
    REGRESSION = "regression"  # Bug fix verification (FR-007)
    INVARIANT = "invariant"  # Business rule assertion (FR-008)


@dataclass
class Impact:
    """Represents a single code change and its effects.

    Attributes:
        id: Unique identifier (e.g., "IMP-001")
        file_path: Relative path to changed file
        category: Type of change
        risk_level: Business criticality
        affected_components: Classes/methods affected
        required_test_type: Recommended test level
        change_summary: Human-readable description
        diff_lines: Start/end lines in diff (start, end)
        is_bug_fix: Detected from commit message/keywords
    """

    id: str
    file_path: str
    category: ChangeCategory
    risk_level: RiskLevel
    affected_components: list[str]
    required_test_type: TestType
    change_summary: str
    diff_lines: tuple[int, int] = (0, 0)
    is_bug_fix: bool = False
    diff_content: str = ""  # Raw diff for business rule extraction
    extracted_rules: list[str] = field(default_factory=list)  # Detected business rules

    @property
    def requires_regression_test(self) -> bool:
        """Check if this impact requires a regression test (FR-007)."""
        return self.is_bug_fix

    @property
    def requires_invariant_test(self) -> bool:
        """Check if this impact requires an invariant test (FR-008)."""
        return (
            self.category == ChangeCategory.BUSINESS_RULE
            and self.risk_level == RiskLevel.BUSINESS_CRITICAL
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "category": self.category.value,
            "risk_level": self.risk_level.value,
            "affected_components": self.affected_components,
            "required_test_type": self.required_test_type.value,
            "change_summary": self.change_summary,
            "diff_lines": list(self.diff_lines),
            "is_bug_fix": self.is_bug_fix,
        }


@dataclass
class TestRequirement:
    """Specifies a test to be generated for an impact.

    Attributes:
        id: Unique identifier (e.g., "TEST-001")
        impact_id: Reference to parent Impact
        test_type: Kind of test to generate
        scenario_type: nominal, edge_case, regression, invariant
        description: What the test should verify
        priority: 1 = highest priority
        suggested_test_name: e.g., "shouldCalculateTotalWithDiscount"
        target_class: Class under test
        target_method: Method under test (if specific)
    """

    id: str
    impact_id: str
    test_type: TestType
    scenario_type: ScenarioType
    description: str
    priority: int
    target_class: str
    suggested_test_name: str = ""
    target_method: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: dict[str, Any] = {
            "id": self.id,
            "impact_id": self.impact_id,
            "test_type": self.test_type.value,
            "scenario_type": self.scenario_type.value,
            "description": self.description,
            "priority": self.priority,
            "target_class": self.target_class,
        }
        if self.suggested_test_name:
            result["suggested_test_name"] = self.suggested_test_name
        if self.target_method:
            result["target_method"] = self.target_method
        return result


@dataclass
class DiffChunk:
    """Internal entity for processing large diffs (FR-011).

    Attributes:
        index: Chunk sequence number (0-based)
        total_chunks: Total chunks in diff
        files: File paths in this chunk
        content: Raw diff content
        line_count: Lines in chunk
    """

    index: int
    total_chunks: int
    files: list[str]
    content: str
    line_count: int

    @property
    def progress_pct(self) -> float:
        """Calculate progress percentage."""
        if self.total_chunks == 0:
            return 100.0
        return (self.index + 1) / self.total_chunks * 100
