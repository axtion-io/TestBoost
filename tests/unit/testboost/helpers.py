# SPDX-License-Identifier: Apache-2.0
"""Shared test helpers for the CLI suite.

These replace the per-class copies of the analyze/gaps setup, the
generation-result factory and the mutation-step seeding that used to be
duplicated across test classes.
"""

import argparse
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.lib.session_tracker import get_current_session, update_step_file

ORDER_SERVICE = "src/main/java/com/example/service/OrderService.java"
USER_SERVICE = "src/main/java/com/example/service/UserService.java"
USER_CONTROLLER = "src/main/java/com/example/web/UserController.java"
PAYMENT_SERVICE = "src/main/java/com/example/service/PaymentService.java"

THREE_FILES = [ORDER_SERVICE, USER_CONTROLLER, PAYMENT_SERVICE]


async def setup_gaps(project_path, files=None, run_gaps=True):
    """Run analyze (and optionally gaps) with a fully mocked bridge.

    Creates the listed source files on disk if missing — edge-case
    analysis is silently skipped for files that don't exist, which would
    turn "generate" cases into "deferred" cases.
    """
    from src.lib.cli import _cmd_analyze_async, _cmd_gaps_async

    files = list(files) if files else [ORDER_SERVICE]
    for rel in files:
        f = Path(project_path) / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        if not f.exists():
            f.write_text(f"public class {Path(rel).stem} {{}}", encoding="utf-8")

    mock_context = json.dumps({
        "success": True, "project_type": "spring-boot", "build_system": "maven",
        "java_version": "17", "frameworks": [], "test_frameworks": [],
        "source_structure": {"class_count": len(files), "packages": []},
        "test_structure": {"test_count": 0}, "dependencies": [],
    })
    args = argparse.Namespace(project_path=str(project_path), verbose=False)
    with patch("src.lib.bridge.analyze_project_context", new_callable=AsyncMock, return_value=mock_context), \
         patch("src.lib.bridge.detect_test_conventions", new_callable=AsyncMock, return_value=json.dumps({"success": False})), \
         patch("src.lib.bridge.find_source_files", return_value=files), \
         patch("src.lib.bridge.build_class_index", return_value={}), \
         patch("src.lib.bridge.extract_test_examples", return_value=[]):
        await _cmd_analyze_async(args)
    if run_gaps:
        await _cmd_gaps_async(args)


def gen_result(class_name="OrderService", package="com.example"):
    """A successful generate_adaptive_tests JSON result for one class."""
    return json.dumps({
        "success": True,
        "test_code": (
            f"package {package};\n"
            "import org.junit.jupiter.api.Test;\n"
            f"class {class_name}Test {{\n  @Test\n  void t() {{}}\n}}"
        ),
        "test_file": f"src/test/java/com/example/{class_name}Test.java",
        "test_count": 1,
        "context": {"class_name": class_name, "package": package},
    })


def failing_compile(file_name="OrderServiceTest.java"):
    """A subprocess.run result whose stderr names the generated test file."""
    return MagicMock(
        returncode=1,
        stdout="",
        stderr=f"[ERROR] {file_name}:[5,12] cannot find symbol\n",
    )


def prepare_mutation(project_path, surviving=None):
    """Seed a completed mutation step with surviving mutants; returns the session."""
    if surviving is None:
        surviving = [
            {
                "class": "com.example.OrderService",
                "method": "calculateTotal",
                "mutator": "MATH",
                "line": 42,
                "description": "Replaced + with -",
            },
        ]
    session = get_current_session(str(project_path))
    update_step_file(
        session["session_dir"], "mutation", "completed",
        "# Mutation\n\nDone.",
        data={"surviving_mutants": surviving},
    )
    return session
