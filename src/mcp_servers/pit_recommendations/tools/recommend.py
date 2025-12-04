"""
Recommend test improvements tool.

Generates specific, actionable recommendations for improving
test effectiveness based on mutation analysis.
"""

import json
from pathlib import Path


from typing import Any


async def recommend_test_improvements(
    project_path: str,
    mutation_analysis: dict[str, Any] | None = None,
    target_score: float = 80,
    max_recommendations: int = 20,
) -> str:
    """
    Generate test improvement recommendations.

    Args:
        project_path: Path to the Java project root directory
        mutation_analysis: Results from analyze-hard-mutants
        target_score: Target mutation score percentage
        max_recommendations: Maximum number of recommendations

    Returns:
        JSON string with test improvement recommendations
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    # If no analysis provided, run basic analysis
    if not mutation_analysis:
        from .analyze import analyze_hard_mutants

        analysis_result = await analyze_hard_mutants(project_path)
        mutation_analysis = json.loads(analysis_result)

    if not mutation_analysis.get("success"):
        return json.dumps(
            {"success": False, "error": mutation_analysis.get("error", "Analysis failed")}
        )

    # Generate recommendations
    recommendations = _generate_recommendations(
        mutation_analysis, target_score, max_recommendations
    )

    results = {
        "success": True,
        "current_score": mutation_analysis.get("summary", {}).get("mutation_score", 0),
        "target_score": target_score,
        "score_gap": target_score - mutation_analysis.get("summary", {}).get("mutation_score", 0),
        "total_recommendations": len(recommendations),
        "recommendations": recommendations,
        "summary": _generate_summary(recommendations),
    }

    return json.dumps(results, indent=2)


def _generate_recommendations(
    analysis: dict[str, Any], target_score: float, max_recommendations: int
) -> list[dict[str, Any]]:
    """Generate actionable test improvement recommendations."""
    recommendations: list[dict[str, Any]] = []

    summary = analysis.get("summary", {})
    current_score = summary.get("mutation_score", 0)
    survived = summary.get("survived", 0)
    no_coverage = summary.get("no_coverage", 0)

    # Calculate how many mutants need to be killed
    score_gap = target_score - current_score
    if score_gap > 0:
        total = summary.get("total_mutants", 0)
        mutants_to_kill = int((score_gap / 100) * total)

        recommendations.append(
            {
                "id": "score_gap",
                "type": "overview",
                "priority": "high",
                "title": f"Kill {mutants_to_kill} more mutants to reach {target_score}%",
                "description": f"Current score is {current_score}%. Need to kill approximately {mutants_to_kill} more mutants.",
                "effort": "varies",
                "impact": "high",
            }
        )

    # No coverage recommendations (highest priority)
    if no_coverage > 0:
        recommendations.append(
            {
                "id": "no_coverage",
                "type": "coverage",
                "priority": "critical",
                "title": f"Add test coverage for {no_coverage} uncovered mutants",
                "description": "These mutants have no test coverage at all. Adding tests here will have immediate impact.",
                "action": "Write tests for methods that currently have no test coverage",
                "effort": "medium",
                "impact": "high",
                "estimated_improvement": min(no_coverage * 0.5, score_gap / 2),
            }
        )

    # Pattern-based recommendations
    patterns = analysis.get("hard_mutant_patterns", [])
    for pattern in patterns[:5]:
        rec = _pattern_to_recommendation(pattern)
        if rec:
            recommendations.append(rec)

    # Hot spot recommendations
    hot_spots = analysis.get("hot_spots", [])
    for hot_spot in hot_spots[:5]:
        rec = _hot_spot_to_recommendation(hot_spot)
        if rec:
            recommendations.append(rec)

    # Grouped analysis recommendations
    grouped = analysis.get("grouped_analysis", {})
    for group_key, group_data in list(grouped.items())[:10]:
        rec = _group_to_recommendation(group_key, group_data)
        if rec:
            recommendations.append(rec)

    # Deduplicate and limit
    seen_titles = set()
    unique_recs = []
    for rec in recommendations:
        if rec["title"] not in seen_titles:
            seen_titles.add(rec["title"])
            unique_recs.append(rec)

    return unique_recs[:max_recommendations]


def _pattern_to_recommendation(pattern: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a pattern to a recommendation."""
    pattern_type = pattern.get("type")

    if pattern_type == "mutator_concentration":
        mutator = pattern.get("mutator", "")
        count = pattern.get("count", 0)

        return {
            "id": f"pattern_{mutator}",
            "type": "pattern",
            "priority": "high" if count > 10 else "medium",
            "title": f"Address {count} {mutator} mutants",
            "description": pattern.get("description", ""),
            "action": pattern.get("suggested_action", ""),
            "effort": "low" if count < 5 else "medium",
            "impact": "high" if count > 10 else "medium",
            "mutator": mutator,
            "count": count,
        }

    elif pattern_type == "line_cluster":
        return {
            "id": f"cluster_{pattern.get('class')}_{pattern.get('line')}",
            "type": "hot_spot",
            "priority": "high",
            "title": f"Complex line in {pattern.get('class')} at line {pattern.get('line')}",
            "description": pattern.get("description", ""),
            "action": pattern.get("suggested_action", ""),
            "effort": "medium",
            "impact": "medium",
            "class": pattern.get("class"),
            "line": pattern.get("line"),
            "count": pattern.get("count", 0),
        }

    return None


