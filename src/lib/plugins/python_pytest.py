# SPDX-License-Identifier: Apache-2.0
"""Python pytest plugin for TestBoost.

Uses stdlib ast to analyze Python source files — zero external dependencies.
"""

import ast
from pathlib import Path

from src.lib.plugins.base import TechnologyPlugin

# Directories excluded from source discovery
_EXCLUDED_DIRS = {
    "tests", "test", "venv", ".venv", "site-packages",
    ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    "__pycache__", ".git", ".hg",
}

# Filenames excluded from source discovery
_EXCLUDED_FILENAMES = {"conftest.py", "__init__.py"}


class PythonPytestPlugin(TechnologyPlugin):
    """Plugin for Python projects using pytest for testing.

    Detection: checks for pyproject.toml, setup.py, or setup.cfg in the
    project root. Source analysis uses stdlib ast — no external dependencies.
    """

    @property
    def identifier(self) -> str:
        return "python-pytest"

    @property
    def description(self) -> str:
        return "Python projects using pytest for testing"

    @property
    def detection_patterns(self) -> list[str]:
        return ["pyproject.toml", "setup.py", "setup.cfg"]

    @property
    def prompt_template_dir(self) -> str:
        return "config/prompts/testing/python_pytest"

    # ------------------------------------------------------------------
    # Source discovery
    # ------------------------------------------------------------------

    def find_source_files(self, project_path: Path) -> list[str]:
        """Discover testable Python source files.

        Excludes test files (test_*.py, *_test.py), conftest.py, __init__.py,
        and common non-source directories.
        """
        project_path = Path(project_path)
        result: list[str] = []

        for py_file in project_path.rglob("*.py"):
            # Skip excluded directories anywhere in the path
            parts = py_file.relative_to(project_path).parts
            if any(part in _EXCLUDED_DIRS for part in parts):
                continue

            name = py_file.name
            if name in _EXCLUDED_FILENAMES:
                continue
            if name.startswith("test_") or name.endswith("_test.py"):
                continue

            relative = str(py_file.relative_to(project_path)).replace("\\", "/")
            result.append(relative)

        result.sort()
        return result

    def classify_source_file(self, relative_path: str) -> str:
        """Classify a Python source file using ast.

        Returns:
            'class' if the file defines top-level classes,
            'function' if it defines only module-level functions,
            'module' otherwise.
        """
        # We need the absolute path — caller should pass it, but we fall back
        # to attempting a relative read from CWD
        file_path = Path(relative_path)
        if not file_path.exists():
            return "module"

        try:
            source = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(file_path))
        except SyntaxError:
            return "module"

        has_classes = any(isinstance(node, ast.ClassDef) for node in ast.walk(tree)
                          if isinstance(node, ast.ClassDef) and _is_top_level(tree, node))
        if has_classes:
            return "class"

        has_functions = any(isinstance(node, ast.FunctionDef) for node in ast.walk(tree)
                            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
                            and _is_top_level(tree, node))
        if has_functions:
            return "function"

        return "module"

    # ------------------------------------------------------------------
    # Test file naming
    # ------------------------------------------------------------------

    def test_file_name(self, source_relative_path: str) -> str:
        """Derive the test file path for a Python source file.

        src/services/user_service.py  → tests/services/test_user_service.py
        my_module.py                  → tests/test_my_module.py
        src/foo/bar.py                → tests/foo/test_bar.py
        """
        normalized = source_relative_path.replace("\\", "/")
        path = Path(normalized)
        stem = path.stem

        # Strip leading src/ component if present
        parts = list(path.parts)
        if parts and parts[0] == "src":
            parts = parts[1:]

        # Drop the filename — we'll rebuild it with test_ prefix
        if len(parts) > 1:
            sub_dirs = "/".join(parts[:-1])
            return f"tests/{sub_dirs}/test_{stem}.py"
        else:
            return f"tests/test_{stem}.py"

    def test_file_pattern(self) -> list[str]:
        return ["**/test_*.py", "**/*_test.py"]

    # ------------------------------------------------------------------
    # Build commands
    # ------------------------------------------------------------------

    def validation_command(self, project_path: Path, session_config: dict) -> list[str]:
        """Syntax-check the generated test file with py_compile."""
        return ["python", "-m", "py_compile", "{test_file}"]

    def test_run_command(self, project_path: Path, session_config: dict) -> list[str]:
        """Run the generated test file with pytest."""
        return ["python", "-m", "pytest", "--tb=short", "--no-header", "{test_file}"]

    # ------------------------------------------------------------------
    # Generation context
    # ------------------------------------------------------------------

    def build_generation_context(self, project_path: Path, source_file: str) -> dict:
        """Build LLM context by parsing the Python source file with ast."""
        project_path = Path(project_path)

        # Resolve source file path
        source_path = Path(source_file)
        if not source_path.is_absolute():
            source_path = project_path / source_file

        try:
            source_code = source_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            source_code = ""

        # Parse with ast
        classes: list[dict] = []
        functions: list[dict] = []
        imports: list[str] = []
        tree: ast.Module | None = None

        try:
            tree = ast.parse(source_code, filename=str(source_path))
            classes = _extract_classes(tree, source_code)
            functions = _extract_top_level_functions(tree, source_code)
            imports = _extract_imports(tree)
        except SyntaxError:
            pass

        # Primary class/module name
        if classes:
            primary_name = classes[0]["name"]
            class_type = "class"
        elif functions:
            primary_name = source_path.stem
            class_type = "function"
        else:
            primary_name = source_path.stem
            class_type = "module"

        # Scan tests/ for existing examples
        existing_tests = _collect_test_examples(project_path)

        return {
            "source_code": source_code,
            "class_name": primary_name,
            "class_type": class_type,
            "dependencies": imports,
            "existing_tests": existing_tests,
            "conventions": {},
            # Python-specific extras
            "classes": classes,
            "functions": functions,
            "type_hints": _has_type_hints(tree) if tree else False,
            "async_functions": _has_async_functions(tree) if tree else False,
        }


