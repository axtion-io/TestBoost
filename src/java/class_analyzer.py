"""Project-level Java class analyzer for TestBoost.

Builds a class index over all source files during the analyze phase,
so the generate phase can access pre-analyzed class structures without
lazy filesystem lookups.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.java.parsing_utils import (
    _PRIMITIVE_TYPES,  # noqa: F401 — re-exported for callers that import from here
    _analyze_jpa_fields,
    _extract_balanced_parens,
    _extract_public_signatures,
    _is_primitive_type,
    _parse_parameters,
)

# ---------------------------------------------------------------------------
# extends / implements extraction
# ---------------------------------------------------------------------------

_CLASS_DECL_PATTERN = re.compile(
    r"(?:public\s+)?(?:abstract\s+)?(?:final\s+)?class\s+\w+(?:<[^>]+>)?\s*"
    r"(?:extends\s+([\w<>, ]+?)\s*)?"
    r"(?:implements\s+([\w<>, ]+?)\s*)?"
    r"\{",
    re.MULTILINE,
)


def _extract_extends_implements(source_code: str) -> tuple[str | None, list[str]]:
    """Extract extends and implements from a Java class declaration.

    Returns:
        (extends_simple_name | None, [implements_simple_name, ...])
    """
    m = _CLASS_DECL_PATTERN.search(source_code)
    if not m:
        return None, []

    extends_raw = m.group(1)
    implements_raw = m.group(2)

    extends_name: str | None = None
    if extends_raw:
        # Strip generics: BaseClass<T> → BaseClass
        extends_name = extends_raw.strip().split("<")[0].strip()

    implements_list: list[str] = []
    if implements_raw:
        for iface in implements_raw.split(","):
            simple = iface.strip().split("<")[0].strip()
            if simple:
                implements_list.append(simple)

    return extends_name, implements_list


# ---------------------------------------------------------------------------
# richer field extraction (with annotations)
# ---------------------------------------------------------------------------

def _extract_field_details(source_code: str) -> list[dict[str, Any]]:
    """Extract class-level fields with their annotations and types.

    Handles patterns like:
        @Id
        @GeneratedValue
        private Long id;

        @Autowired
        private UserRepository userRepository;

        private final String name;
    """
    results: list[dict[str, Any]] = []
    # Walk line by line collecting annotation blocks + field declaration
    lines = source_code.splitlines()
    pending_annotations: list[str] = []
    for line in lines:
        stripped = line.strip()
        ann_match = re.match(r"@(\w+)(?:\([^)]*\))?", stripped)
        if ann_match and not stripped.startswith("//"):
            pending_annotations.append(ann_match.group(1))
            continue
        # Field declaration: [modifiers] Type name;
        field_match = re.match(
            r"(?:private|protected|public)?\s*(?:static\s+)?(?:final\s+)?"
            r"([\w<>\[\]]+(?:\s*<[^;]*>)?)\s+(\w+)\s*[;=]",
            stripped,
        )
        if field_match:
            ftype = field_match.group(1).strip()
            fname = field_match.group(2).strip()
            # Skip keywords that look like field declarations
            if fname not in {"if", "while", "for", "return", "class", "new", "import", "package"}:
                results.append({
                    "name": fname,
                    "type": ftype,
                    "annotations": list(pending_annotations),
                })
            pending_annotations = []
            continue
        # Any non-blank, non-comment line clears the pending annotation list
        if stripped and not stripped.startswith("//") and not stripped.startswith("*"):
            pending_annotations = []

    return results


# ---------------------------------------------------------------------------
# Core: analyze_java_class
# ---------------------------------------------------------------------------

def analyze_java_class(source_code: str, relative_path: str = "") -> dict[str, Any]:
    """Parse a Java source file into a ClassIndexEntry dict.

    Returns a dict with:
        class_name, package, relative_path, category,
        extends, implements, annotations, fields, methods,
        dependencies, imports, is_record, is_jpa_entity, jpa_info,
        public_signatures
    """
    entry: dict[str, Any] = {
        "class_name": "",
        "package": "",
        "relative_path": relative_path,
        "category": "other",
        "extends": None,
        "implements": [],
        "annotations": [],
        "fields": [],
        "methods": [],
        "dependencies": [],
        "imports": [],
        "is_record": False,
        "is_jpa_entity": False,
        "jpa_info": {
            "id_field": None,
            "id_type": None,
            "has_generated_value": False,
            "date_fields": [],
        },
        "public_signatures": "",
    }

    # Package
    pkg_m = re.search(r"package\s+([\w.]+);", source_code)
    if pkg_m:
        entry["package"] = pkg_m.group(1)

    # Imports
    for m in re.finditer(r"import\s+([\w.]+(?:\.\*)?);", source_code, re.MULTILINE):
        entry["imports"].append(m.group(1))

    # Record check
    record_m = re.search(r"(?:public\s+)?record\s+(\w+)\s*\(([^)]*)\)", source_code)
    if record_m:
        entry["class_name"] = record_m.group(1)
        entry["is_record"] = True
        for param in _parse_parameters(record_m.group(2)):
            if not _is_primitive_type(param["type"]):
                entry["dependencies"].append({"type": param["type"], "name": param["name"]})
        entry["category"] = "model"
        return entry

    # Class name
    cls_m = re.search(r"(?:public\s+)?(?:abstract\s+)?class\s+(\w+)", source_code)
    if cls_m:
        entry["class_name"] = cls_m.group(1)

    # Extends / implements
    extends_name, implements_list = _extract_extends_implements(source_code)
    entry["extends"] = extends_name
    entry["implements"] = implements_list

    # Class-level annotations
    class_decl_m = re.search(r'(?:public\s+)?(?:abstract\s+)?class\s+\w+', source_code)
    if class_decl_m:
        before = source_code[:class_decl_m.start()]
        found = re.findall(r'@(\w+)(?:\([^)]*\))?', before)
        keep = {
            'Controller', 'RestController', 'Service', 'Repository', 'Component',
            'RequestMapping', 'Timed', 'Transactional', 'Configuration', 'Bean',
            'Slf4j', 'Log4j2', 'Data', 'Entity', 'Table', 'Document',
        }
        entry["annotations"] = [a for a in found if a in keep]

    # Fields (rich: with annotations)
    entry["fields"] = _extract_field_details(source_code)

    # Methods
    method_sig_pattern = re.compile(
        r"(public|protected)\s+"
        r"(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?"
        r"(\w+(?:<[^>]+>)?)\s+"
        r"(\w+)\s*\(",
        re.MULTILINE,
    )
    class_name = entry["class_name"]
    for m in method_sig_pattern.finditer(source_code):
        visibility = m.group(1)
        return_type = m.group(2)
        method_name = m.group(3)
        if method_name == class_name:
            continue  # constructor
        params = _extract_balanced_parens(source_code, m.end() - 1)
        parsed = _parse_parameters(params)
        entry["methods"].append({
            "name": method_name,
            "return_type": return_type,
            "parameters": params,
            "parsed_params": parsed,
            "is_void": return_type == "void",
            "visibility": visibility,
        })

    # Constructor injection
    if class_name:
        ctor_pattern = re.compile(
            rf"(?:public\s+)?{re.escape(class_name)}\s*\(([^)]*)\)",
            re.MULTILINE | re.DOTALL,
        )
        for m in ctor_pattern.finditer(source_code):
            for param in _parse_parameters(m.group(1)):
                if not _is_primitive_type(param["type"]):
                    if not any(d["name"] == param["name"] for d in entry["dependencies"]):
                        entry["dependencies"].append({"type": param["type"], "name": param["name"]})

    # Field injection (@Autowired, @Inject, @Resource)
    dep_pattern = re.compile(
        r"@(?:Autowired|Inject|Resource)\s+(?:private\s+)?(\w+(?:<[^>]+>)?)\s+(\w+)",
        re.MULTILINE,
    )
    for m in dep_pattern.finditer(source_code):
        if not any(d["name"] == m.group(2) for d in entry["dependencies"]):
            entry["dependencies"].append({"type": m.group(1), "name": m.group(2)})

    # JPA fields
    entry["jpa_info"] = _analyze_jpa_fields(source_code)
    entry["is_jpa_entity"] = (
        "Entity" in entry["annotations"] or "Table" in entry["annotations"]
    )

    # Category
    entry["category"] = _detect_category(source_code, entry)

    # Pre-built signatures string for LLM
    entry["public_signatures"] = _extract_public_signatures(source_code)

    return entry


def _detect_category(source_code: str, entry: dict[str, Any]) -> str:
    name = entry["class_name"].lower()
    anns = [a.lower() for a in entry["annotations"]]
    if "restcontroller" in anns or "controller" in anns or "controller" in name or "resource" in name:
        return "controller"
    if "service" in anns or "service" in name:
        return "service"
    if "repository" in anns or "repository" in name or "dao" in name or "mapper" in name:
        return "repository"
    if "entity" in anns or "table" in anns or "document" in anns or "model" in name or "entity" in name:
        return "model"
    if "configuration" in anns or "config" in name or "configuration" in name:
        return "config"
    if "exception" in name or "error" in name:
        return "exception"
    if "util" in name or "helper" in name or "utils" in name:
        return "utility"
    return "other"


# ---------------------------------------------------------------------------
# Build class index over a whole project
# ---------------------------------------------------------------------------

def build_class_index(project_path: str, source_files: list[str]) -> dict[str, dict[str, Any]]:
    """Build a class index for all source files.

    Args:
        project_path: Absolute path to the Java project root.
        source_files: List of relative file paths (e.g. "src/main/java/.../Foo.java").

    Returns:
        Dict mapping class_name → ClassIndexEntry.
    """
    index: dict[str, dict[str, Any]] = {}
    project_dir = Path(project_path)
    for relative_path in source_files:
        full_path = project_dir / relative_path
        try:
            source_code = full_path.read_text(encoding="utf-8", errors="replace")
            entry = analyze_java_class(source_code, relative_path)
            class_name = entry.get("class_name")
            if class_name:
                index[class_name] = entry
        except Exception:
            pass  # Skip unreadable files silently
    return index


# ---------------------------------------------------------------------------
# Extract representative test examples
# ---------------------------------------------------------------------------

_TEST_CATEGORIES = {
    "service": ["service", "Service"],
    "controller": ["controller", "Controller", "resource", "Resource"],
    "repository": ["repository", "Repository", "dao", "Dao"],
}


def extract_test_examples(
    project_path: str, max_examples: int = 3, max_lines: int = 150
) -> list[dict[str, str]]:
    """Extract representative test file examples from the project.

    Picks one test per category (service, controller, repository) when possible,
    then fills with the longest remaining test files.

    Args:
        project_path: Absolute path to the Java project root.
        max_examples: Maximum number of examples to return.
        max_lines: Maximum number of lines per example.

    Returns:
        List of {"path": str, "content": str} dicts (relative paths).
    """
    project_dir = Path(project_path)
    test_root = project_dir / "src" / "test" / "java"
    if not test_root.exists():
        return []

    test_files = list(test_root.rglob("*Test.java")) + list(test_root.rglob("*Tests.java"))
    if not test_files:
        return []

    # Group by category
    categorized: dict[str, Path | None] = dict.fromkeys(_TEST_CATEGORIES)
    remaining: list[Path] = []

    for tf in test_files:
        stem = tf.stem.lower()
        placed = False
        for cat, keywords in _TEST_CATEGORIES.items():
            if categorized[cat] is None and any(kw.lower() in stem for kw in keywords):
                categorized[cat] = tf
                placed = True
                break
        if not placed:
            remaining.append(tf)

    # Build ordered list: categories first, then remaining sorted by size descending
    ordered: list[Path] = [p for p in categorized.values() if p is not None]
    remaining_sorted = sorted(remaining, key=lambda p: p.stat().st_size, reverse=True)
    ordered.extend(remaining_sorted)

    examples: list[dict[str, str]] = []
    seen: set[Path] = set()
    for tf in ordered:
        if tf in seen:
            continue
        seen.add(tf)
        try:
            content = tf.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()[:max_lines]
            try:
                rel = str(tf.relative_to(project_dir))
            except ValueError:
                rel = str(tf)
            examples.append({"path": rel, "content": "\n".join(lines)})
        except Exception:
            continue
        if len(examples) >= max_examples:
            break

    return examples
