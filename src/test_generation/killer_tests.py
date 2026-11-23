"""
Generate killer tests tool.

Generates tests specifically designed to kill surviving mutants based on
mutation testing analysis, with the LLM and the mutation_killer prompt.

There is deliberately NO template fallback: a placeholder test
(`assertThat(result).isEqualTo(/* expected */)`) does not compile and breaks
the whole test suite. A class whose source cannot be found, or for which the
LLM returns no test, is reported as skipped instead.
"""

import json
import re
from pathlib import Path
from typing import Any

from src.lib.llm import get_llm
from src.lib.logging import get_logger
from src.lib.prompt_utils import (
    extract_code_block,
    load_prompt_template,
    render_template,
    response_text,
)

logger = get_logger(__name__)

# A fully-qualified Java class name as PIT reports it (nested: Outer$Inner).
# Anything else is refused before it is turned into a file path.
_JAVA_CLASS_NAME = re.compile(r"^[A-Za-z_$][\w$]*(\.[A-Za-z_$][\w$]*)*$")


async def generate_killer_tests(
    project_path: str,
    surviving_mutants: list[dict[str, Any]],
    max_tests: int = 10,
    hints: dict[str, str] | None = None,
) -> str:
    """
    Generate tests to kill surviving mutants.

    Args:
        project_path: Path to the Java project root directory
        surviving_mutants: List of surviving mutants to target
        max_tests: Maximum number of killer tests to generate
        hints: Developer-provided guidance keyed by "ClassName.methodName"
            (or just "ClassName"); matching hints are appended to the LLM
            prompt for that class

    Returns:
        JSON string with generated killer test code
    """
    project_dir = Path(project_path)

    if not project_dir.exists():
        return json.dumps(
            {"success": False, "error": f"Project path does not exist: {project_path}"}
        )

    if not surviving_mutants:
        return json.dumps({"success": False, "error": "No surviving mutants provided"})

    # Group mutants by class
    by_class: dict[str, list[dict[str, Any]]] = {}
    for mutant in surviving_mutants[:max_tests]:
        class_name = mutant.get("class", "")
        if class_name not in by_class:
            by_class[class_name] = []
        by_class[class_name].append(mutant)

    # Generate killer tests for each class
    generated_tests: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []

    for class_name, mutants in by_class.items():
        if not _JAVA_CLASS_NAME.match(class_name):
            skipped.append({"class": class_name, "reason": "invalid class name"})
            continue
        src_path = _find_source_file(project_dir, class_name)
        if src_path is None or not src_path.exists():
            skipped.append({"class": class_name, "reason": "source file not found"})
            continue
        source_code = src_path.read_text(encoding="utf-8", errors="replace")

        # Hints matching this class (keys are "ClassName.methodName" or
        # "ClassName", with either the simple or fully-qualified name)
        simple_name = class_name.rsplit(".", 1)[-1]
        class_hints = {
            k: v for k, v in (hints or {}).items()
            if k in (class_name, simple_name)
            or k.startswith((f"{class_name}.", f"{simple_name}."))
        }

        test_code = await _generate_killer_tests_llm(
            class_name, mutants, source_code, hints=class_hints or None
        )
        if test_code is None:
            skipped.append({"class": class_name, "reason": "LLM returned no @Test method"})
            continue

        generated_tests.append(
            {
                "class": class_name,
                "test_file": str(_get_killer_test_path(project_dir, class_name, src_path)),
                "test_code": test_code,
                "mutants_targeted": len(mutants),
            }
        )

    results = {
        "success": True,
        "generated_tests": generated_tests,
        "total_tests": sum(t["mutants_targeted"] for t in generated_tests),
        "total_mutants_targeted": len(surviving_mutants[:max_tests]),
        "skipped": skipped,
    }

    return json.dumps(results, indent=2)


async def _generate_killer_tests_llm(
    class_name: str,
    mutants: list[dict[str, Any]],
    source_code: str,
    hints: dict[str, str] | None = None,
) -> str | None:
    """Use LLM with mutation_killer prompt to generate targeted killer tests.

    Returns None when the response contains no @Test method.
    """
    parts = class_name.rsplit(".", 1)
    package = parts[0] if len(parts) > 1 else ""
    simple_name = parts[-1]

    template = load_prompt_template("testing/mutation_killer.md")
    prompt = render_template(
        template,
        surviving_mutants=json.dumps(mutants, indent=2),
        source_code=source_code,
        class_name=simple_name,
        package=package,
    )

    if hints:
        prompt += (
            "\n\n## Developer hints about these mutants (follow them)\n\n"
            + "\n".join(f"- `{key}`: {text}" for key, text in hints.items())
        )

    llm = get_llm()
    response = await llm.ainvoke(prompt)
    code = extract_code_block(response_text(response))

    if "@Test" not in code:
        logger.warning("llm_killer_no_test", class_name=class_name)
        return None

    logger.info(
        "llm_killer_generation_success",
        class_name=class_name,
        test_count=code.count("@Test"),
    )
    return code


def _find_source_file(project_dir: Path, class_name: str) -> Path | None:
    """Find the source file of a class (single- or multi-module Maven layout)."""
    outer = class_name.split("$", 1)[0]  # nested classes live in the outer file
    class_path = outer.replace(".", "/") + ".java"

    direct = project_dir / "src" / "main" / "java" / class_path
    if direct.exists():
        return direct
    for candidate in sorted(project_dir.glob(f"**/src/main/java/{class_path}")):
        if "target" not in candidate.relative_to(project_dir).parts:
            return candidate
    flat = project_dir / "src" / class_path
    return flat if flat.exists() else None


def _get_killer_test_path(project_dir: Path, class_name: str, source_path: Path | None = None) -> Path:
    """Killer test path, next to the module of the class under test.

    `<module>/src/main/java/a/b/Foo.java` -> `<module>/src/test/java/a/b/FooKillerTest.java`.
    """
    outer = class_name.split("$", 1)[0]
    parts = outer.split(".")
    parts[-1] = f"{parts[-1]}KillerTest.java"
    module_root = project_dir
    if source_path is not None:
        src_parts = source_path.parts
        for i in range(len(src_parts) - 2):
            if src_parts[i:i + 3] == ("src", "main", "java"):
                module_root = Path(*src_parts[:i])
                break
    return module_root / "src" / "test" / "java" / Path(*parts)
