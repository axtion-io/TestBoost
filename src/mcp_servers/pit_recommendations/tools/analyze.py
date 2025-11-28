"""
Analyze hard mutants tool.

Analyzes mutation testing results to identify patterns in
hard-to-kill mutants for targeted test improvements.
"""

import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


async def analyze_hard_mutants(
    project_path: str, report_path: str | None = None, group_by: str = "mutator"
) -> str:
    """
    Analyze mutation testing results for hard-to-kill mutants.

    Args:
        project_path: Path to the Java project root directory
        report_path: Path to PIT mutation report directory
        group_by: How to group results (mutator, class, method)

    Returns:
        JSON string with hard mutant analysis
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
            return json.dumps(
                {"success": False, "error": "PIT report not found. Run mutation testing first."}
            )
        report_file = pit_reports[0]

    if not report_file.exists():
        return json.dumps({"success": False, "error": f"Mutations file not found: {report_file}"})

    # Perform analysis
    analysis = await _analyze_hard_mutants(report_file, group_by)

    return json.dumps(analysis, indent=2)


async def _analyze_hard_mutants(report_file: Path, group_by: str) -> dict[str, Any]:
    """Analyze mutation report for hard-to-kill patterns."""
    analysis = {
        "success": True,
        "summary": {
            "total_mutants": 0,
            "killed": 0,
            "survived": 0,
            "no_coverage": 0,
            "mutation_score": 0,
        },
        "hard_mutant_patterns": [],
        "grouped_analysis": {},
        "hot_spots": [],
        "complexity_indicators": [],
    }

    try:
        tree = ET.parse(report_file)
        root = tree.getroot()

        # Collect all mutations
        surviving = []
        all_mutations = []

        for mutation in root.findall(".//mutation"):
            status = mutation.get("status", "UNKNOWN")
            mutant_data = {
                "class": mutation.findtext("mutatedClass", ""),
                "method": mutation.findtext("mutatedMethod", ""),
                "line": int(mutation.findtext("lineNumber", "0")),
                "mutator": mutation.findtext("mutator", "").split(".")[-1],
                "description": mutation.findtext("description", ""),
                "status": status,
            }

            all_mutations.append(mutant_data)
            analysis["summary"]["total_mutants"] += 1

            if status == "KILLED":
                analysis["summary"]["killed"] += 1
            elif status == "SURVIVED":
                analysis["summary"]["survived"] += 1
                surviving.append(mutant_data)
            elif status == "NO_COVERAGE":
                analysis["summary"]["no_coverage"] += 1

        # Calculate mutation score
        total = analysis["summary"]["total_mutants"]
        if total > 0:
            analysis["summary"]["mutation_score"] = round(
                (analysis["summary"]["killed"] / total) * 100, 1
            )

        # Group analysis
        if group_by == "mutator":
            analysis["grouped_analysis"] = _group_by_mutator(surviving)
        elif group_by == "class":
            analysis["grouped_analysis"] = _group_by_class(surviving)
        else:  # method
            analysis["grouped_analysis"] = _group_by_method(surviving)

        # Identify patterns
        analysis["hard_mutant_patterns"] = _identify_patterns(surviving)

        # Find hot spots (high concentration of surviving mutants)
        analysis["hot_spots"] = _find_hot_spots(surviving)

        # Identify complexity indicators
        analysis["complexity_indicators"] = _identify_complexity(surviving, all_mutations)

    except ET.ParseError as e:
        analysis["success"] = False
        analysis["error"] = f"Failed to parse report: {e}"

    return analysis


def _group_by_mutator(surviving: list[dict]) -> dict[str, Any]:
    """Group surviving mutants by mutator type."""
    groups = defaultdict(list)

    for mutant in surviving:
        groups[mutant["mutator"]].append(mutant)

    result = {}
    for mutator, mutants in sorted(groups.items(), key=lambda x: -len(x[1])):
        result[mutator] = {
            "count": len(mutants),
            "affected_classes": list(set(m["class"].split(".")[-1] for m in mutants)),
            "examples": mutants[:5],
        }

    return result


def _group_by_class(surviving: list[dict]) -> dict[str, Any]:
    """Group surviving mutants by class."""
    groups = defaultdict(list)

    for mutant in surviving:
        groups[mutant["class"]].append(mutant)

    result = {}
    for class_name, mutants in sorted(groups.items(), key=lambda x: -len(x[1])):
        simple_name = class_name.split(".")[-1]
        result[simple_name] = {
            "full_name": class_name,
            "count": len(mutants),
            "methods": list(set(m["method"] for m in mutants)),
            "mutators": list(set(m["mutator"] for m in mutants)),
            "lines": sorted(set(m["line"] for m in mutants)),
        }

    return result


def _group_by_method(surviving: list[dict]) -> dict[str, Any]:
    """Group surviving mutants by method."""
    groups = defaultdict(list)

    for mutant in surviving:
        key = f"{mutant['class'].split('.')[-1]}#{mutant['method']}"
        groups[key].append(mutant)

    result = {}
    for method_key, mutants in sorted(groups.items(), key=lambda x: -len(x[1])):
        result[method_key] = {
            "count": len(mutants),
            "mutators": Counter(m["mutator"] for m in mutants).most_common(),
            "lines": sorted(set(m["line"] for m in mutants)),
            "examples": mutants[:5],
        }

    return result


def _identify_patterns(surviving: list[dict]) -> list[dict]:
    """Identify common patterns in hard-to-kill mutants."""
    patterns = []

    # Mutator frequency
    mutator_counts = Counter(m["mutator"] for m in surviving)
    total = len(surviving)

    for mutator, count in mutator_counts.most_common(5):
        percentage = round((count / total) * 100, 1) if total > 0 else 0
        patterns.append(
            {
                "type": "mutator_concentration",
                "mutator": mutator,
                "count": count,
                "percentage": percentage,
                "description": f"{mutator} accounts for {percentage}% of surviving mutants",
                "suggested_action": _get_mutator_action(mutator),
            }
        )

    # Line clustering (multiple mutants on same line)
    line_clusters = defaultdict(list)
    for mutant in surviving:
        key = f"{mutant['class']}:{mutant['line']}"
        line_clusters[key].append(mutant)

    clusters = [(key, mutants) for key, mutants in line_clusters.items() if len(mutants) > 1]
    clusters.sort(key=lambda x: -len(x[1]))

    for key, mutants in clusters[:3]:
        class_name, line = key.rsplit(":", 1)
        patterns.append(
            {
                "type": "line_cluster",
                "class": class_name.split(".")[-1],
                "line": int(line),
                "count": len(mutants),
                "mutators": [m["mutator"] for m in mutants],
                "description": f"Line {line} has {len(mutants)} surviving mutants",
                "suggested_action": "Review this line - likely needs multiple targeted tests",
            }
        )

    return patterns


def _find_hot_spots(surviving: list[dict]) -> list[dict]:
    """Find code hot spots with high mutant survival."""
    # Group by method and calculate density
    method_mutants = defaultdict(list)
    for mutant in surviving:
        key = f"{mutant['class']}#{mutant['method']}"
        method_mutants[key].append(mutant)

    hot_spots = []
    for key, mutants in method_mutants.items():
        if len(mutants) >= 3:  # Threshold for hot spot
            class_name, method = key.split("#")
            lines = [m["line"] for m in mutants]

            hot_spots.append(
                {
                    "class": class_name.split(".")[-1],
                    "method": method,
                    "surviving_count": len(mutants),
                    "line_range": f"{min(lines)}-{max(lines)}",
                    "mutators": list(set(m["mutator"] for m in mutants)),
                    "severity": "high" if len(mutants) >= 5 else "medium",
                }
            )

    return sorted(hot_spots, key=lambda x: -x["surviving_count"])[:10]


def _identify_complexity(surviving: list[dict], all_mutations: list[dict]) -> list[dict]:
    """Identify complexity indicators from mutation patterns."""
    indicators = []

    # Calculate survival rate by class
    class_stats = defaultdict(lambda: {"killed": 0, "survived": 0})
    for mutation in all_mutations:
        class_name = mutation["class"].split(".")[-1]
        if mutation["status"] == "KILLED":
            class_stats[class_name]["killed"] += 1
        elif mutation["status"] == "SURVIVED":
            class_stats[class_name]["survived"] += 1

    # Find classes with high survival rates
    for class_name, stats in class_stats.items():
        total = stats["killed"] + stats["survived"]
        if total > 0:
            survival_rate = stats["survived"] / total
            if survival_rate > 0.5 and stats["survived"] >= 3:
                indicators.append(
                    {
                        "type": "high_survival_rate",
                        "class": class_name,
                        "survival_rate": round(survival_rate * 100, 1),
                        "surviving_count": stats["survived"],
                        "indication": "Complex logic or insufficient test coverage",
                    }
                )

    return sorted(indicators, key=lambda x: -x["survival_rate"])


def _get_mutator_action(mutator: str) -> str:
    """Get suggested action for a mutator type."""
    actions = {
        "ConditionalsBoundaryMutator": "Add boundary value tests (<=, >=, <, >)",
        "NegateConditionalsMutator": "Test both branches of conditionals",
        "MathMutator": "Verify exact mathematical results",
        "IncrementsMutator": "Test increment/decrement operations precisely",
        "ReturnValuesMutator": "Assert specific return values, not just non-null",
        "VoidMethodCallMutator": "Verify side effects of void method calls",
        "EmptyReturnValuesMutator": "Test for non-empty return values",
        "NullReturnValuesMutator": "Test for non-null return values",
        "BooleanTrueReturnValsMutator": "Add tests expecting false returns",
        "BooleanFalseReturnValsMutator": "Add tests expecting true returns",
    }

    return actions.get(mutator, f"Add targeted tests for {mutator}")
