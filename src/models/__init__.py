"""Data models for TestBoost."""

from src.models.impact import (
    ChangeCategory,
    DiffChunk,
    Impact,
    PyramidLevel,
    RiskLevel,
    ScenarioType,
    TestRequirement,
)
from src.models.impact_report import ImpactReport

# Backward compatibility alias
TestKind = PyramidLevel

__all__ = [
    "ChangeCategory",
    "DiffChunk",
    "Impact",
    "ImpactReport",
    "PyramidLevel",
    "RiskLevel",
    "ScenarioType",
    "TestKind",  # Backward compatibility alias
    "TestRequirement",
]
