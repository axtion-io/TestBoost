# SPDX-License-Identifier: Apache-2.0
"""TestBoost as an MCP server (`testboost-mcp`, stdio).

The host agent (Claude Code, Cursor, Copilot, OpenCode…) writes the tests;
these tools give it what only TestBoost does deterministically: briefs,
registration + compilation, runs, PIT, the equivalent-mutant ledger, and the
`check` verdict. No tool calls an LLM.

Each tool runs the TestBoost CLI in a subprocess: commands print, exit and
own their asyncio loop, and a crash in one must not take the server down.
`TESTBOOST_MCP_TIMEOUT` (seconds, default 1800) bounds a call.
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp.server import MCPServer

MAX_OUTPUT = 20_000
EXIT_MEANING = {0: "ok", 1: "failed / below threshold", 2: "measure failed", 78: "awaiting human input"}

server = MCPServer(
    name="testboost",
    instructions=(
        "TestBoost measures and supports the tests YOU write for a Java/Maven project. "
        "To judge tests: `check` (coverage + mutation score; `base` = a git ref to judge only a change). "
        "To write tests with briefs: init → analyze → gaps (coverage=True) → context → write each test at "
        "the path given → register_tests → validate → mutate → context(killer=True) → register_killer_tests. "
        "A surviving mutant no test can observe: declare_equivalent with a real reason."
    ),
)


def _timeout() -> float:
    try:
        return float(os.environ.get("TESTBOOST_MCP_TIMEOUT", "1800"))
    except ValueError:
        return 1800.0


async def run_cli(*args: str) -> tuple[int, str]:
    """`python -m testboost <args>` → (exit code, stdout+stderr without metrics lines).

    Logs go to the user cache, not to the server's working directory (which, for
    an MCP server, is wherever the host started it).
    """
    env = {**os.environ}
    env.setdefault("TESTBOOST_LOG_DIR", str(Path.home() / ".cache" / "testboost" / "logs"))
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "testboost", *args,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env,
    )
    try:
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_timeout())
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return 124, f"timed out after {_timeout():.0f}s (TESTBOOST_MCP_TIMEOUT)"
    text = "\n".join(ln for ln in out.decode("utf-8", errors="replace").splitlines()
                     if not ln.startswith("[TESTBOOST_METRICS:"))
    return proc.returncode or 0, text


def _result(code: int, text: str) -> str:
    if len(text) > MAX_OUTPUT:
        text = "… (start truncated)\n" + text[-MAX_OUTPUT:]
    return f"exit {code} ({EXIT_MEANING.get(code, 'error')})\n\n{text}".rstrip() + "\n"


def _project(project_path: str) -> str:
    path = Path(project_path).expanduser().resolve()
    if not path.is_dir():
        raise ValueError(f"not a directory: {project_path}")
    return str(path)


@server.tool()
async def check(project_path: str, base: str | None = None, min_coverage: float = 80.0,
                min_mutation: float = 80.0, mutation: bool = True) -> str:
    """Measure the tests (JaCoCo line coverage + PIT mutation score), whoever wrote them.

    `base`: a git ref (e.g. "origin/main") to judge only the lines changed since its merge base.
    Exit 0 = both thresholds met, 1 = one is not, 2 = the measure failed (red suite, build error).
    Returns the markdown report: uncovered lines and surviving mutants with their ids.
    """
    project = _project(project_path)
    args = ["check", project, "--min-coverage", str(min_coverage), "--min-mutation", str(min_mutation)]
    if base:
        args += ["--base", base]
    if not mutation:
        args.append("--no-mutation")
    return _result(*await run_cli(*args))


@server.tool()
async def pit_setup(project_path: str) -> str:
    """Declare PIT + its JUnit 5 plugin (pinned versions) in the root pom.xml — needed once."""
    return _result(*await run_cli("pit-setup", _project(project_path)))


@server.tool()
async def init(project_path: str) -> str:
    """Create a TestBoost session for the project (needed before analyze/gaps/context)."""
    return _result(*await run_cli("init", _project(project_path)))


@server.tool()
async def analyze(project_path: str) -> str:
    """Analyze the project: frameworks, test conventions, available test libraries."""
    return _result(*await run_cli("analyze", _project(project_path)))


@server.tool()
async def gaps(project_path: str, coverage: bool = True, min_coverage: float = 80.0) -> str:
    """Find what is untested. coverage=True: classes below `min_coverage` JaCoCo line coverage."""
    args = ["gaps", _project(project_path)]
    if coverage:
        args += ["--coverage", "--min-coverage", str(min_coverage)]
    return _result(*await run_cli(*args))


@server.tool()
async def context(project_path: str, files: list[str] | None = None, killer: bool = False) -> str:
    """Write one short brief per test to write (or, killer=True, per class with surviving mutants)
    and the exact test path to use. Read each brief and the class, then write the test there."""
    args = ["context", _project(project_path)]
    if files:
        args += ["--files", *files]
    if killer:
        args.append("--killer")
    return _result(*await run_cli(*args))


@server.tool()
async def register_tests(project_path: str) -> str:
    """Register and compile the tests you wrote at the paths `context` gave (no LLM)."""
    return _result(*await run_cli("generate", _project(project_path), "--agent"))


@server.tool()
async def register_killer_tests(project_path: str) -> str:
    """Register and compile the killer tests you wrote after `context(killer=True)`."""
    return _result(*await run_cli("killer", _project(project_path), "--agent"))


@server.tool()
async def validate(project_path: str, full: bool = False) -> str:
    """Compile and run the registered tests (full=True: the whole suite, for regressions)."""
    args = ["validate", _project(project_path)]
    if full:
        args.append("--full")
    return _result(*await run_cli(*args))


@server.tool()
async def mutate(project_path: str, target_classes: list[str] | None = None,
                 target_tests: list[str] | None = None, min_score: int = 80) -> str:
    """Run PIT on the session's tests; lists surviving mutants with their ids."""
    args = ["mutate", _project(project_path), "--min-score", str(min_score)]
    if target_classes:
        args += ["--target-classes", *target_classes]
    if target_tests:
        args += ["--target-tests", *target_tests]
    return _result(*await run_cli(*args))


@server.tool()
async def declare_equivalent(project_path: str, ids: list[str], reason: str) -> str:
    """Declare surviving mutants equivalent: no test can observe them. `reason` must say why
    (at least 10 characters); they then leave the score. Never use it to hide a weak test."""
    return _result(*await run_cli("equivalent", _project(project_path), *ids, "--reason", reason))


@server.tool()
async def status(project_path: str) -> str:
    """Current session: steps done, their status, what to do next."""
    return _result(*await run_cli("status", _project(project_path)))


def main() -> None:
    server.run()


if __name__ == "__main__":
    main()