def _hot_spot_to_recommendation(hot_spot: dict[str, Any]) -> dict[str, Any]:
    """Convert a hot spot to a recommendation."""
    class_name = hot_spot.get("class", "")
    method = hot_spot.get("method", "")
    count = hot_spot.get("surviving_count", 0)
    severity = hot_spot.get("severity", "medium")

    return {
        "id": f"hotspot_{class_name}_{method}",
        "type": "hot_spot",
        "priority": "critical" if severity == "high" else "high",
        "title": f"Improve tests for {class_name}.{method} ({count} surviving)",
        "description": f"Method {method} has {count} surviving mutants across lines {hot_spot.get('line_range', '')}",
        "action": f"Add targeted tests for {', '.join(hot_spot.get('mutators', []))} in this method",
        "effort": "medium" if count < 5 else "high",
        "impact": "high",
        "class": class_name,
        "method": method,
        "count": count,
        "mutators": hot_spot.get("mutators", []),
    }


def _group_to_recommendation(group_key: str, group_data: dict[str, Any]) -> dict[str, Any] | None:
    """Convert grouped analysis to a recommendation."""
    count = group_data.get("count", 0)
    if count < 2:
        return None

    # Determine if this is a mutator group or class/method group
    if "affected_classes" in group_data:
        # Mutator group
        return {
            "id": f"mutator_{group_key}",
            "type": "mutator_specific",
            "priority": "high" if count > 5 else "medium",
            "title": f"Target {group_key} mutants ({count} surviving)",
            "description": f"Affects classes: {', '.join(group_data.get('affected_classes', [])[:5])}",
            "action": _get_mutator_action(group_key),
            "effort": "low" if count < 5 else "medium",
            "impact": "medium",
            "mutator": group_key,
            "count": count,
        }
    elif "methods" in group_data:
        # Class group
        methods = group_data.get("methods", [])
        return {
            "id": f"class_{group_key}",
            "type": "class_specific",
            "priority": "high" if count > 10 else "medium",
            "title": f"Improve test coverage for {group_key}",
            "description": f"{count} surviving mutants across {len(methods)} methods",
            "action": f"Focus on methods: {', '.join(methods[:3])}{'...' if len(methods) > 3 else ''}",
            "effort": "high" if count > 10 else "medium",
            "impact": "high",
            "class": group_key,
            "count": count,
            "methods": methods,
        }

    return None


def _get_mutator_action(mutator: str) -> str:
    """Get detailed action for a mutator type."""
    actions = {
        "ConditionalsBoundaryMutator": (
            "Add tests with boundary values. For comparisons like x <= 5, "
            "test with x = 4, 5, and 6 to catch boundary mutations."
        ),
        "NegateConditionalsMutator": (
            "Ensure both true and false branches are tested. "
            "Add tests that verify behavior when conditions are true AND when false."
        ),
        "MathMutator": (
            "Add assertions that verify exact calculation results. "
            "Test with values where +1 vs -1 or * vs / produces different results."
        ),
        "IncrementsMutator": (
            "Test increment/decrement operations with exact value assertions. "
            "Verify counter values, array indices, and loop iterations precisely."
        ),
        "ReturnValuesMutator": (
            "Assert specific return values, not just non-null. "
            "Verify the actual content of returned objects."
        ),
        "VoidMethodCallMutator": (
            "Verify side effects of void method calls. "
            "Use verify() to ensure methods are called, check state changes."
        ),
        "EmptyReturnValuesMutator": (
            "Test that collections/arrays/strings are not empty when expected. "
            "Use assertThat(result).isNotEmpty() or verify list size."
        ),
    }

    return actions.get(
        mutator,
        f"Add targeted tests to detect {mutator} mutations. "
        "Focus on verifying exact behavior that would change when mutated.",
    )


def _generate_summary(recommendations: list[dict[str, Any]]) -> dict[str, Any]:
    """Generate a summary of recommendations."""
    by_priority: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    by_type: dict[str, int] = {}
    total_effort = 0
    effort_map = {"low": 1, "medium": 2, "high": 3}

    for rec in recommendations:
        priority = rec.get("priority", "medium")
        rec_type = rec.get("type", "other")
        effort = rec.get("effort", "medium")

        by_priority[priority] = by_priority.get(priority, 0) + 1
        by_type[rec_type] = by_type.get(rec_type, 0) + 1
        total_effort += effort_map.get(effort, 2)

    return {
        "by_priority": by_priority,
        "by_type": by_type,
        "estimated_total_effort": (
            "low"
            if total_effort < len(recommendations) * 1.5
            else "high" if total_effort > len(recommendations) * 2.5 else "medium"
        ),
        "quick_wins": len([r for r in recommendations if r.get("effort") == "low"]),
        "high_impact": len([r for r in recommendations if r.get("impact") == "high"]),
    }
