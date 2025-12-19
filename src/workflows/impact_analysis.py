"""Impact Analysis Workflow (T011-T016, T017-T022, T033-T038).

Analyzes git diff to identify code changes, classify risk levels,
and generate test requirements per FR-001 through FR-008.
"""

import asyncio
import functools
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, TypeVar

import jsonschema
from jsonschema import ValidationError, validate

from src.lib.diff_chunker import chunk_diff, count_lines, is_large_diff, split_by_file
from src.lib.llm import LLMError, get_llm
from src.lib.logging import get_logger
from src.lib.risk_keywords import (
    contains_critical_keyword,
    is_critical_path,
    is_non_critical_path,
    score_risk_from_keywords,
)
from src.models.impact import (
    ChangeCategory,
    DiffChunk,
    Impact,
    RiskLevel,
    ScenarioType,
    TestRequirement,
    TestType,
)
from src.models.impact_report import ImpactReport

logger = get_logger(__name__)

# Type variable for retry decorator
T = TypeVar("T")


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 30.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """
    Reusable retry decorator with exponential backoff (T033, FR-012).

    Use this decorator for any operation that may fail transiently,
    especially LLM API calls.

    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds (default: 2.0)
        max_delay: Maximum delay between retries (default: 30.0)
        exceptions: Tuple of exception types to catch

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=3)
        async def call_llm(prompt: str) -> str:
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                        )
                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            max_attempts=max_attempts,
                            error=str(e),
                        )
            raise last_exception  # type: ignore

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            "retry_attempt",
                            function=func.__name__,
                            attempt=attempt + 1,
                            max_attempts=max_attempts,
                            delay=delay,
                            error=str(e),
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "retry_exhausted",
                            function=func.__name__,
                            max_attempts=max_attempts,
                            error=str(e),
                        )
            raise last_exception  # type: ignore

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore

    return decorator


# File path patterns for categorization (FR-002)
CATEGORY_PATTERNS: dict[ChangeCategory, list[str]] = {
    ChangeCategory.ENDPOINT: [
        r".*Controller\.java$",
        r".*Resource\.java$",
        r".*Endpoint\.java$",
        r".*/rest/.*\.java$",
        r".*/controller/.*\.java$",
        r".*/api/.*\.java$",
    ],
    ChangeCategory.BUSINESS_RULE: [
        r".*Service\.java$",
        r".*ServiceImpl\.java$",
        r".*/service/.*\.java$",
        r".*/domain/.*\.java$",
        r".*/business/.*\.java$",
    ],
    ChangeCategory.QUERY: [
        r".*Repository\.java$",
        r".*Dao\.java$",
        r".*Mapper\.java$",
        r".*/repository/.*\.java$",
        r".*/dao/.*\.java$",
    ],
    ChangeCategory.DTO: [
        r".*Entity\.java$",
        r".*Model\.java$",
        r".*Dto\.java$",
        r".*Request\.java$",
        r".*Response\.java$",
        r".*/entity/.*\.java$",
        r".*/model/.*\.java$",
        r".*/dto/.*\.java$",
    ],
    ChangeCategory.MIGRATION: [
        r".*/migration/.*",
        r".*/migrations/.*",
        r".*/db/.*\.sql$",
        r".*\.sql$",
        r".*/flyway/.*",
        r".*/liquibase/.*",
    ],
    ChangeCategory.API_CONTRACT: [
        r".*Client\.java$",
        r".*FeignClient\.java$",
        r".*/client/.*\.java$",
        r".*/integration/.*\.java$",
        r".*\.proto$",
        r".*openapi.*\.yaml$",
        r".*swagger.*\.yaml$",
    ],
    ChangeCategory.CONFIGURATION: [
        r"application.*\.yml$",
        r"application.*\.yaml$",
        r"application.*\.properties$",
        r".*Config\.java$",
        r".*Configuration\.java$",
        r".*/config/.*\.java$",
        r"pom\.xml$",
        r"build\.gradle$",
    ],
    ChangeCategory.TEST: [
        r".*Test\.java$",
        r".*Tests\.java$",
        r".*IT\.java$",
        r".*Spec\.java$",
        r".*/test/.*\.java$",
        r".*/tests/.*\.java$",
    ],
}

# Test type mapping per change category (FR-005 - test pyramid)
TEST_TYPE_MAPPING: dict[ChangeCategory, TestType] = {
    ChangeCategory.BUSINESS_RULE: TestType.UNIT,
    ChangeCategory.ENDPOINT: TestType.CONTROLLER,
    ChangeCategory.DTO: TestType.UNIT,
    ChangeCategory.QUERY: TestType.DATA_LAYER,
    ChangeCategory.MIGRATION: TestType.INTEGRATION,
    ChangeCategory.API_CONTRACT: TestType.CONTRACT,
    ChangeCategory.CONFIGURATION: TestType.INTEGRATION,
    ChangeCategory.TEST: TestType.UNIT,  # Test file changes
    ChangeCategory.OTHER: TestType.UNIT,
}

# Regex patterns for extracting class/method names from Java diffs
CLASS_PATTERN = re.compile(r"(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)")
METHOD_PATTERN = re.compile(
    r"(?:public|private|protected)\s+(?:static\s+)?(?:\w+(?:<[^>]+>)?)\s+(\w+)\s*\("
)

# Bug fix indicators
BUG_FIX_KEYWORDS = {"fix", "bug", "issue", "patch", "hotfix", "resolve", "correct"}

# JSON Schema for ImpactReport validation (T035, FR-009)
IMPACT_REPORT_SCHEMA: dict[str, Any] = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "required": ["project_path", "git_ref", "timestamp", "impacts", "test_requirements", "summary"],
    "properties": {
        "project_path": {"type": "string"},
        "git_ref": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"},
        "impacts": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "file_path", "category", "risk_level", "required_test_type"],
                "properties": {
                    "id": {"type": "string", "pattern": "^IMP-\\d{3}$"},
                    "file_path": {"type": "string"},
                    "category": {
                        "type": "string",
                        "enum": [
                            "business_rule",
                            "endpoint",
                            "dto",
                            "query",
                            "migration",
                            "api_contract",
                            "configuration",
                            "test",
                            "other",
                        ],
                    },
                    "risk_level": {
                        "type": "string",
                        "enum": ["business_critical", "non_critical"],
                    },
                    "affected_components": {"type": "array", "items": {"type": "string"}},
                    "required_test_type": {
                        "type": "string",
                        "enum": ["unit", "controller", "data_layer", "integration", "contract"],
                    },
                    "change_summary": {"type": "string"},
                    "diff_lines": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                    },
                    "is_bug_fix": {"type": "boolean"},
                },
            },
        },
        "test_requirements": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "impact_id", "test_type", "scenario_type", "priority"],
                "properties": {
                    "id": {"type": "string", "pattern": "^TEST-\\d{3}$"},
                    "impact_id": {"type": "string", "pattern": "^IMP-\\d{3}$"},
                    "test_type": {
                        "type": "string",
                        "enum": ["unit", "controller", "data_layer", "integration", "contract"],
                    },
                    "scenario_type": {
                        "type": "string",
                        "enum": ["nominal", "edge_case", "regression", "invariant"],
                    },
                    "description": {"type": "string"},
                    "priority": {"type": "integer", "minimum": 1, "maximum": 5},
                    "target_class": {"type": "string"},
                    "suggested_test_name": {"type": "string"},
                },
            },
        },
        "summary": {
            "type": "object",
            "required": [
                "total_impacts",
                "business_critical",
                "tests_to_generate",
                "total_lines_changed",
            ],
            "properties": {
                "total_impacts": {"type": "integer", "minimum": 0},
                "business_critical": {"type": "integer", "minimum": 0},
                "non_critical": {"type": "integer", "minimum": 0},
                "tests_to_generate": {"type": "integer", "minimum": 0},
                "total_lines_changed": {"type": "integer", "minimum": 0},
                "processing_time_seconds": {"type": "number", "minimum": 0},
            },
        },
    },
}


def validate_impact_report(report_dict: dict[str, Any]) -> tuple[bool, str | None]:
    """
    Validate an ImpactReport dict against the JSON schema (T035).

    Args:
        report_dict: The report dictionary to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    try:
        validate(instance=report_dict, schema=IMPACT_REPORT_SCHEMA)
        return True, None
    except ValidationError as e:
        error_path = " -> ".join(str(p) for p in e.absolute_path) if e.absolute_path else "root"
        error_msg = f"Schema validation failed at {error_path}: {e.message}"
        logger.warning("impact_report_validation_failed", error=error_msg)
        return False, error_msg
    except jsonschema.SchemaError as e:
        error_msg = f"Invalid schema: {e.message}"
        logger.error("impact_report_schema_error", error=error_msg)
        return False, error_msg


