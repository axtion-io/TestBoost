# SPDX-License-Identifier: Apache-2.0
"""Lines changed since a git ref, for `check --base`.

Judging a merge request means judging the code it changes: coverage and
mutation score are computed on those lines only, so legacy code does not
drown the signal and PIT only mutates the changed classes.
"""

import re
import subprocess
from pathlib import Path

MAIN_JAVA = "src/main/java/"
_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _git(project_path: str, *args: str) -> str:
    result = subprocess.run(["git", "-C", project_path, *args], capture_output=True, text=True, timeout=60)
    if result.returncode != 0:
        raise ValueError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def parse_diff(diff: str) -> dict[str, set[int]]:
    """`git diff --unified=0` output → {path: added/modified line numbers (new side)}."""
    changed: dict[str, set[int]] = {}
    for chunk in re.split(r"^diff --git ", diff, flags=re.MULTILINE)[1:]:
        target = re.search(r"^\+\+\+ (?:b/)?(.+)$", chunk, re.MULTILINE)
        if not target or target.group(1) == "/dev/null":
            continue                                    # deleted file
        lines = changed.setdefault(target.group(1).strip(), set())
        for m in _HUNK.finditer(chunk):
            start, count = int(m.group(1)), int(m.group(2) if m.group(2) is not None else 1)
            lines.update(range(start, start + count))
    return {path: lines for path, lines in changed.items() if lines}


def changed_lines(project_path: str, base: str) -> dict[str, set[int]]:
    """Main Java source lines changed since the merge base with `base`, working tree
    included (paths relative to the project; untracked new files count entirely).

    The merge base, not `base` itself: when the target branch moved on, its new
    commits are not this change's lines (what `git diff base...HEAD` shows).
    """
    _git(project_path, "rev-parse", "--verify", f"{base}^{{commit}}")
    try:
        fork_point = _git(project_path, "merge-base", base, "HEAD").strip()
    except ValueError:                                   # unrelated histories: compare with base
        fork_point = base
    diff = _git(project_path, "diff", "--unified=0", "--no-color", "--no-ext-diff", "--relative",
                fork_point, "--", ".")
    changed = parse_diff(diff)
    for rel in _git(project_path, "ls-files", "--others", "--exclude-standard").splitlines():
        path = Path(project_path) / rel
        if rel.endswith(".java") and path.is_file():
            changed[rel] = set(range(1, len(path.read_text(encoding="utf-8", errors="replace").splitlines()) + 1))
    return {p: lines for p, lines in changed.items() if p.endswith(".java") and _is_main(p)}


def _is_main(path: str) -> bool:
    return path.startswith(MAIN_JAVA) or f"/{MAIN_JAVA}" in path


def source_key(path: str) -> str:
    """'engine/src/main/java/a/b/C.java' → 'a/b/C.java' (how PIT names a source)."""
    return path.split(MAIN_JAVA, 1)[1]


def class_name(path: str) -> str:
    """'engine/src/main/java/a/b/C.java' → 'a.b.C'."""
    return source_key(path)[: -len(".java")].replace("/", ".")
