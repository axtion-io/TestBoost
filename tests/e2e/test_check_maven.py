# SPDX-License-Identifier: Apache-2.0
"""`testboost check` on examples/java-demo with the REAL Maven, JaCoCo and PIT.

Nothing is mocked: every bug the agent benchmarks found was at the seam with
Maven/PIT (stale reports, missing JUnit 5 plugin, a whole-suite timeout),
where a mocked `subprocess` passes. Skipped when mvn/java are absent; the
`maven` CI job installs them.
"""

import argparse
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.lib.commands.check_cmd import EXIT_BELOW, EXIT_PASS, cmd_check
from src.lib.commands.mutation_cmd import cmd_equivalent

DEMO = Path(__file__).resolve().parents[2] / "examples" / "java-demo"
PROMO = "src/main/java/io/testboost/demo/PromoCode.java"

pytestmark = [
    pytest.mark.e2e, pytest.mark.maven, pytest.mark.slow,
    pytest.mark.skipif(not (shutil.which("mvn") and shutil.which("java") and shutil.which("git")),
                       reason="needs mvn, java and git"),
]

PROMO_TEST = """package io.testboost.demo;

import static org.junit.jupiter.api.Assertions.assertEquals;

import org.junit.jupiter.api.Test;

class PromoCodeTest {
    @Test
    void discountIsRoundedDown() {
        assertEquals(850, new PromoCode("SPRING", 15).apply(1000));
        assertEquals(850, new PromoCode("SPRING", 15).apply(999));
    }

    @Test
    void neverBelowOneEuro() {
        assertEquals(100, new PromoCode("HALF", 50).apply(150));
        assertEquals(101, new PromoCode("HALF", 50).apply(202));
    }
}
"""


def _git(repo, *args):
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                   check=True, capture_output=True)


def _check(project, **kw):
    args = argparse.Namespace(project_path=str(project), base=None, min_coverage=80.0, min_mutation=80.0,
                              no_mutation=False, target_tests=None)
    for k, v in kw.items():
        setattr(args, k, v)
    rc = cmd_check(args)
    return rc, json.loads((project / ".testboost/check/check.json").read_text())


@pytest.fixture
def demo(tmp_path):
    project = tmp_path / "java-demo"
    shutil.copytree(DEMO, project, ignore=shutil.ignore_patterns("target", ".testboost"))
    _git(project, "init", "-q")
    _git(project, "add", "-A")
    _git(project, "commit", "-qm", "base")
    return project


def test_whole_project_is_measured_not_declared(demo):
    rc, data = _check(demo)
    assert rc == EXIT_BELOW                                   # the demo is deliberately under-tested
    assert data["coverage"]["files"][PROMO]["covered"] == 0   # PromoCode has no test at all
    shipping = data["mutation"]["survivors"]
    assert any(m["status"] == "SURVIVED" and m["source_file"].endswith("Shipping.java") for m in shipping)


def test_a_change_is_judged_on_its_lines_then_passes_once_tested(demo):
    promo = demo / PROMO
    promo.write_text(promo.read_text().replace(
        "        return amountCents - amountCents * percent / 100;",
        "        int discounted = amountCents - amountCents * percent / 100;\n"
        "        return Math.max(discounted, 100);"))

    rc, data = _check(demo, base="HEAD")
    assert rc == EXIT_BELOW
    assert set(data["coverage"]["files"]) == {PROMO}           # Shipping's gaps are not this change's
    assert data["coverage"]["files"][PROMO]["uncovered"] == [30, 31]

    test = demo / "src/test/java/io/testboost/demo/PromoCodeTest.java"
    test.write_text(PROMO_TEST)
    rc, data = _check(demo, base="HEAD")
    assert data["coverage"]["pct"] == 100.0
    assert rc == EXIT_PASS, data["mutation"]


def test_equivalent_declared_from_a_check_leaves_the_score(demo):
    _rc, data = _check(demo, no_mutation=False)
    survivor = next(m for m in data["mutation"]["survivors"] if m["status"] == "SURVIVED")
    assert cmd_equivalent(argparse.Namespace(project_path=str(demo), ids=[survivor["id"]],
                                             reason="demo: declared to check the effective score",
                                             remove=False)) == 0
    _rc, after = _check(demo)
    assert after["mutation"]["equivalent"] >= 1
    assert survivor["id"] not in {m["id"] for m in after["mutation"]["survivors"]}


def test_a_red_suite_is_a_measure_error_not_a_score(demo, capsys):
    (demo / "src/test/java/io/testboost/demo/RedTest.java").write_text(
        "package io.testboost.demo;\nimport org.junit.jupiter.api.Test;\n"
        "import static org.junit.jupiter.api.Assertions.assertEquals;\n"
        "class RedTest { @Test void red() { assertEquals(1, Shipping.costCents(1, 1, false)); } }\n")
    from src.lib.commands.check_cmd import EXIT_ERROR
    args = argparse.Namespace(project_path=str(demo), base=None, min_coverage=80.0, min_mutation=80.0,
                              no_mutation=False, target_tests=None)
    assert cmd_check(args) == EXIT_ERROR
    assert "1 test(s) fail without any mutation" in capsys.readouterr().err   # before PIT
    assert not (demo / ".testboost/check/check.json").exists()
