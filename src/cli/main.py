# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 TestBoost Contributors

"""Typer CLI application for TestBoost."""

# CRITICAL: Load .env file BEFORE any imports that use config
# This ensures .env values override any stale shell environment variables
from pathlib import Path

from dotenv import load_dotenv

_env_path = Path(__file__).parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path, override=True)

# Clear any cached settings to pick up new env values
from src.lib.config import get_settings  # noqa: E402

get_settings.cache_clear()

# IMPORTANT: Must be imported early to patch DeepAgents before any other module uses it
import asyncio  # noqa: E402

import typer  # noqa: E402

import src.lib.deepagents_compat  # noqa: F401, E402
from src.cli.commands.audit import app as audit_app  # noqa: E402
from src.cli.commands.config import app as config_app  # noqa: E402
from src.cli.commands.deploy import app as deploy_app  # noqa: E402
from src.cli.commands.maintenance import app as maintenance_app  # noqa: E402
from src.cli.commands.tests import app as tests_app  # noqa: E402
from src.lib.logging import get_logger  # noqa: E402
from src.lib.startup_checks import StartupCheckError, run_all_startup_checks  # noqa: E402

logger = get_logger(__name__)

app = typer.Typer(
    name="testboost",
    help="AI-powered Java test generation and maintenance platform",
    no_args_is_help=True,
    add_completion=False,
)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo("TestBoost version 0.1.0")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """
    TestBoost CLI - AI-powered Java test generation and maintenance.

    Implements T009: Check LLM connectivity before accepting commands.
    Constitutional principle: "Zéro Complaisance" - No workflows execute without LLM.
    """
    # T009: Run startup checks before any command execution
    # Skip if only version flag is provided
    if version:
        return

    try:
        # Run startup checks synchronously in CLI context
        asyncio.run(run_all_startup_checks())
        logger.info("cli_startup_checks_passed")
    except StartupCheckError as e:
        logger.error("cli_startup_checks_failed", error=str(e))
        typer.echo(f"❌ Startup checks failed: {e}", err=True)
        # Application MUST fail if startup checks fail (FR-010)
        raise typer.Exit(code=1) from None


@app.command()
def init(
    mode: str = typer.Option(
        "interactive",
        "--mode",
        "-m",
        help="Execution mode (interactive, autonomous, analysis_only, debug)",
    ),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project to initialize",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing configuration",
    ),
) -> None:
    """Initialize TestBoost for a Java project."""
    logger.info("init_command", project_path=project_path, force=force)
    typer.echo(f"Initializing TestBoost in: {project_path}")
    # Implementation will be added in later phases


@app.command()
def analyze(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project to analyze",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed output",
    ),
) -> None:
    """Analyze a Java project for test generation opportunities.

    This is a shortcut for 'testboost tests analyze'.
    """
    from src.cli.commands.tests import analyze_project

    # Delegate to the full implementation in tests.py
    analyze_project(
        project_path=project_path,
        verbose=verbose,
    )


@app.command()
def generate(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    target: str = typer.Option(
        None,
        "--target",
        "-t",
        help="Specific class or package to generate tests for",
    ),
    mode: str = typer.Option(
        "interactive",
        "--mode",
        "-m",
        help="Execution mode (interactive, autonomous, analysis_only)",
    ),
    mutation_score: float = typer.Option(
        80.0,
        "--mutation-score",
        help="Target mutation score percentage",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Analyze without generating tests",
    ),
) -> None:
    """Generate tests for a Java project.

    This is a shortcut for 'testboost tests generate'.
    """
    from src.cli.commands.tests import generate_tests

    # Delegate to the full implementation in tests.py
    generate_tests(
        mode=mode,
        project_path=project_path,
        target=target,
        mutation_score=mutation_score,
        include_integration=True,
        include_snapshot=True,
        output_dir=None,
        dry_run=dry_run,
        verbose=False,
    )


@app.command()
def maven(
    mode: str = typer.Option("interactive", "--mode", "-m", help="Execution mode"),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Maven project",
    ),
    check_updates: bool = typer.Option(
        False,
        "--check-updates",
        "-u",
        help="Check for dependency updates (list only)",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Analyze without applying changes",
    ),
) -> None:
    """Perform Maven maintenance tasks.

    This is a shortcut for 'testboost maintenance run' or 'testboost maintenance list'.
    """
    from src.cli.commands.maintenance import list_updates, run_maintenance

    if check_updates:
        # Just list available updates
        list_updates(
            project_path=project_path,
            include_snapshots=False,
            output_format="rich",
        )
    else:
        # Run full maintenance workflow
        run_maintenance(
            mode=mode,
            project_path=project_path,
            auto_approve=False,
            dry_run=dry_run,
            skip_tests=False,
            output_format="rich",
        )


@app.command()
def status(
    session_id: str = typer.Argument(
        None,
        help="Session ID to check status for",
    ),
) -> None:
    """Check the status of a TestBoost session."""
    logger.info("status_command", session_id=session_id)
    if session_id:
        typer.echo(f"Checking status for session: {session_id}")
    else:
        typer.echo("Listing recent sessions...")
    # Implementation will be added in later phases


@app.command()
def serve(
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        "-h",
        help="Host to bind the server to",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to bind the server to",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help="Enable auto-reload for development",
    ),
) -> None:
    """Start the TestBoost API server."""
    import os

    import uvicorn

    logger.info("serve_command", host=host, port=port, reload=reload)
    typer.echo(f"Starting TestBoost API server on {host}:{port}")

    # Skip API startup checks since CLI already ran them
    os.environ["TESTBOOST_SKIP_API_STARTUP_CHECKS"] = "1"

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=reload,
    )


app.add_typer(maintenance_app, name="maintenance")
app.add_typer(audit_app, name="audit")
app.add_typer(tests_app, name="tests")
app.add_typer(deploy_app, name="deploy")
app.add_typer(config_app, name="config")

if __name__ == "__main__":
    app()
