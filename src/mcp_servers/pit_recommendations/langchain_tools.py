"""LangChain BaseTool wrappers for PIT Recommendations MCP tools."""

from typing import Any

from langchain_core.tools import BaseTool, tool

# Import existing MCP tool implementations
from src.mcp_servers.pit_recommendations.tools.analyze import analyze_hard_mutants
from src.mcp_servers.pit_recommendations.tools.prioritize import prioritize_test_efforts
from src.mcp_servers.pit_recommendations.tools.recommend import recommend_test_improvements


@tool
async def pit_analyze_hard_mutants(
    project_path: str, report_path: str | None = None, group_by: str = "mutator"
) -> str:
    """
    Analyze mutation testing results to identify hard-to-kill mutants.

    Use this tool to:
    - Analyze PIT mutation testing reports
    - Identify patterns in surviving mutants
    - Find code hot spots with high mutant survival
    - Detect complexity indicators from mutation patterns

    Args:
        project_path: Path to the Java project root directory
        report_path: Path to PIT mutation report directory (optional, auto-detected if not provided)
        group_by: How to group hard-to-kill mutants (mutator, class, method)

    Returns:
        JSON with hard mutant analysis including summary, patterns, hot spots, and complexity indicators
    """
    return await analyze_hard_mutants(
        project_path=project_path, report_path=report_path, group_by=group_by
    )


@tool
async def pit_recommend_test_improvements(
    project_path: str,
    mutation_analysis: dict[str, Any] | None = None,
    target_score: float = 80.0,
    max_recommendations: int = 20,
) -> str:
    """
    Generate specific recommendations for improving test effectiveness.

    Use this tool to:
    - Generate targeted test improvement recommendations
    - Prioritize improvements based on mutation analysis
    - Suggest specific test patterns for hard-to-kill mutants
    - Provide actionable guidance to increase mutation score

    Args:
        project_path: Path to the Java project root directory
        mutation_analysis: Results from analyze-hard-mutants (optional)
        target_score: Target mutation score percentage (default: 80.0)
        max_recommendations: Maximum number of recommendations (default: 20)

    Returns:
        JSON with prioritized test improvement recommendations
    """
    return await recommend_test_improvements(
        project_path=project_path,
        mutation_analysis=mutation_analysis,
        target_score=target_score,
        max_recommendations=max_recommendations,
    )


@tool
async def pit_prioritize_test_efforts(
    project_path: str,
    recommendations: list[dict[str, Any]] | None = None,
    strategy: str = "balanced",
) -> str:
    """
    Prioritize test improvement efforts based on impact and effort.

    Use this tool to:
    - Prioritize test improvements by strategy (quick_wins, high_impact, balanced)
    - Estimate effort vs impact for each recommendation
    - Create actionable roadmap for test improvements
    - Focus testing efforts on highest-value targets

    Args:
        project_path: Path to the Java project root directory
        recommendations: List of test improvement recommendations (from recommend-test-improvements)
        strategy: Prioritization strategy (quick_wins, high_impact, balanced)

    Returns:
        JSON with prioritized test improvement roadmap
    """
    return await prioritize_test_efforts(
        project_path=project_path, recommendations=recommendations, strategy=strategy
    )


def get_pit_tools() -> list[BaseTool]:
    """
    Get all PIT recommendations MCP tools as LangChain BaseTool instances.

    Returns:
        List of 3 BaseTool instances for mutation testing analysis and recommendations
    """
    return [
        pit_analyze_hard_mutants,
        pit_recommend_test_improvements,
        pit_prioritize_test_efforts,
    ]


__all__ = [
    "get_pit_tools",
    "pit_analyze_hard_mutants",
    "pit_recommend_test_improvements",
    "pit_prioritize_test_efforts",
]