def parse_diff(diff_content: str) -> list[tuple[str, str, int, int]]:
    """
    Parse a unified diff to extract file-level changes (T012).

    Args:
        diff_content: Raw unified diff content

    Returns:
        List of (file_path, file_diff, start_line, end_line) tuples
    """
    if not diff_content.strip():
        return []

    file_diffs = split_by_file(diff_content)
    results: list[tuple[str, str, int, int]] = []
    current_line = 0

    for file_path, file_diff in file_diffs:
        line_count = count_lines(file_diff)
        results.append((file_path, file_diff, current_line, current_line + line_count))
        current_line += line_count

    return results


def categorize_change(file_path: str) -> ChangeCategory:
    """
    Map a file path to its ChangeCategory (T013, FR-002).

    Args:
        file_path: Relative file path

    Returns:
        The appropriate ChangeCategory
    """
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.match(pattern, file_path, re.IGNORECASE):
                return category

    return ChangeCategory.OTHER


def select_test_type(category: ChangeCategory) -> TestType:
    """
    Select the appropriate test type for a change category (T018, FR-005).

    Follows the test pyramid principle - lowest viable test level.

    Args:
        category: The change category

    Returns:
        The recommended TestType
    """
    return TEST_TYPE_MAPPING.get(category, TestType.UNIT)


