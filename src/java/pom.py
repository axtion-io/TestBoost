# SPDX-License-Identifier: Apache-2.0
"""Namespace-agnostic pom.xml lookups.

Real POMs declare `xmlns="http://maven.apache.org/POM/4.0.0"`, hand-written
fixtures often do not. The former `find("m:x", ns) or find("x")` idiom was
wrong: an ElementTree Element is falsy when it has no children, so a found
leaf (`<java.version>`, `<activeByDefault>`, `<id>`) was discarded and the
non-namespaced lookup returned None on every real POM.
"""

from xml.etree.ElementTree import Element

POM_NAMESPACE = "http://maven.apache.org/POM/4.0.0"


def pom_child(parent: Element | None, tag: str) -> Element | None:
    """Direct child `tag` of `parent`, with or without the POM namespace."""
    if parent is None:
        return None
    found = parent.find(f"{{{POM_NAMESPACE}}}{tag}")
    return found if found is not None else parent.find(tag)


def pom_text(parent: Element | None, tag: str) -> str | None:
    """Stripped text of child `tag`, or None when absent or empty."""
    child = pom_child(parent, tag)
    if child is None or not child.text or not child.text.strip():
        return None
    return child.text.strip()


def pom_findall(root: Element, tag: str) -> list[Element]:
    """All descendants named `tag`, with or without the POM namespace."""
    return root.findall(f".//{{{POM_NAMESPACE}}}{tag}") or root.findall(f".//{tag}")
