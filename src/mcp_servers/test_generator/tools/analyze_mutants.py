"""
Analyze mutants tool.

Analyzes mutation testing results to identify hard-to-kill mutants
and provide insights for test improvement.
"""

import json
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Any


async def analyze_mutants(
    project_path: str, report_path: str | None = None, min_score: float = 80
) -> str:
    """
    Analyze mutation testing results for insights.

    Args:
        project_path: Path to the Java project root directory
        report_path: Path to PIT mutation report (optional)
        min_score: Minimum mutation score threshold

    Returns:
        JSON string with mutant analysis
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    # Find PIT report
    if report_path:
        report_file = Path(report_path) / "mutations.xml"
    else:
        pit_reports = list(project_dir.rglob("pit-reports/**/mutations.xml"))
        if not pit_reports:
            return json.dumps({"success": False, "error": "PIT report not found"})
        report_file = pit_reports[0]

    if not report_file.exists():
        return json.dumps({"success": False, "error": f"Mutations file not found: {report_file}"})

    # Analyze mutations
    analysis = await _analyze_mutations(report_file, min_score)

    return json.dumps(analysis, indent=2)


async def _analyze_mutations(report_file: Path, min_score: float) -> dict[str, Any]:
    """Perform detailed mutation analysis."""
    hard_to_kill: list[dict[str, Any]] = []
    by_class: list[dict[str, Any]] = []
    recommendations: list[str] = []
    priority_improvements: list[dict[str, Any]] = []

    analysis: dict[str, Any] = {
        "success": True,
        "mutation_score": 0,
        "meets_threshold": False,
        "threshold": min_score,
        "summary": {"total_mutants": 0, "killed": 0, "survived": 0, "no_coverage": 0},
        "hard_to_kill": hard_to_kill,
        "by_mutator": {},
        "by_class": by_class,
        "recommendations": recommendations,
        "priority_improvements": priority_improvements,
    }

    try:
        tree = ET.parse(report_file)
        root = tree.getroot()

        surviving: list[dict[str, Any]] = []
        no_coverage_list: list[dict[str, Any]] = []
        mutator_stats: Counter[str] = Counter()
        class_stats: dict[str, dict[str, Any]] = {}

        for mutation in root.findall(".//mutation"):
            status = mutation.get("status", "UNKNOWN")
            class_name = mutation.findtext("mutatedClass", "")
            method = mutation.findtext("mutatedMethod", "")
            line = int(mutation.findtext("lineNumber", "0"))
            mutator = mutation.findtext("mutator", "").split(".")[-1]
            description = mutation.findtext("description", "")
            _ = mutation.findtext("killingTest", "")  # killingTest extracted but not used currently

            analysis["summary"]["total_mutants"] += 1
            mutator_stats[mutator] += 1

            # Track by class
            if class_name not in class_stats:
                class_stats[class_name] = {
                    "killed": 0,
                    "survived": 0,
                    "no_coverage": 0,
                    "methods": set(),
                }
            class_stats[class_name]["methods"].add(method)

            if status == "KILLED":
                analysis["summary"]["killed"] += 1
                class_stats[class_name]["killed"] += 1
            elif status == "SURVIVED":
                analysis["summary"]["survived"] += 1
                class_stats[class_name]["survived"] += 1
                surviving.append(
                    {
                        "class": class_name,
                        "method": method,
                        "line": line,
                        "mutator": mutator,
                        "description": description,
                    }
                )
            elif status == "NO_COVERAGE":
                analysis["summary"]["no_coverage"] += 1
                class_stats[class_name]["no_coverage"] += 1
                no_coverage_list.append({"class": class_name, "method": method, "line": line})

        # Calculate mutation score
        total = analysis["summary"]["total_mutants"]
        if total > 0:
            score = (analysis["summary"]["killed"] / total) * 100
            analysis["mutation_score"] = round(score, 1)
            analysis["meets_threshold"] = score >= min_score

        # Analyze by mutator type
        analysis["by_mutator"] = dict(mutator_stats.most_common())

        # Identify hard-to-kill mutants (patterns)
        hard_to_kill.extend(_identify_hard_to_kill(surviving))

        # Class-level analysis
        for class_name, stats in class_stats.items():
            total_class = stats["killed"] + stats["survived"] + stats["no_coverage"]
            score = (stats["killed"] / total_class * 100) if total_class > 0 else 0

            by_class.append(
                {
                    "class": class_name,
                    "score": round(score, 1),
                    "killed": stats["killed"],
                    "survived": stats["survived"],
                    "no_coverage": stats["no_coverage"],
                    "methods_count": len(stats["methods"]),
                }
            )

        # Sort classes by score
        by_class.sort(key=lambda x: x["score"])

        # Generate recommendations
        recommendations.extend(_generate_recommendations(analysis, surviving, no_coverage_list))

        # Identify priority improvements
        priority_improvements.extend(_identify_priorities(surviving, no_coverage_list, class_stats))

    except ET.ParseError as e:
        analysis["success"] = False
        analysis["error"] = f"Failed to parse report: {e}"

    return analysis


def _identify_hard_to_kill(surviving: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Identify patterns in hard-to-kill mutants."""
    patterns: dict[str, dict[str, Any]] = {}

    for mutant in surviving:
        mutator = mutant["mutator"]
        if mutator not in patterns:
            patterns[mutator] = {"mutator": mutator, "count": 0, "examples": []}

        patterns[mutator]["count"] += 1
        if len(patterns[mutator]["examples"]) < 3:
            patterns[mutator]["examples"].append(
                {
                    "class": mutant["class"].split(".")[-1],
                    "method": mutant["method"],
                    "line": mutant["line"],
                    "description": mutant["description"],
                }
            )

    # Return sorted by count
    return sorted(patterns.values(), key=lambda x: x["count"], reverse=True)