def identify_affected_components(
    file_path: str,
    diff_content: str,
) -> list[str]:
    """
    Extract class/method names and break points from diff (T014, FR-003).

    Identifies:
    - Class names
    - Method names
    - Input parameters
    - Return types
    - Persistence operations

    Args:
        file_path: Path to the changed file
        diff_content: Diff content for this file

    Returns:
        List of affected component identifiers
    """
    components: list[str] = []

    # Extract base class name from file path
    if file_path.endswith(".java"):
        base_name = Path(file_path).stem
        components.append(base_name)

    # Find class declarations in diff
    for match in CLASS_PATTERN.finditer(diff_content):
        class_name = match.group(1)
        if class_name not in components:
            components.append(class_name)

    # Find method declarations in diff (focus on changed methods)
    # Only look at added/modified lines (starting with +)
    changed_lines = [line for line in diff_content.splitlines() if line.startswith("+")]
    changed_content = "\n".join(changed_lines)

    for match in METHOD_PATTERN.finditer(changed_content):
        method_name = match.group(1)
        if method_name not in components:
            components.append(method_name)

    # If no components found, use filename
    if not components:
        components.append(Path(file_path).name)

    return components


def classify_risk(
    file_path: str,
    diff_content: str,
    category: ChangeCategory,
) -> RiskLevel:
    """
    Classify the risk level of a change (T020, FR-004).

    Uses keyword-based scoring with path analysis.

    Args:
        file_path: Path to the changed file
        diff_content: Diff content for this file
        category: The change category

    Returns:
        RiskLevel classification
    """
    # Test files are always non-critical
    if category == ChangeCategory.TEST:
        return RiskLevel.NON_CRITICAL

    # Check path patterns first
    if is_critical_path(file_path):
        return RiskLevel.BUSINESS_CRITICAL

    if is_non_critical_path(file_path):
        return RiskLevel.NON_CRITICAL

    # Score based on content keywords
    critical_score, non_critical_score = score_risk_from_keywords(diff_content)

    # Also check the file path
    path_critical, path_non_critical = score_risk_from_keywords(file_path)
    critical_score += path_critical * 2  # Path matches count more
    non_critical_score += path_non_critical

    # Business rules and API contracts are inherently higher risk
    if category in {ChangeCategory.BUSINESS_RULE, ChangeCategory.API_CONTRACT}:
        critical_score += 2

    # Determine risk based on scores
    if critical_score > non_critical_score:
        return RiskLevel.BUSINESS_CRITICAL
    elif non_critical_score > 0:
        return RiskLevel.NON_CRITICAL
    else:
        # Ambiguous case - use default based on category
        # LLM fallback can be used via classify_risk_with_llm for more accuracy
        if category in {
            ChangeCategory.CONFIGURATION,
            ChangeCategory.MIGRATION,
            ChangeCategory.ENDPOINT,
        }:
            return RiskLevel.BUSINESS_CRITICAL
        return RiskLevel.NON_CRITICAL


