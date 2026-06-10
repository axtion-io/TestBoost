#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Dead-code finder for the TestBoost repository.

Two complementary AST-based passes, designed to be conservative (a name
collision makes a symbol look alive; we prefer false negatives to false
positives):

1. MODULE REACHABILITY — builds the import graph and walks it from the
   real entry points (testboost.__main__ → src.lib.cli, the FastAPI
   webhook, the dev scripts). Modules never reached are dead as a whole,
   no matter what their symbols look like.

2. SYMBOL REFERENCES — indexes every definition (functions, classes,
   methods, module-level constants) and every reference (Name loads,
   attribute names, import aliases, string literals for dynamic lookups).
   A symbol with no reference outside its own definition is reported as
   DEAD; a symbol referenced only from tests/ is reported as TEST-ONLY
   (production code kept alive solely by its tests).

Usage:
    python scripts/find_dead_code.py [--json]
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

PROD_DIRS = ["src", "testboost", "tools"]
TEST_DIRS = ["tests"]
SCRIPT_DIRS = ["scripts"]

# Reachability roots: (module qualname, why)
ROOT_MODULES = [
    ("testboost.__main__", "python -m testboost"),
    ("webhook", "uvicorn webhook:app (tools/gitlab-webhook)"),
]

# Names that are alive by convention even with no in-repo reference
IGNORED_NAMES = {
    "main",          # entry point
    "app",           # uvicorn target
    "__init__", "__main__",
}


def _iter_py_files(dirs: list[str]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        base = REPO / d
        if base.exists():
            out.extend(p for p in base.rglob("*.py") if "__pycache__" not in p.parts)
    return sorted(out)


def _module_name(path: Path) -> str:
    """Best-effort dotted module name for a repo file."""
    rel = path.relative_to(REPO)
    parts = list(rel.with_suffix("").parts)
    # tools/gitlab-webhook/webhook.py runs as a top-level module "webhook"
    if parts[0] == "tools":
        return parts[-1]
    if parts[0] == "scripts":
        return parts[-1]
    return ".".join(parts)


@dataclass
class Definition:
    name: str
    qualname: str        # Class.method for methods
    kind: str            # function / method / class / constant
    file: Path
    lineno: int
    end_lineno: int
    decorators: list[str] = field(default_factory=list)


class DefCollector(ast.NodeVisitor):
    def __init__(self, file: Path):
        self.file = file
        self.defs: list[Definition] = []
        self._class_stack: list[str] = []

    def _decorator_names(self, node) -> list[str]:
        names = []
        for dec in getattr(node, "decorator_list", []):
            names.append(ast.unparse(dec))
        return names

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defs.append(Definition(
            node.name, node.name, "class", self.file,
            node.lineno, node.end_lineno or node.lineno,
            self._decorator_names(node),
        ))
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _visit_func(self, node) -> None:
        kind = "method" if self._class_stack else "function"
        qual = ".".join([*self._class_stack, node.name])
        self.defs.append(Definition(
            node.name, qual, kind, self.file,
            node.lineno, node.end_lineno or node.lineno,
            self._decorator_names(node),
        ))
        self.generic_visit(node)

    visit_FunctionDef = _visit_func
    visit_AsyncFunctionDef = _visit_func

    def visit_Assign(self, node: ast.Assign) -> None:
        # Module-level UPPER_CASE constants only
        if not self._class_stack:
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id.isupper():
                    self.defs.append(Definition(
                        tgt.id, tgt.id, "constant", self.file,
                        node.lineno, node.end_lineno or node.lineno,
                    ))
        self.generic_visit(node)


class RefCollector(ast.NodeVisitor):
    """Collect every identifier that could keep a symbol alive."""

    def __init__(self):
        self.refs: list[tuple[str, int]] = []      # (name, lineno)
        self.imports: list[tuple[str, str]] = []   # (module, imported name)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load | ast.Del):
            self.refs.append((node.id, node.lineno))
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self.refs.append((node.attr, node.lineno))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, "*"))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        mod = node.module or ""
        for alias in node.names:
            self.imports.append((mod, alias.name))
            # ruff F401 guarantees imports are used, so the import itself
            # counts as a reference to the original (possibly aliased) name
            self.refs.append((alias.name, node.lineno))
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        # String literals keep dynamic lookups alive: getattr(x, "name"),
        # commands dict keys, plugin ids, subprocess module names…
        if isinstance(node.value, str) and node.value.isidentifier():
            self.refs.append((node.value, node.lineno))
        self.generic_visit(node)


def parse_all(files: list[Path]):
    trees = {}
    for f in files:
        try:
            trees[f] = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError as e:
            print(f"WARN: cannot parse {f}: {e}", file=sys.stderr)
    return trees