def _generate_recommendations(
    analysis: dict[str, Any], surviving: list[dict[str, Any]], no_coverage: list[dict[str, Any]]
) -> list[str]:
    """Generate test improvement recommendations."""
    recommendations = []

    score = analysis["mutation_score"]
    threshold = analysis["threshold"]

    if score < threshold:
        gap = threshold - score
        recommendations.append(
            f"Mutation score ({score}%) is below threshold ({threshold}%). "
            f"Need to kill {int(gap * analysis['summary']['total_mutants'] / 100)} more mutants."
        )

    if no_coverage:
        recommendations.append(
            f"Found {len(no_coverage)} mutants with no test coverage. "
            "Add tests for these methods first."
        )

    # Analyze mutator patterns
    mutators = analysis["by_mutator"]
    if "ConditionalsBoundaryMutator" in mutators:
        count = mutators["ConditionalsBoundaryMutator"]
        recommendations.append(
            f"{count} boundary condition mutants survived. "
            "Add tests for boundary values (<=, >=, <, >)."
        )

    if "NegateConditionalsMutator" in mutators:
        count = mutators["NegateConditionalsMutator"]
        recommendations.append(
            f"{count} negated conditional mutants survived. "
            "Add tests that verify both true and false branches."
        )

    if "ReturnValuesMutator" in mutators or "EmptyReturnValuesMutator" in mutators:
        recommendations.append(
            "Surviving return value mutants detected. "
            "Add assertions that verify actual return values, not just non-null."
        )

    # Class-specific recommendations
    worst_classes = [c for c in analysis["by_class"] if c["score"] < 50][:3]
    if worst_classes:
        class_names = ", ".join(c["class"].split(".")[-1] for c in worst_classes)
        recommendations.append(f"Focus testing effort on: {class_names} (lowest mutation scores).")

    return recommendations


def _identify_priorities(
    surviving: list[dict[str, Any]],
    no_coverage: list[dict[str, Any]],
    class_stats: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Identify priority test improvements."""
    priorities: list[dict[str, Any]] = []

    # Group surviving mutants by class and method
    by_method: dict[str, list[dict[str, Any]]] = {}
    for mutant in surviving:
        key = f"{mutant['class']}#{mutant['method']}"
        if key not in by_method:
            by_method[key] = []
        by_method[key].append(mutant)

    # Sort by number of surviving mutants
    for key, mutants in sorted(by_method.items(), key=lambda x: -len(x[1]))[:10]:
        class_name, method = key.split("#")
        priorities.append(
            {
                "type": "surviving_mutants",
                "class": class_name.split(".")[-1],
                "method": method,
                "count": len(mutants),
                "mutants": mutants[:5],  # Include up to 5 examples
                "action": f"Add tests to kill {len(mutants)} surviving mutants",
            }
        )

    # Add no-coverage priorities
    no_cov_by_method = {}
    for item in no_coverage:
        key = f"{item['class']}#{item['method']}"
        if key not in no_cov_by_method:
            no_cov_by_method[key] = 0
        no_cov_by_method[key] += 1

    for key, count in sorted(no_cov_by_method.items(), key=lambda x: -x[1])[:5]:
        class_name, method = key.split("#")
        priorities.append(
            {
                "type": "no_coverage",
                "class": class_name.split(".")[-1],
                "method": method,
                "count": count,
                "action": f"Add test coverage for {method} ({count} uncovered mutants)",
            }
        )

    return priorities
