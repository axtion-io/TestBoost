"""Typer CLI application for TestBoost."""

import typer

from src.cli.commands.audit import app as audit_app
from src.cli.commands.deploy import app as deploy_app
from src.cli.commands.maintenance import app as maintenance_app
from src.cli.commands.tests import app as tests_app
from src.lib.logging import get_logger

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
    """TestBoost CLI - AI-powered Java test generation and maintenance."""
    pass


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
    mode: str = typer.Option("interactive", "--mode", "-m", help="Execution mode"),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project to analyze",
    ),
    output: str = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file for analysis results",
    ),
) -> None:
    """Analyze a Java project for test generation opportunities."""
    logger.info("analyze_command", project_path=project_path, output=output)
    typer.echo(f"Analyzing project: {project_path}")
    # Implementation will be added in later phases


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
) -> None:
    """Generate tests for a Java project."""
    logger.info(
        "generate_command",
        project_path=project_path,
        target=target,
        mode=mode,
    )
    typer.echo(f"Generating tests for: {project_path}")
    # Implementation will be added in later phases


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
        help="Check for dependency updates",
    ),
) -> None:
    """Perform Maven maintenance tasks."""
    logger.info(
        "maven_command",
        project_path=project_path,
        check_updates=check_updates,
    )
    typer.echo(f"Maven maintenance for: {project_path}")
    # Implementation will be added in later phases


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
    import uvicorn

    logger.info("serve_command", host=host, port=port, reload=reload)
    typer.echo(f"Starting TestBoost API server on {host}:{port}")

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

if __name__ == "__main__":
    app()