def module_reachability(trees, all_files):
    """Walk the import graph from ROOT_MODULES; return unreachable modules."""
    mod_by_name = { _module_name(f): f for f in all_files }
    imports_of: dict[str, set[str]] = defaultdict(set)

    for f, tree in trees.items():
        me = _module_name(f)
        rc = RefCollector()
        rc.visit(tree)
        for mod, name in rc.imports:
            # "from src.lib import cli" → src.lib.cli ; "import src.lib.cli"
            for candidate in (mod, f"{mod}.{name}" if mod else name):
                if candidate in mod_by_name:
                    imports_of[me].add(candidate)
        # package __init__ pulls the package dir in
        if me.endswith("__init__"):
            pkg = me.rsplit(".", 1)[0]
            imports_of[pkg + ".__init__"] |= imports_of.get(me, set())

    reachable: set[str] = set()
    stack = [m for m, _ in ROOT_MODULES if m in mod_by_name]
    # scripts are their own roots (dev tools, run directly)
    stack += [_module_name(f) for f in all_files if f.parts[len(REPO.parts)] == "scripts"]
    while stack:
        m = stack.pop()
        if m in reachable:
            continue
        reachable.add(m)
        # importing a module implies importing its package __init__s
        parts = m.split(".")
        for i in range(1, len(parts)):
            init = ".".join(parts[:i]) + ".__init__"
            if init in mod_by_name and init not in reachable:
                stack.append(init)
        stack.extend(imports_of.get(m, ()))

    unreachable = [
        (m, f) for m, f in sorted(mod_by_name.items())
        if m not in reachable and not m.endswith("__init__")
    ]
    return unreachable, reachable


def is_test_path(f: Path) -> bool:
    return "tests" in f.relative_to(REPO).parts


def analyze():
    prod_files = _iter_py_files(PROD_DIRS)
    test_files = _iter_py_files(TEST_DIRS)
    script_files = _iter_py_files(SCRIPT_DIRS)
    all_files = prod_files + test_files + script_files

    trees = parse_all(all_files)

    # ---- pass 1: module reachability (production modules only) ----
    prod_trees = {f: t for f, t in trees.items() if f in prod_files or f in script_files}
    unreachable_modules, _ = module_reachability(prod_trees, prod_files + script_files)

    # ---- pass 2: symbol references ----
    defs: list[Definition] = []
    for f in prod_files:
        if f not in trees:
            continue
        dc = DefCollector(f)
        dc.visit(trees[f])
        defs.extend(dc.defs)

    # references per file
    refs_by_file: dict[Path, list[tuple[str, int]]] = {}
    for f, tree in trees.items():
        rc = RefCollector()
        rc.visit(tree)
        refs_by_file[f] = rc.refs

    # non-Python files can keep symbols alive too (yml templates, md docs
    # call CLI subcommands, etc.) — only string-match identifiers
    extra_refs: set[str] = set()
    for pattern in ("*.yml", "*.yaml", "*.sh", "*.toml", "*.ps1"):
        for f in REPO.rglob(pattern):
            if ".git" in f.parts or "node_modules" in f.parts:
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for d in {d.name for d in defs}:
                if d in text:
                    extra_refs.add(d)

    dead, test_only = [], []
    for d in defs:
        if d.name.startswith("__") and d.name.endswith("__"):
            continue
        if d.name in IGNORED_NAMES:
            continue
        if any("app." in dec or "pytest" in dec for dec in d.decorators):
            continue  # FastAPI routes, fixtures

        prod_hit = False
        test_hit = False
        for f, refs in refs_by_file.items():
            for name, lineno in refs:
                if name != d.name:
                    continue
                # ignore references inside the definition's own body
                if f == d.file and d.lineno <= lineno <= d.end_lineno:
                    continue
                if is_test_path(f):
                    test_hit = True
                else:
                    prod_hit = True
            if prod_hit:
                break
        if not prod_hit and d.name in extra_refs:
            prod_hit = True

        if not prod_hit and not test_hit:
            dead.append(d)
        elif not prod_hit:
            test_only.append(d)

    return unreachable_modules, dead, test_only


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    unreachable, dead, test_only = analyze()

    if args.json:
        print(json.dumps({
            "unreachable_modules": [m for m, _ in unreachable],
            "dead": [f"{d.file.relative_to(REPO)}:{d.lineno} {d.kind} {d.qualname}" for d in dead],
            "test_only": [f"{d.file.relative_to(REPO)}:{d.lineno} {d.kind} {d.qualname}" for d in test_only],
        }, indent=2))
        return 0

    print("=" * 72)
    print(f"UNREACHABLE MODULES ({len(unreachable)}) — never imported from any entry point")
    print("=" * 72)
    for _m, f in unreachable:
        print(f"  {f.relative_to(REPO)}")

    print()
    print("=" * 72)
    print(f"DEAD SYMBOLS ({len(dead)}) — no reference anywhere (prod, tests, configs)")
    print("=" * 72)
    for d in sorted(dead, key=lambda d: (str(d.file), d.lineno)):
        print(f"  {d.file.relative_to(REPO)}:{d.lineno:<5} {d.kind:<9} {d.qualname}")

    print()
    print("=" * 72)
    print(f"TEST-ONLY SYMBOLS ({len(test_only)}) — production code referenced only by tests")
    print("=" * 72)
    for d in sorted(test_only, key=lambda d: (str(d.file), d.lineno)):
        print(f"  {d.file.relative_to(REPO)}:{d.lineno:<5} {d.kind:<9} {d.qualname}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
