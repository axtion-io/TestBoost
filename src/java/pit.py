# SPDX-License-Identifier: Apache-2.0
"""PIT setup: one pinned version, the JUnit 5 plugin, reports of every module.

PIT cannot discover JUnit 5 tests without `pitest-junit5-plugin` as a
*plugin dependency*, and Maven offers no command-line way to add one: the
plugin must be declared in the pom. `testboost pit-setup` declares it (pinned
versions, in the root pom's `<build><plugins>`, inherited by modules);
`mutate`/`check` refuse early with that instruction instead of letting PIT
report "0 tests" or "no test plugin".
"""

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from src.java.pom import pom_child, pom_findall, pom_text

PIT_VERSION = "1.30.2"
JUNIT5_PLUGIN_VERSION = "1.2.3"
PIT_GOAL = "org.pitest:pitest-maven:mutationCoverage"


def _poms(project_path: str) -> list[Path]:
    project = Path(project_path)
    return [p for p in sorted(project.glob("**/pom.xml"))
            if "target" not in p.relative_to(project).parts and ".testboost" not in p.parts]


def _parse(pom: Path) -> ET.Element | None:
    try:
        return ET.parse(pom).getroot()
    except ET.ParseError:
        return None


def _declares(project_path: str, artifact_id: str, *, among: str) -> bool:
    for pom in _poms(project_path):
        root = _parse(pom)
        if root is None:
            continue
        for element in pom_findall(root, among):
            if pom_text(element, "artifactId") == artifact_id:
                return True
    return False


def pit_status(project_path: str) -> dict[str, bool]:
    """What PIT needs and what the poms declare."""
    junit5 = (_declares(project_path, "junit-jupiter", among="dependency")
              or _declares(project_path, "junit-jupiter-api", among="dependency")
              or _declares(project_path, "spring-boot-starter-test", among="dependency"))
    return {
        "pit_declared": _declares(project_path, "pitest-maven", among="plugin"),
        "junit5_plugin_declared": _declares(project_path, "pitest-junit5-plugin", among="dependency"),
        "junit5_tests": junit5,
    }


def setup_problem(project_path: str) -> str | None:
    """Why PIT cannot run on this project as configured (None if it can)."""
    status = pit_status(project_path)
    if status["junit5_tests"] and not status["junit5_plugin_declared"]:
        return ("PIT needs `pitest-junit5-plugin` declared in the pom to run JUnit 5 tests. "
                "Run `testboost pit-setup <project>` (adds pitest-maven "
                f"{PIT_VERSION} + pitest-junit5-plugin {JUNIT5_PLUGIN_VERSION}) and commit the pom.")
    return None


def pit_goal(project_path: str) -> str:
    """The version the pom declares, else TestBoost's pinned one (never Maven's 'latest')."""
    return PIT_GOAL if pit_status(project_path)["pit_declared"] else \
        f"org.pitest:pitest-maven:{PIT_VERSION}:mutationCoverage"


PLUGIN_XML = """<plugin>
  <groupId>org.pitest</groupId>
  <artifactId>pitest-maven</artifactId>
  <version>{pit}</version>
  <dependencies>
    <dependency>
      <groupId>org.pitest</groupId>
      <artifactId>pitest-junit5-plugin</artifactId>
      <version>{junit5}</version>
    </dependency>
  </dependencies>
</plugin>"""