@retry_with_backoff(max_attempts=3, exceptions=(LLMError, Exception))
async def classify_risk_with_llm(
    file_path: str,
    diff_content: str,
    category: ChangeCategory,
) -> RiskLevel:
    """
    Classify risk using LLM for ambiguous cases (T021, FR-004, FR-012).

    This function provides more accurate risk classification when
    keyword-based scoring is ambiguous. Uses retry with exponential
    backoff per FR-012.

    Args:
        file_path: Path to the changed file
        diff_content: Diff content for this file
        category: The change category

    Returns:
        RiskLevel classification from LLM analysis

    Raises:
        LLMError: If LLM call fails after retries
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    # First try keyword-based classification
    keyword_result = classify_risk(file_path, diff_content, category)

    # Check if classification is ambiguous (no strong signals)
    critical_score, non_critical_score = score_risk_from_keywords(diff_content)
    path_critical, path_non_critical = score_risk_from_keywords(file_path)

    # If we have clear signals, use keyword result
    total_critical = critical_score + path_critical * 2
    total_non_critical = non_critical_score + path_non_critical

    if abs(total_critical - total_non_critical) > 2:
        # Clear signal, no need for LLM
        return keyword_result

    # Ambiguous case - use LLM
    logger.info(
        "classify_risk_llm_fallback",
        file_path=file_path,
        category=category.value,
        critical_score=total_critical,
        non_critical_score=total_non_critical,
    )

    try:
        llm = get_llm(temperature=0.0, max_tokens=100)

        system_prompt = """You are a code risk classifier. Analyze the code change and classify its risk level.

Business-critical code includes:
- Payment/billing/financial logic
- Authentication/authorization
- Security-sensitive operations
- User data handling (PII, GDPR)
- Core business rules that affect revenue

Non-critical code includes:
- Logging and debugging
- Formatting and display
- Documentation
- Test utilities
- Internal tooling

Respond with ONLY one word: "CRITICAL" or "NON_CRITICAL"."""

        user_prompt = f"""File: {file_path}
Category: {category.value}

Diff content (first 1000 chars):
{diff_content[:1000]}

