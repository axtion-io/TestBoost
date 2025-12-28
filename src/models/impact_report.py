"""ImpactReport model (T006).

Top-level report linking code changes to required tests.
Produces JSON output per FR-009.
"""

from dataclasses import dataclass, field
from datetime import datetime

from src.models.impact import Impact, RiskLevel, TestRequirement


@dataclass
class ImpactReport:
    """Top-level report linking changes to tests.

    Attributes:
        version: Schema version (always "1.0")
        generated_at: ISO 8601 timestamp
        project_path: Absolute path analyzed
        git_ref: HEAD commit SHA
        total_lines_changed: Lines in diff
        processing_time_seconds: Analysis duration
        impacts: List of identified impacts
        test_requirements: List of tests to generate
    """

    project_path: str
    git_ref: str
    impacts: list[Impact] = field(default_factory=list)
    test_requirements: list[TestRequirement] = field(default_factory=list)
    version: str = "1.0"
    generated_at: datetime = field(default_factory=datetime.utcnow)
    total_lines_changed: int = 0
    processing_time_seconds: float = 0.0

    @property
    def summary(self) -> dict:
        """Compute summary statistics."""
        by_test_type: dict[str, int] = {}
        for req in self.test_requirements:
            type_value = req.test_type.value
            by_test_type[type_value] = by_test_type.get(type_value, 0) + 1

        return {
            "total_impacts": len(self.impacts),
            "business_critical": sum(
                1 for i in self.impacts if i.risk_level == RiskLevel.BUSINESS_CRITICAL
            ),
            "non_critical": sum(
                1 for i in self.impacts if i.risk_level == RiskLevel.NON_CRITICAL
            ),
            "tests_to_generate": len(self.test_requirements),
            "by_test_type": by_test_type,
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization (FR-009)."""
        return {
            "version": self.version,
            "generated_at": self.generated_at.isoformat() + "Z",
            "project_path": self.project_path,
            "git_ref": self.git_ref,
            "total_lines_changed": self.total_lines_changed,
            "processing_time_seconds": round(self.processing_time_seconds, 2),
            "summary": self.summary,
            "impacts": [impact.to_dict() for impact in self.impacts],
            "test_requirements": [req.to_dict() for req in self.test_requirements],
        }

    def has_uncovered_critical_impacts(self) -> bool:
        """Check if any business-critical impacts lack tests.

        Used for CI exit code logic (T032).
        """
        critical_impact_ids = {
            i.id for i in self.impacts if i.risk_level == RiskLevel.BUSINESS_CRITICAL
        }
        covered_impact_ids = {req.impact_id for req in self.test_requirements}
        return bool(critical_impact_ids - covered_impact_ids)