def _indented(block: str, indent: str, unit: str = "  ") -> str:
    """`block` (2-space steps) re-indented with the pom's own step, under `indent`."""
    out = []
    for line in block.splitlines():
        stripped = line.lstrip(" ")
        out.append(indent + unit * ((len(line) - len(stripped)) // 2) + stripped)
    return "\n".join(out)


def _unit(text: str) -> str:
    """The pom's indentation step: that of the first indented element (default 4 spaces)."""
    m = re.search(r"\n([ \t]+)<", text)
    return m.group(1) if m else "    "


def add_pit_plugin(project_path: str) -> str:
    """Declare PIT + the JUnit 5 plugin in the root pom, keeping its formatting.

    Returns what was done ("added", "already declared"). Raises ValueError when
    the pom declares pitest-maven without the JUnit 5 plugin (a human edit).
    """
    pom = Path(project_path) / "pom.xml"
    status = pit_status(project_path)
    if status["pit_declared"]:
        if status["junit5_plugin_declared"] or not status["junit5_tests"]:
            return "already declared"
        raise ValueError("pitest-maven is declared without pitest-junit5-plugin: add it as a "
                         f"<dependency> of that plugin (version {JUNIT5_PLUGIN_VERSION}).")
    text = pom.read_text(encoding="utf-8")
    root = _parse(pom)
    if root is None:
        raise ValueError(f"{pom} is not valid XML")
    plugin = PLUGIN_XML.format(pit=PIT_VERSION, junit5=JUNIT5_PLUGIN_VERSION)
    unit = _unit(text)

    build = pom_child(root, "build")
    # The <build> of the project itself, not one nested in <profiles>.
    build_match = _top_level_build(text)
    if build is not None and build_match and pom_child(build, "plugins") is not None:
        start, end = build_match
        section = text[start:end]
        close = _top_level_plugins_close(section)
        indent = _line_indent(section, close) + unit
        new = section[:close].rstrip() + "\n" + _indented(plugin, indent, unit) + "\n" + \
            _line_indent(section, close) + section[close:]
        text = text[:start] + new + text[end:]
    elif build is not None and build_match:
        start, end = build_match
        section = text[start:end]
        close = section.rindex("</build>")
        indent = _line_indent(section, close) + unit
        block = f"<plugins>\n{_indented(plugin, '  ')}\n</plugins>"
        new = section[:close].rstrip() + "\n" + _indented(block, indent, unit) + "\n" + \
            _line_indent(section, close) + section[close:]
        text = text[:start] + new + text[end:]
    else:
        close = text.rindex("</project>")
        block = f"<build>\n  <plugins>\n{_indented(plugin, '    ')}\n  </plugins>\n</build>"
        text = text[:close].rstrip() + "\n" + _indented(block, unit, unit) + "\n" + text[close:]
    if _parse_text(text) is None:                      # never leave a broken pom
        raise ValueError("could not insert the PIT plugin without breaking the pom")
    pom.write_text(text, encoding="utf-8")
    return "added"


def _parse_text(text: str) -> ET.Element | None:
    try:
        return ET.fromstring(text)
    except ET.ParseError:
        return None


def _line_indent(text: str, pos: int) -> str:
    line_start = text.rfind("\n", 0, pos) + 1
    return re.match(r"[ \t]*", text[line_start:pos]).group(0)


def _depth_spans(text: str, tag: str) -> list[tuple[int, int, int]]:
    """(start, end, depth) of every <tag>…</tag> element, depth = nesting in the document."""
    spans, stack, depth = [], [], 0
    for m in re.finditer(r"<(/?)([\w:.-]+)[^>]*?(/?)>|<!--.*?-->|<\?.*?\?>", text, re.DOTALL):
        if m.group(2) is None:
            continue
        closing, name, selfclosing = m.group(1), m.group(2).split(":")[-1], m.group(3)
        if selfclosing:
            continue
        if not closing:
            depth += 1
            stack.append((name, m.start(), depth))
        else:
            open_name, start, d = stack.pop()
            if open_name == tag:
                spans.append((start, m.end(), d))
            depth -= 1
    return spans


def _top_level_build(text: str) -> tuple[int, int] | None:
    builds = [(s, e) for s, e, d in _depth_spans(text, "build") if d == 2]   # <project><build>
    return builds[0] if builds else None


def _top_level_plugins_close(section: str) -> int:
    """Offset of the `</plugins>` closing <build><plugins> (not pluginManagement's)."""
    spans = [(s, e) for s, e, d in _depth_spans(section, "plugins") if d == 2]
    s, e = spans[0]
    return e - len("</plugins>")
