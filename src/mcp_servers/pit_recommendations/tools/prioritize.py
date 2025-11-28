"""
Prioritize test efforts tool.

Prioritizes test improvement efforts based on impact, effort,
and selected strategy.
"""

import json
from pathlib import Path


async def prioritize_test_efforts(
    project_path: str, recommendations: list[dict] | None = None, strategy: str = "balanced"
) -> str:
    """
    Prioritize test improvement efforts.

    Args:
        project_path: Path to the Java project root directory
        recommendations: List of test improvement recommendations
        strategy: Prioritization strategy (quick_wins, high_impact, balanced)

    Returns:
        JSON string with prioritized test efforts
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    if not recommendations:
        # Run recommendation generation
        from .recommend import recommend_test_improvements

        rec_result = await recommend_test_improvements(project_path)
        rec_data = json.loads(rec_result)

        if not rec_data.get("success"):
            return json.dumps(
                {
                    "success": False,
                    "error": rec_data.get("error", "Failed to generate recommendations"),
                }
            )

        recommendations = rec_data.get("recommendations", [])

    if not recommendations:
        return json.dumps(
            {"success": True, "message": "No recommendations to prioritize", "prioritized": []}
        )

    # Score and prioritize recommendations
    scored = _score_recommendations(recommendations, strategy)

    # Group into action phases
    phases = _create_action_phases(scored)

    results = {
        "success": True,
        "strategy": strategy,
        "strategy_description": _get_strategy_description(strategy),
        "total_items": len(scored),
        "prioritized": scored,
        "action_phases": phases,
        "estimated_timeline": _estimate_timeline(phases),
        "expected_improvement": _calculate_expected_improvement(scored),
    }

    return json.dumps(results, indent=2)


def _score_recommendations(recommendations: list[dict], strategy: str) -> list[dict]:
    """Score and sort recommendations based on strategy."""
    effort_scores = {"low": 1, "medium": 2, "high": 3}
    impact_scores = {"low": 1, "medium": 2, "high": 3}
    priority_scores = {"critical": 4, "high": 3, "medium": 2, "low": 1}

    scored_recs = []

    for rec in recommendations:
        effort = effort_scores.get(rec.get("effort", "medium"), 2)
        impact = impact_scores.get(rec.get("impact", "medium"), 2)
        priority = priority_scores.get(rec.get("priority", "medium"), 2)

        # Calculate score based on strategy
        if strategy == "quick_wins":
            # Favor low effort, any impact
            score = (4 - effort) * 3 + impact
        elif strategy == "high_impact":
            # Favor high impact, regardless of effort
            score = impact * 3 + priority
        else:  # balanced
            # Balance effort vs impact, with priority boost
            score = (impact / effort) * priority

        scored_rec = {
            **rec,
            "score": round(score, 2),
            "roi": f"{'High' if impact > effort else 'Medium' if impact == effort else 'Low'} ROI",
        }
        scored_recs.append(scored_rec)

    # Sort by score descending
    scored_recs.sort(key=lambda x: -x["score"])

    # Add rank
    for i, rec in enumerate(scored_recs):
        rec["rank"] = i + 1

    return scored_recs


def _create_action_phases(scored_recs: list[dict]) -> list[dict]:
    """Create action phases from prioritized recommendations."""
    phases = [
        {
            "phase": 1,
            "name": "Quick Wins",
            "description": "Low effort, immediate impact improvements",
            "items": [],
            "estimated_effort": "1-2 days",
        },
        {
            "phase": 2,
            "name": "Core Improvements",
            "description": "Medium effort improvements with good ROI",
            "items": [],
            "estimated_effort": "3-5 days",
        },
        {
            "phase": 3,
            "name": "Deep Improvements",
            "description": "Higher effort improvements for complete coverage",
            "items": [],
            "estimated_effort": "1-2 weeks",
        },
    ]

    for rec in scored_recs:
        effort = rec.get("effort", "medium")
        priority = rec.get("priority", "medium")

        # Determine phase
        if effort == "low" or (effort == "medium" and priority == "critical"):
            phase_idx = 0
        elif effort == "medium" or (effort == "high" and priority == "critical"):
            phase_idx = 1
        else:
            phase_idx = 2

        phases[phase_idx]["items"].append(
            {
                "rank": rec["rank"],
                "title": rec["title"],
                "action": rec.get("action", ""),
                "impact": rec.get("impact", "medium"),
                "count": rec.get("count", 0),
            }
        )

    # Calculate totals for each phase
    for phase in phases:
        phase["item_count"] = len(phase["items"])
        phase["total_mutants"] = sum(item.get("count", 0) for item in phase["items"])

    return phases


def _get_strategy_description(strategy: str) -> str:
    """Get description for a prioritization strategy."""
    descriptions = {
        "quick_wins": (
            "Focus on low-effort improvements first. "
            "Best for rapidly improving mutation score with minimal investment."
        ),
        "high_impact": (
            "Focus on highest impact improvements regardless of effort. "
            "Best for maximizing test quality improvement."
        ),
        "balanced": ("Balance effort vs impact for best ROI. " "Recommended for most situations."),
    }
    return descriptions.get(strategy, "Unknown strategy")


def _estimate_timeline(phases: list[dict]) -> dict:
    """Estimate timeline for completing improvements."""
    timeline = {"quick_wins": "1-2 days", "all_phases": "1-3 weeks", "breakdown": []}

    cumulative_days = 0
    for phase in phases:
        if phase["item_count"] > 0:
            if phase["phase"] == 1:
                days = min(2, phase["item_count"])
            elif phase["phase"] == 2:
                days = min(5, phase["item_count"])
            else:
                days = min(10, phase["item_count"] * 2)

            cumulative_days += days
            timeline["breakdown"].append(
                {
                    "phase": phase["name"],
                    "items": phase["item_count"],
                    "days": f"{days} day{'s' if days != 1 else ''}",
                }
            )

    timeline["total_estimated_days"] = cumulative_days

    return timeline


def _calculate_expected_improvement(scored_recs: list[dict]) -> dict:
    """Calculate expected improvement from recommendations."""
    improvement = {
        "estimated_mutants_killed": 0,
        "by_phase": {"phase_1": 0, "phase_2": 0, "phase_3": 0},
    }

    for rec in scored_recs:
        count = rec.get("count", 0)
        effort = rec.get("effort", "medium")

        # Estimate kill rate based on effort (better tests = more kills)
        kill_rate = 0.8 if effort == "high" else 0.6 if effort == "medium" else 0.4
        estimated_kills = int(count * kill_rate)

        improvement["estimated_mutants_killed"] += estimated_kills

        # Assign to phase
        if effort == "low":
            improvement["by_phase"]["phase_1"] += estimated_kills
        elif effort == "medium":
            improvement["by_phase"]["phase_2"] += estimated_kills
        else:
            improvement["by_phase"]["phase_3"] += estimated_kills

    return improvement
