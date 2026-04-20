# SPDX-License-Identifier: Apache-2.0
"""Java parsing utilities — shared low-level parsers.

No dependencies on other src.* modules.
Used by src.java.class_analyzer and src.test_generation.generate_unit.
"""

from __future__ import annotations

import re
from typing import Any

_PRIMITIVE_TYPES = {
    "int", "long", "short", "byte", "double", "float", "boolean", "char",
    "Integer", "Long", "Short", "Byte", "Double", "Float", "Boolean", "Character",
    "String", "java.lang.String", "java.lang.Integer", "java.lang.Long",
    "java.lang.Double", "java.lang.Float", "java.lang.Boolean",
    "void", "Object",
}


def _is_primitive_type(type_name: str) -> bool:
    clean = type_name.replace("final", "").strip().split("<")[0].strip()
    return clean in _PRIMITIVE_TYPES


def _extract_balanced_parens(text: str, start_pos: int) -> str:
    """Extract content between balanced parentheses starting at start_pos.

    Handles nested parentheses correctly, unlike a simple regex [^)]*.
    For example: @PathVariable("ownerId") int ownerId -> correctly captures full params.
    """
    depth = 0
    content: list[str] = []
    i = start_pos
    while i < len(text):
        c = text[i]
        if c == "(":
            if depth > 0:
                content.append(c)
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return "".join(content)
            content.append(c)
        elif depth > 0:
            content.append(c)
        i += 1
    return "".join(content)


def _parse_parameters(params_str: str) -> list[dict[str, str]]:
    """Parse Java method parameters into structured form."""
    if not params_str or not params_str.strip():
        return []
    params: list[str] = []
    depth = 0
    current = ""
    for char in params_str:
        if char in "<(":
            depth += 1
        elif char in ">)":
            depth -= 1
        elif char == "," and depth == 0:
            if current.strip():
                params.append(current.strip())
            current = ""
            continue
        current += char
    if current.strip():
        params.append(current.strip())
    result = []
    for param in params:
        # Handle annotations like @Valid, @PathVariable, etc.
        param = re.sub(r"@\w+(?:\([^)]*\))?\s*", "", param).strip()
        # Remove 'final' modifier from parameter type
        param = re.sub(r"\bfinal\s+", "", param).strip()
        parts = param.rsplit(None, 1)
        if len(parts) == 2:
            result.append({"type": parts[0], "name": parts[1]})
    return result


def _extract_public_signatures(source_code: str) -> str:
    """Extract public method signatures with full parameter types from Java source."""
    pattern = re.compile(
        r"public\s+(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?"
        r"(\w[\w<>\[\], ]*?)\s+(\w+)\s*\(([^)]*)\)"
        r"(?:\s+throws\s+([\w, ]+))?",
        re.MULTILINE,
    )
    sigs = []
    for m in pattern.finditer(source_code):
        ret = m.group(1).strip()
        name = m.group(2)
        if name in {"if", "while", "for", "switch", "class", "new", "return"}:
            continue
        params = m.group(3).strip()
        throws = f" throws {m.group(4).strip()}" if m.group(4) else ""
        sigs.append(f"  - `{ret} {name}({params}){throws}`")
    return "\n".join(sigs[:20])


def _analyze_jpa_fields(source_code: str) -> dict[str, Any]:
    """Analyze JPA entity fields to detect @GeneratedValue, @Id, and field types.

    This information is critical for generating correct tests that don't call
    setId() on @GeneratedValue fields.
    """
    jpa_info: dict[str, Any] = {
        "id_field": None,
        "id_type": None,
        "has_generated_value": False,
        "generated_value_strategy": None,
        "date_fields": [],
    }

    id_block_pattern = re.compile(
        r'@Id\s*'
        r'(?:@GeneratedValue\s*(?:\(\s*(?:strategy\s*=\s*)?(?:GenerationType\.)?(\w+)\s*\))?\s*)?'
        r'(?:@\w+(?:\([^)]*\))?\s*)*'
        r'(?:private|protected)?\s*'
        r'(\w+)\s+'
        r'(\w+)\s*;',
        re.MULTILINE | re.DOTALL,
    )

    id_match = id_block_pattern.search(source_code)
    if id_match:
        strategy = id_match.group(1)
        id_type = id_match.group(2)
        id_name = id_match.group(3)
        jpa_info["id_field"] = id_name
        jpa_info["id_type"] = id_type
        jpa_info["has_generated_value"] = strategy is not None or "@GeneratedValue" in source_code
        jpa_info["generated_value_strategy"] = strategy
    elif "@GeneratedValue" in source_code:
        jpa_info["has_generated_value"] = True

    date_pat = re.compile(
        r'(?:private|protected)?\s*'
        r'(Date|LocalDate|LocalDateTime|Instant|ZonedDateTime)\s+(\w+)\s*;',
        re.MULTILINE,
    )
    for dm in date_pat.finditer(source_code):
        jpa_info["date_fields"].append({"name": dm.group(2), "type": dm.group(1)})

    return jpa_info