Is this change business-critical or non-critical?"""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        response = await llm.ainvoke(messages)
        result = response.content.strip().upper()

        if "CRITICAL" in result and "NON" not in result:
            return RiskLevel.BUSINESS_CRITICAL
        else:
            return RiskLevel.NON_CRITICAL

    except Exception as e:
        logger.warning(
            "classify_risk_llm_failed",
            file_path=file_path,
            error=str(e),
        )
        # Fall back to keyword result
        return keyword_result


def detect_bug_fix(diff_content: str, file_path: str) -> bool:
    """
    Detect if a change is a bug fix (for FR-007 regression tests).

    Args:
        diff_content: Diff content
        file_path: File path

    Returns:
        True if this appears to be a bug fix
    """
    # Check for bug fix indicators in the diff content
    content_lower = diff_content.lower()
    for keyword in BUG_FIX_KEYWORDS:
        if keyword in content_lower:
            return True
    return False


def generate_change_summary(
    file_path: str,
    components: list[str],
    category: ChangeCategory,
) -> str:
    """
    Generate a human-readable summary of the change.

    Args:
        file_path: Path to changed file
        components: Affected components
        category: Change category

    Returns:
        Summary string
    """
    base_name = Path(file_path).name
    component_str = ", ".join(components[:3])
    if len(components) > 3:
        component_str += f" (+{len(components) - 3} more)"

    return f"Modified {category.value} in {base_name}: {component_str}"


def analyze_impacts(
    diff_content: str,
    project_path: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Impact]:
    """
    Main entry point for impact analysis (T015, FR-001).

    Orchestrates parsing, categorization, and risk classification.
    Handles empty diff case by returning empty list.

    Args:
        diff_content: Raw git diff content
        project_path: Path to the project
        progress_callback: Optional callback(current, total, message)

    Returns:
        List of identified Impacts
    """
    # Handle empty diff case (US1 scenario 4)
    if not diff_content.strip():
        return []

    # Check if chunking is needed (T016, FR-011)
    if is_large_diff(diff_content):
        return _analyze_with_chunks(diff_content, project_path, progress_callback)

    return _analyze_single(diff_content, project_path, progress_callback)


def _analyze_single(
    diff_content: str,
    project_path: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Impact]:
    """Analyze a single diff without chunking."""
    file_changes = parse_diff(diff_content)
    impacts: list[Impact] = []
    impact_counter = 1

    total_files = len(file_changes)

    for idx, (file_path, file_diff, start_line, end_line) in enumerate(file_changes):
        if progress_callback:
            progress_callback(idx + 1, total_files, f"Analyzing {Path(file_path).name}")

        # Skip test files from impact analysis (they don't need tests)
        category = categorize_change(file_path)
        if category == ChangeCategory.TEST:
            continue

        # Extract components
        components = identify_affected_components(file_path, file_diff)

        # Classify risk
        risk_level = classify_risk(file_path, file_diff, category)

        # Select test type
        test_type = select_test_type(category)

        # Detect bug fix
        is_bug_fix = detect_bug_fix(file_diff, file_path)

        # Generate summary
        summary = generate_change_summary(file_path, components, category)

        impact = Impact(
            id=f"IMP-{impact_counter:03d}",
            file_path=file_path,
            category=category,
            risk_level=risk_level,
            affected_components=components,
            required_test_type=test_type,
            change_summary=summary,
            diff_lines=(start_line, end_line),
            is_bug_fix=is_bug_fix,
        )

        impacts.append(impact)
        impact_counter += 1

    return impacts


def _analyze_with_chunks(
    diff_content: str,
    project_path: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> list[Impact]:
    """Analyze a large diff using chunks (T016, FR-011)."""
    chunks = chunk_diff(diff_content, max_lines=500)
    all_impacts: list[Impact] = []
    impact_counter = 1

    for chunk in chunks:
        if progress_callback:
            progress_callback(
                chunk.index + 1,
                chunk.total_chunks,
                f"Processing chunk {chunk.index + 1}/{chunk.total_chunks}",
            )

        chunk_impacts = _analyze_single(chunk.content, project_path)

        # Renumber impacts to be globally unique
        for impact in chunk_impacts:
            impact = Impact(
                id=f"IMP-{impact_counter:03d}",
                file_path=impact.file_path,
                category=impact.category,
                risk_level=impact.risk_level,
                affected_components=impact.affected_components,
                required_test_type=impact.required_test_type,
                change_summary=impact.change_summary,
                diff_lines=impact.diff_lines,
                is_bug_fix=impact.is_bug_fix,
            )
            all_impacts.append(impact)
            impact_counter += 1

    return all_impacts


def generate_test_requirements(impacts: list[Impact]) -> list[TestRequirement]:
    """
    Generate test requirements for impacts (T023-T027, FR-006/007/008).

    Creates:
    - 1 nominal test per impact (FR-006)
    - 1-2 edge case tests per impact (FR-006)
    - Regression tests for bug fixes (FR-007)
    - Invariant tests for critical business rules (FR-008)

    Args:
        impacts: List of identified impacts

    Returns:
        List of TestRequirement objects
    """
    requirements: list[TestRequirement] = []
    req_counter = 1

    for impact in impacts:
        # Skip test file changes
        if impact.category == ChangeCategory.TEST:
            continue

        # Determine priority based on risk
        base_priority = 1 if impact.risk_level == RiskLevel.BUSINESS_CRITICAL else 3

        # T024: Nominal case (always 1)
        requirements.append(
            TestRequirement(
                id=f"TEST-{req_counter:03d}",
                impact_id=impact.id,
                test_type=impact.required_test_type,
                scenario_type=ScenarioType.NOMINAL,
                description=f"Verify nominal behavior of {impact.affected_components[0]}",
                priority=base_priority,
                target_class=impact.affected_components[0],
                suggested_test_name=f"should{impact.affected_components[0]}WorkCorrectly",
            )
        )
        req_counter += 1

        # T025: Edge cases (1-2 per impact)
        edge_cases = _generate_edge_cases(impact)
        for edge_desc, edge_name in edge_cases:
            requirements.append(
                TestRequirement(
                    id=f"TEST-{req_counter:03d}",
                    impact_id=impact.id,
                    test_type=impact.required_test_type,
                    scenario_type=ScenarioType.EDGE_CASE,
                    description=edge_desc,
                    priority=base_priority + 1,
                    target_class=impact.affected_components[0],
                    suggested_test_name=edge_name,
                )
            )
            req_counter += 1

        # T026: Regression test for bug fixes
        if impact.requires_regression_test:
            requirements.append(
                TestRequirement(
                    id=f"TEST-{req_counter:03d}",
                    impact_id=impact.id,
                    test_type=impact.required_test_type,
                    scenario_type=ScenarioType.REGRESSION,
                    description=f"Regression test to prevent bug from recurring in {impact.affected_components[0]}",
                    priority=1,  # Regression tests are high priority
                    target_class=impact.affected_components[0],
                    suggested_test_name=f"shouldNotRegress{impact.affected_components[0]}",
                )
            )
            req_counter += 1

        # T027: Invariant test for critical business rules
        if impact.requires_invariant_test:
            requirements.append(
                TestRequirement(
                    id=f"TEST-{req_counter:03d}",
                    impact_id=impact.id,
                    test_type=impact.required_test_type,
                    scenario_type=ScenarioType.INVARIANT,
                    description=f"Verify business rule invariant in {impact.affected_components[0]}",
                    priority=1,  # Invariant tests are high priority
                    target_class=impact.affected_components[0],
                    suggested_test_name=f"shouldMaintainInvariant{impact.affected_components[0]}",
                )
            )
            req_counter += 1

    return requirements


def _generate_edge_cases(impact: Impact) -> list[tuple[str, str]]:
    """Generate edge case descriptions based on impact category."""
    component = impact.affected_components[0]
    edge_cases: list[tuple[str, str]] = []

    if impact.category == ChangeCategory.ENDPOINT:
        edge_cases.append(
            (f"Verify {component} handles invalid input", f"shouldRejectInvalidInput{component}")
        )
        edge_cases.append(
            (
                f"Verify {component} handles missing authorization",
                f"shouldRejectUnauthorized{component}",
            )
        )
    elif impact.category == ChangeCategory.BUSINESS_RULE:
        edge_cases.append(
            (f"Verify {component} handles null values", f"shouldHandleNull{component}")
        )
        edge_cases.append(
            (f"Verify {component} handles boundary values", f"shouldHandleBoundary{component}")
        )
    elif impact.category == ChangeCategory.QUERY:
        edge_cases.append(
            (f"Verify {component} handles empty result", f"shouldHandleEmptyResult{component}")
        )
    elif impact.category == ChangeCategory.DTO:
        edge_cases.append(
            (f"Verify {component} validation rules", f"shouldValidate{component}")
        )
    else:
        edge_cases.append(
            (f"Verify {component} handles edge conditions", f"shouldHandleEdgeCase{component}")
        )

    return edge_cases[:2]  # Max 2 edge cases per impact


def build_impact_report(
    project_path: str,
    git_ref: str,
    impacts: list[Impact],
    test_requirements: list[TestRequirement],
    total_lines: int,
    processing_time: float,
) -> ImpactReport:
    """
    Assemble the final ImpactReport (T028, FR-009).

    Args:
        project_path: Absolute path to project
        git_ref: HEAD commit SHA
        impacts: List of impacts
        test_requirements: List of test requirements
        total_lines: Total lines in diff
        processing_time: Analysis duration in seconds

    Returns:
        Complete ImpactReport
    """
    return ImpactReport(
        project_path=project_path,
        git_ref=git_ref,
        impacts=impacts,
        test_requirements=test_requirements,
        total_lines_changed=total_lines,
        processing_time_seconds=processing_time,
    )


async def run_impact_analysis(
    project_path: str,
    progress_callback: Callable[[int, int, str], None] | None = None,
) -> ImpactReport:
    """
    Run full impact analysis workflow.

    Integrates with git diff tool to analyze uncommitted changes.

    Args:
        project_path: Path to the project
        progress_callback: Optional progress callback

    Returns:
        Complete ImpactReport
    """
    from src.mcp_servers.git_maintenance.tools.diff import get_uncommitted_diff

    start_time = time.time()

    # Get diff
    diff_result_json = await get_uncommitted_diff(project_path)
    diff_result = json.loads(diff_result_json)

    if not diff_result.get("success"):
        return ImpactReport(
            project_path=project_path,
            git_ref="",
            impacts=[],
            test_requirements=[],
        )

    diff_content = diff_result.get("diff", "")
    git_ref = diff_result.get("head_sha", "")
    total_lines = diff_result.get("total_lines", 0)

    # Analyze impacts
    impacts = analyze_impacts(diff_content, project_path, progress_callback)

    # Generate test requirements
    test_requirements = generate_test_requirements(impacts)

    processing_time = time.time() - start_time

    return build_impact_report(
        project_path=str(Path(project_path).absolute()),
        git_ref=git_ref,
        impacts=impacts,
        test_requirements=test_requirements,
        total_lines=total_lines,
        processing_time=processing_time,
    )