# ---------------------------------------------------------------------------
# Private AST helpers
# ---------------------------------------------------------------------------

def _is_top_level(tree: ast.Module, node: ast.AST) -> bool:
    """Return True if node is a direct child of the module (not nested)."""
    return node in tree.body


def _extract_classes(tree: ast.Module, source_code: str) -> list[dict]:
    """Extract top-level class definitions."""
    result = []
    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [ast.unparse(b) for b in node.bases]
        decorators = [ast.unparse(d) for d in node.decorator_list]
        methods = []
        for item in node.body:
            if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef):
                methods.append(_extract_function_info(item))

        docstring = ast.get_docstring(node) or ""
        result.append({
            "name": node.name,
            "bases": bases,
            "decorators": decorators,
            "methods": methods,
            "docstring": docstring,
        })
    return result


def _extract_top_level_functions(tree: ast.Module, source_code: str) -> list[dict]:
    """Extract top-level (module-level) function definitions."""
    return [
        _extract_function_info(node)
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]


def _extract_function_info(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict:
    """Extract signature info from a function/method node."""
    params = []
    for arg in node.args.args:
        param: dict = {"name": arg.arg}
        if arg.annotation:
            param["type"] = ast.unparse(arg.annotation)
        params.append(param)

    return_type = ast.unparse(node.returns) if node.returns else None
    docstring = ast.get_docstring(node) or ""
    decorators = [ast.unparse(d) for d in node.decorator_list]
    is_async = isinstance(node, ast.AsyncFunctionDef)

    return {
        "name": node.name,
        "params": params,
        "return_type": return_type,
        "docstring": docstring,
        "decorators": decorators,
        "is_async": is_async,
    }


def _extract_imports(tree: ast.Module) -> list[str]:
    """Extract import statements as strings (for mock target identification)."""
    imports = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append(f"{module}.{alias.name}")
    return imports


def _has_type_hints(tree: ast.Module) -> bool:
    """Return True if the module uses type annotations."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.returns or any(a.annotation for a in node.args.args):
                return True
        if isinstance(node, ast.AnnAssign):
            return True
    return False


def _has_async_functions(tree: ast.Module) -> bool:
    """Return True if the module contains async function definitions."""
    return any(isinstance(node, ast.AsyncFunctionDef) for node in ast.walk(tree))


def _collect_test_examples(project_path: Path, max_examples: int = 3, max_lines: int = 100) -> list[str]:
    """Collect short test file examples from the tests/ directory."""
    tests_dir = project_path / "tests"
    if not tests_dir.exists():
        return []

    examples = []
    for test_file in sorted(tests_dir.rglob("test_*.py"))[:max_examples]:
        try:
            lines = test_file.read_text(encoding="utf-8", errors="replace").splitlines()
            examples.append("\n".join(lines[:max_lines]))
        except OSError:
            pass
    return examples
