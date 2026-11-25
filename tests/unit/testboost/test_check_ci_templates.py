# SPDX-License-Identifier: Apache-2.0
"""The CI templates consumers copy call real commands with real options: a template
that drifts from the CLI only fails in someone else's pipeline."""

import re
import shlex
from pathlib import Path

import pytest
import yaml

from src.lib.cli import main

ROOT = Path(__file__).resolve().parents[3]
TEMPLATES = ["templates/gitlab/testboost-check.yml", "templates/github/testboost-check.yml"]


def _commands(text):
    for line in re.findall(r"testboost (?:check|gitlab|github)[^\n|;]*", text):
        yield shlex.split(re.sub(r'"[^"]*\$[^"]*"', "X", line.replace("||", "")).split(" rc=")[0])


@pytest.mark.parametrize("template", TEMPLATES)
def test_template_commands_parse(template, monkeypatch, tmp_path):
    text = (ROOT / template).read_text()
    yaml.safe_load(text)
    commands = list(_commands(text))
    assert {c[1] for c in commands} >= {"check"}
    for argv in commands:
        argv = [a if a != "." else str(tmp_path) for a in argv]
        monkeypatch.setattr("sys.argv", [*argv, "--help"])
        with pytest.raises(SystemExit) as done:           # argparse accepts every option, then prints help
            main()
        assert done.value.code == 0, argv
