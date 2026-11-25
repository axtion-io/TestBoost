# SPDX-License-Identifier: Apache-2.0
"""`testboost check`: the measure, scoped to a diff, rendered for a merge request.

The real Maven run is in tests/e2e/test_check_maven.py; here, the rules that
decide the verdict, on fixed data.
"""

import subprocess

import pytest

from src.java.diff import changed_lines, class_name, parse_diff, source_key
from src.lib import equivalents
from src.lib.commands.check_cmd import (
    REPORT_MARKER,
    coverage_summary,
    failing_tests,
    mutation_summary,
    render_report,
)

DIFF = """diff --git a/engine/src/main/java/a/B.java b/engine/src/main/java/a/B.java
index 1..2 100644
--- a/engine/src/main/java/a/B.java
+++ b/engine/src/main/java/a/B.java
@@ -10,0 +11,2 @@ class B {
+  int x;
+  int y;
@@ -20 +22 @@ class B {
-  old
+  new
@@ -30,3 +33,0 @@ class B {
-  removed
diff --git a/README.md b/README.md
deleted file mode 100644
--- a/README.md
+++ /dev/null
@@ -1 +0,0 @@
-x
"""
B = "engine/src/main/java/a/B.java"
COV = {B: {"lines": {11: "covered", 12: "missed", 22: "partial", 40: "missed"}},
       "engine/src/main/java/a/C.java": {"lines": {5: "missed"}}}


class TestDiff:
    def test_added_and_modified_lines_of_the_new_side(self):
        assert parse_diff(DIFF) == {B: {11, 12, 22}}           # pure deletions and deleted files: none

    def test_paths_and_class_names(self):
        assert source_key(B) == "a/B.java" and class_name(B) == "a.B"

    def test_on_a_real_repository_with_an_untracked_file(self, tmp_path):
        def git(*a):
            subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                           check=True, capture_output=True)
        src = tmp_path / "src/main/java/a"
        src.mkdir(parents=True)
        (src / "B.java").write_text("class B {\n}\n")
        (tmp_path / "src/test").mkdir(parents=True)
        git("init", "-q"); git("add", "-A"); git("commit", "-qm", "base")   # noqa: E702
        (src / "B.java").write_text("class B {\n  int x;\n}\n")
        (src / "New.java").write_text("class New {\n}\n")
        (tmp_path / "src/test/BTest.java").write_text("class BTest {}\n")     # not main code
        assert changed_lines(str(tmp_path), "HEAD") == {
            "src/main/java/a/B.java": {2}, "src/main/java/a/New.java": {1, 2}}

    def test_unknown_ref_is_an_error(self, tmp_path):
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        with pytest.raises(ValueError, match="rev-parse"):
            changed_lines(str(tmp_path), "origin/nope")


class TestCoverage:
    def test_whole_project(self):
        summary = coverage_summary(COV, None)
        assert (summary["covered"], summary["lines"], summary["pct"]) == (2, 5, 40.0)

    def test_only_the_changed_executable_lines(self):
        summary = coverage_summary(COV, {B: {11, 12, 22, 13}})   # 13: blank or comment, not executable
        assert (summary["covered"], summary["lines"]) == (2, 3)   # partial line 22 counts as covered…
        assert summary["files"][B]["partial"] == [22]             # …and is listed
        assert summary["files"][B]["uncovered"] == [12]
        assert "engine/src/main/java/a/C.java" not in summary["files"]

    def test_nothing_executable_changed(self):
        assert coverage_summary(COV, {B: {1}})["pct"] is None


def _mutant(line, status, source="a/B.java"):
    return {"class": "a.B", "method": "m", "line": line, "mutator": "M", "description": f"d{line}",
            "status": status, "source_file": source}


