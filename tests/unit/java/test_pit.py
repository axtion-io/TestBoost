# SPDX-License-Identifier: Apache-2.0
"""PIT setup (`testboost pit-setup`): JUnit 5 projects need pitest-junit5-plugin as a
*plugin dependency*, which only the pom can declare. The edit keeps the pom's
formatting, goes in the project's own <build><plugins> (inherited by modules), never
in <pluginManagement> or a profile, and is idempotent."""

import xml.etree.ElementTree as ET

import pytest

from src.java.pit import JUNIT5_PLUGIN_VERSION, PIT_VERSION, add_pit_plugin, pit_goal, setup_problem

NS = 'xmlns="http://maven.apache.org/POM/4.0.0"'
JUPITER = "<dependencies><dependency><artifactId>junit-jupiter</artifactId></dependency></dependencies>"


def _write(tmp_path, body, ns=NS):
    (tmp_path / "pom.xml").write_text(f'<?xml version="1.0"?>\n<project {ns}>\n    {JUPITER}\n{body}</project>\n')
    return tmp_path / "pom.xml"


def _build_plugins(pom):
    root = ET.parse(pom).getroot()
    q = lambda t: f"{{http://maven.apache.org/POM/4.0.0}}{t}"  # noqa: E731
    return [p.findtext(q("artifactId")) for p in root.find(q("build")).find(q("plugins"))]


@pytest.mark.parametrize("body", [
    "",                                                                       # no <build>
    "    <build>\n        <finalName>x</finalName>\n    </build>\n",           # <build> without <plugins>
    ("    <build>\n        <pluginManagement>\n            <plugins>\n"
     "                <plugin><artifactId>managed</artifactId></plugin>\n            </plugins>\n"
     "        </pluginManagement>\n        <plugins>\n"
     "            <plugin><artifactId>surefire</artifactId></plugin>\n        </plugins>\n    </build>\n"),
])
def test_declared_in_the_project_build_plugins(tmp_path, body):
    pom = _write(tmp_path, body)
    assert setup_problem(str(tmp_path)) is not None
    assert add_pit_plugin(str(tmp_path)) == "added"
    assert "pitest-maven" in _build_plugins(pom)
    assert setup_problem(str(tmp_path)) is None
    assert f"<version>{PIT_VERSION}</version>" in pom.read_text()
    assert f"<version>{JUNIT5_PLUGIN_VERSION}</version>" in pom.read_text()
    if "managed" in body:                                   # pluginManagement untouched
        root = ET.parse(pom).getroot()
        assert "pitest" not in ET.tostring(root.find(".//{*}pluginManagement")).decode()


def test_a_profile_build_is_not_the_project_build(tmp_path):
    pom = _write(tmp_path, "    <profiles><profile><id>p</id><build><plugins/></build></profile></profiles>\n")
    add_pit_plugin(str(tmp_path))
    assert _build_plugins(pom) == ["pitest-maven"]


def test_idempotent_and_uses_the_declared_version(tmp_path):
    pom = _write(tmp_path, "")
    add_pit_plugin(str(tmp_path))
    once = pom.read_text()
    assert add_pit_plugin(str(tmp_path)) == "already declared"
    assert pom.read_text() == once
    assert pit_goal(str(tmp_path)) == "org.pitest:pitest-maven:mutationCoverage"


def test_pit_declared_without_junit5_plugin_is_left_to_a_human(tmp_path):
    _write(tmp_path, "    <build><plugins><plugin><artifactId>pitest-maven</artifactId></plugin></plugins></build>\n")
    with pytest.raises(ValueError, match="pitest-junit5-plugin"):
        add_pit_plugin(str(tmp_path))


def test_junit4_project_needs_nothing(tmp_path):
    (tmp_path / "pom.xml").write_text("<project><dependencies><dependency><artifactId>junit</artifactId>"
                                      "</dependency></dependencies></project>")
    assert setup_problem(str(tmp_path)) is None
    assert pit_goal(str(tmp_path)) == f"org.pitest:pitest-maven:{PIT_VERSION}:mutationCoverage"


def test_cli(tmp_path, monkeypatch, capsys):
    from src.lib.cli import main

    _write(tmp_path, "")
    monkeypatch.setattr("sys.argv", ["testboost", "pit-setup", str(tmp_path)])
    assert main() == 0
    assert "Review and commit it" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv", ["testboost", "pit-setup", str(tmp_path / "nope")])
    assert main() == 1


PARENT = ("<project><groupId>g</groupId><artifactId>parent</artifactId><version>1</version><build>"
          "<pluginManagement><plugins><plugin><artifactId>pitest-maven</artifactId><dependencies>"
          "<dependency><artifactId>pitest-junit5-plugin</artifactId></dependency></dependencies>"
          "</plugin></plugins></pluginManagement></build></project>")
MODULE = ("<project><parent><groupId>g</groupId><artifactId>parent</artifactId><version>1</version>{rel}"
          "</parent>" + JUPITER + "</project>")


class TestParentPoms:
    """A module judged alone inherits PIT from a parent outside its directory."""

    def test_parent_on_disk(self, tmp_path):
        (tmp_path / "pom.xml").write_text(PARENT)
        (tmp_path / "engine").mkdir()
        (tmp_path / "engine/pom.xml").write_text(MODULE.format(rel=""))
        assert setup_problem(str(tmp_path / "engine")) is None
        assert pit_goal(str(tmp_path / "engine")) == "org.pitest:pitest-maven:mutationCoverage"

    def test_parent_installed_in_the_local_repository(self, tmp_path, monkeypatch):
        m2 = tmp_path / "m2"
        (m2 / "g/parent/1").mkdir(parents=True)
        (m2 / "g/parent/1/parent-1.pom").write_text(PARENT)
        monkeypatch.setattr("src.java.pit._m2_repository", lambda: m2)
        (tmp_path / "engine").mkdir()
        (tmp_path / "engine/pom.xml").write_text(MODULE.format(rel="<relativePath/>"))
        assert setup_problem(str(tmp_path / "engine")) is None

    def test_unreadable_parent_is_not_judged(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.java.pit._m2_repository", lambda: tmp_path / "empty")
        (tmp_path / "pom.xml").write_text(MODULE.format(rel=""))
        assert setup_problem(str(tmp_path)) is None              # PIT will say, not a guess

    def test_parent_without_pit_still_refused(self, tmp_path):
        (tmp_path / "pom.xml").write_text(
            "<project><groupId>g</groupId><artifactId>parent</artifactId><version>1</version></project>")
        (tmp_path / "engine").mkdir()
        (tmp_path / "engine/pom.xml").write_text(MODULE.format(rel=""))
        assert "pit-setup" in setup_problem(str(tmp_path / "engine"))
