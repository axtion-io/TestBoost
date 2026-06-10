# SPDX-License-Identifier: Apache-2.0
"""CLI command implementations, one module per command group.

The stable public surface is `src.lib.cli`, which re-exports everything
here — external callers (tests, wrapper scripts, `python -m testboost`)
should keep going through the facade.
"""

from src.lib.commands.analyze_cmd import cmd_analyze, cmd_gaps
from src.lib.commands.generate_cmd import cmd_generate
from src.lib.commands.hitl_cmd import cmd_resume, cmd_sign_answer
from src.lib.commands.init_cmd import cmd_init
from src.lib.commands.install_cmd import cmd_install
from src.lib.commands.mutation_cmd import cmd_killer, cmd_mutate
from src.lib.commands.ops_cmd import (
    cmd_cleanup,
    cmd_doctor,
    cmd_gitlab,
    cmd_status,
    cmd_verify,
)
from src.lib.commands.validate_cmd import cmd_validate

__all__ = [
    "cmd_analyze",
    "cmd_cleanup",
    "cmd_doctor",
    "cmd_gaps",
    "cmd_generate",
    "cmd_gitlab",
    "cmd_init",
    "cmd_install",
    "cmd_killer",
    "cmd_mutate",
    "cmd_resume",
    "cmd_sign_answer",
    "cmd_status",
    "cmd_validate",
    "cmd_verify",
]