class TestMutation:
    MUTANTS = [_mutant(11, "KILLED"), _mutant(12, "SURVIVED"), _mutant(22, "TIMED_OUT"),
               _mutant(22, "NO_COVERAGE"), _mutant(40, "SURVIVED")]

    def test_scope_and_pit_convention(self, tmp_path):
        result = mutation_summary(str(tmp_path), self.MUTANTS, {B: {11, 12, 22}})
        assert (result["total"], result["detected"], result["score"]) == (4, 2, 50.0)
        assert [m["line"] for m in result["survivors"]] == [12, 22]   # no-coverage is not detected

    def test_declared_equivalents_leave_the_denominator(self, tmp_path):
        survivor = _mutant(12, "SURVIVED")
        equivalents.declare(str(tmp_path), [survivor], [equivalents.mutant_id(survivor)],
                            "the value is overwritten before use")
        result = mutation_summary(str(tmp_path), self.MUTANTS, {B: {11, 12, 22}})
        assert (result["equivalent"], result["score"]) == (1, round(200 / 3, 1))


class TestReport:
    def _data(self, survivors):
        mutation = {"score": 50.0, "total": 4, "detected": 2, "equivalent": 0,
                    "survivors": equivalents.with_ids(survivors)}
        return {"base": "origin/main", "min_coverage": 80, "min_mutation": 80, "passed": False,
                "coverage": coverage_summary(COV, {B: {11, 12, 22}}), "mutation": mutation}

    def test_mr_comment(self):
        md = render_report(self._data([_mutant(12, "SURVIVED"), _mutant(12, "SURVIVED"),
                                       _mutant(22, "NO_COVERAGE")]))
        assert md.startswith("## TestBoost check — FAILED")
        assert "lines changed since `origin/main`" in md
        assert "| Line coverage | 66.7% (2/3 lines) | ❌ (min 80%) |" in md
        assert "d12 (×2)" in md                                    # identical mutants grouped
        assert "1 more mutant(s) are on lines no test runs" in md
        assert f"testboost equivalent . {equivalents.mutant_id(_mutant(12, 'SURVIVED'))}" in md
        assert md.rstrip().endswith(REPORT_MARKER)                 # the sticky comment's anchor


SUREFIRE = """[INFO] Tests run: 3, Failures: 0, Errors: 0, Skipped: 0, Time elapsed: 0.1 s -- in a.BTest
[ERROR] Tests run: 2, Failures: 1, Errors: 0, Skipped: 0, Time elapsed: 0.1 s <<< FAILURE! -- in a.CTest
[INFO] Results:
[ERROR] Tests run: 5, Failures: 1, Errors: 0, Skipped: 0
[INFO] Tests run: 4, Failures: 0, Errors: 1, Skipped: 0
"""


def test_failing_tests_are_counted_from_module_totals_only():
    assert failing_tests(SUREFIRE) == 2                            # per-class lines are ignored
    assert failing_tests("[INFO] Tests run: 5, Failures: 0, Errors: 0, Skipped: 1\n") == 0


def test_the_target_branch_moving_on_is_not_this_change(tmp_path):
    def git(*a):
        subprocess.run(["git", "-C", str(tmp_path), "-c", "user.name=t", "-c", "user.email=t@t", *a],
                       check=True, capture_output=True)
    src = tmp_path / "src/main/java/a"
    src.mkdir(parents=True)
    (src / "A.java").write_text("class A {\n}\n")
    (src / "B.java").write_text("class B {\n}\n")
    git("init", "-q", "-b", "main"); git("add", "-A"); git("commit", "-qm", "base")      # noqa: E702
    git("checkout", "-qb", "feature")
    (src / "B.java").write_text("class B {\n  int mine;\n}\n")
    git("commit", "-qam", "feature")
    git("checkout", "-q", "main")
    (src / "A.java").write_text("class A {\n  int theirs;\n}\n")
    git("commit", "-qam", "main moved on")
    git("checkout", "-q", "feature")
    assert changed_lines(str(tmp_path), "main") == {"src/main/java/a/B.java": {2}}
