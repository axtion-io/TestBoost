"""
CLI commands for Maven maintenance operations.

Provides the 'boost maintenance' command for dependency updates.
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.cli.progress import create_progress
from src.lib.logging import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="maintenance",
    help="Maven dependency maintenance commands",
    no_args_is_help=True,
)


@app.command("run")
def run_maintenance(
    mode: str = typer.Option(
        "interactive",
        "--mode",
        "-m",
        help="Execution mode (interactive, autonomous, analysis_only, debug)",
    ),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Maven project",
    ),
    auto_approve: bool = typer.Option(
        False,
        "--auto-approve",
        "-y",
        help="Automatically approve all updates",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        "-n",
        help="Analyze without applying changes",
    ),
    skip_tests: bool = typer.Option(
        False,
        "--skip-tests",
        help="Skip test validation",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format (rich, json)",
    ),
) -> None:
    """
    Run Maven dependency maintenance workflow.

    Analyzes the project for available dependency updates, creates a
    maintenance branch, applies updates, validates with tests, and
    commits the changes.
    """
    logger.info(
        "maintenance_run_command",
        project_path=project_path,
        auto_approve=auto_approve,
        dry_run=dry_run,
    )

    # Validate project path
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_dir}")
        raise typer.Exit(1)

    pom_file = project_dir / "pom.xml"
    if not pom_file.exists():
        console.print(f"[red]Error:[/red] Not a Maven project: pom.xml not found in {project_dir}")
        raise typer.Exit(1)

    # Run the maintenance workflow
    async def _run() -> Any:
        # Use new agent-based workflow (US2)
        from uuid import uuid4

        from src.workflows.maven_maintenance_agent import run_maven_maintenance_with_agent

        session_id = str(uuid4())

        with create_progress(console) as progress:
            if dry_run:
                task = progress.add_task("Analyzing dependencies with AI agent...", total=None)
            else:
                task = progress.add_task("Running AI-powered maintenance workflow...", total=None)

            try:
                # Convert mode to agent-compatible format
                agent_mode = mode if mode in ["autonomous", "interactive", "analysis_only", "debug"] else "autonomous"

                result_json = await run_maven_maintenance_with_agent(
                    project_path=str(project_dir),
                    session_id=session_id,
                    mode=agent_mode
                )

                progress.update(task, completed=True)

                # Parse JSON result
                result_data = json.loads(result_json)

                # Create a result object compatible with old format
                class AgentResult:
                    def __init__(self, data: dict[str, Any]) -> None:
                        self.completed = data.get("success", False)
                        self.errors: list[str] = [] if self.completed else ["Workflow failed"]
                        self.warnings: list[str] = []
                        self.applied_updates: list[dict[str, Any]] = []
                        self.failed_updates: list[dict[str, Any]] = []
                        self.maintenance_branch = "agent-maintenance"
                        self.session_id = data.get("session_id", session_id)
                        self.analysis = data.get("analysis", "")

                return AgentResult(result_data)

            except Exception as e:
                progress.stop()
                console.print(f"[red]Error:[/red] {str(e)}")
                logger.error("maintenance_workflow_failed", error=str(e))
                raise typer.Exit(1) from None

    result = asyncio.run(_run())

    # Display results
    if output_format == "json":
        output = {
            "success": result.completed and len(result.errors) == 0,
            "project_path": str(project_dir),
            "session_id": getattr(result, "session_id", "unknown"),
            "analysis": getattr(result, "analysis", ""),
            "applied_updates": result.applied_updates,
            "failed_updates": result.failed_updates,
            "errors": result.errors,
            "warnings": result.warnings,
            "branch": result.maintenance_branch,
        }
        console.print_json(json.dumps(output))
    else:
        # Rich formatted output
        if result.completed and len(result.errors) == 0:
            # Show AI agent analysis
            if hasattr(result, "analysis") and result.analysis:
                console.print(
                    Panel(
                        f"[green]AI Agent Analysis[/green]\n\n{result.analysis}",
                        title="Maven Maintenance Analysis",
                    )
                )

            console.print(
                Panel(
                    f"[green]Maintenance Complete[/green]\n\n"
                    f"Session ID: {getattr(result, 'session_id', 'unknown')}\n"
                    f"Branch: {result.maintenance_branch}\n"
                    f"Applied: {len(result.applied_updates)} updates\n"
                    f"Failed: {len(result.failed_updates)} updates",
                    title="Success",
                )
            )
        else:
            console.print(
                Panel(
                    "[red]Maintenance Failed[/red]\n\n"
                    "Errors:\n" + "\n".join(f"- {e}" for e in result.errors),
                    title="Error",
                )
            )

        # Show applied updates table
        if result.applied_updates:
            table = Table(title="Applied Updates")
            table.add_column("Group ID", style="cyan")
            table.add_column("Artifact ID", style="magenta")
            table.add_column("Old Version", style="red")
            table.add_column("New Version", style="green")

            for update in result.applied_updates:
                table.add_row(
                    update.get("groupId", ""),
                    update.get("artifactId", ""),
                    update.get("currentVersion", ""),
                    update.get("targetVersion", ""),
                )

            console.print(table)

        # Show failed updates
        if result.failed_updates:
            table = Table(title="Failed Updates")
            table.add_column("Dependency", style="cyan")
            table.add_column("Error", style="red")

            for update in result.failed_updates:
                table.add_row(
                    f"{update.get('groupId', '')}:{update.get('artifactId', '')}",
                    update.get("error", "Unknown error"),
                )

            console.print(table)


@app.command("status")
def check_status(
    session_id: str = typer.Argument(
        ...,
        help="Session ID to check status for",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        "-w",
        help="Continuously watch for updates",
    ),
) -> None:
    """
    Check the status of a maintenance session.

    Use the session ID returned from 'maintenance run' to track
    the progress of a running maintenance workflow.
    """
    import httpx

    logger.info("maintenance_status_command", session_id=session_id)

    api_url = "http://localhost:8000"

    try:
        with httpx.Client() as client:
            response = client.get(f"{api_url}/api/testboost/maintenance/maven/{session_id}")

            if response.status_code == 404:
                console.print(f"[red]Error:[/red] Session not found: {session_id}")
                raise typer.Exit(1)

            response.raise_for_status()
            status = response.json()

            # Display status
            progress_pct = int(status.get("progress", 0) * 100)

            console.print(
                Panel(
                    f"Session: {session_id}\n"
                    f"Status: {status.get('status', 'unknown')}\n"
                    f"Current Step: {status.get('current_step', 'unknown')}\n"
                    f"Progress: {progress_pct}%\n"
                    f"Applied: {status.get('applied_updates', 0)}/{status.get('total_updates', 0)}",
                    title="Maintenance Status",
                )
            )

            if status.get("errors"):
                console.print("\n[red]Errors:[/red]")
                for error in status.get("errors", []):
                    console.print(f"  - {error}")

            if status.get("warnings"):
                console.print("\n[yellow]Warnings:[/yellow]")
                for warning in status.get("warnings", []):
                    console.print(f"  - {warning}")

    except httpx.ConnectError:
        console.print(
            "[red]Error:[/red] Could not connect to TestBoost API. Is the server running?"
        )
        raise typer.Exit(1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {str(e)}")
        raise typer.Exit(1) from None


@app.command("list")
def list_updates(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Maven project",
    ),
    include_snapshots: bool = typer.Option(
        False,
        "--include-snapshots",
        help="Include SNAPSHOT versions",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format (rich, json)",
    ),
) -> None:
    """
    List available dependency updates for a Maven project.

    Shows all dependencies with available updates and any known
    security vulnerabilities.
    """
    logger.info(
        "maintenance_list_command",
        project_path=project_path,
        include_snapshots=include_snapshots,
    )

    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_dir}")
        raise typer.Exit(1)

    async def _analyze() -> dict[str, Any]:
        from src.mcp_servers.maven_maintenance.tools.analyze import analyze_dependencies

        with create_progress(console) as progress:
            task = progress.add_task("Analyzing dependencies...", total=None)

            result = await analyze_dependencies(
                str(project_dir), include_snapshots=include_snapshots, check_vulnerabilities=True
            )

            progress.update(task, completed=True)

            return json.loads(result)  # type: ignore[no-any-return]

    analysis = asyncio.run(_analyze())

    if not analysis.get("success"):
        console.print(f"[red]Error:[/red] {analysis.get('error', 'Analysis failed')}")
        raise typer.Exit(1)

    if output_format == "json":
        console.print_json(json.dumps(analysis))
    else:
        # Show updates table
        updates = analysis.get("available_updates", [])
        if updates:
            table = Table(title=f"Available Updates ({len(updates)})")
            table.add_column("Group ID", style="cyan")
            table.add_column("Artifact ID", style="magenta")
            table.add_column("Current", style="red")
            table.add_column("Available", style="green")

            for update in updates:
                table.add_row(
                    update.get("groupId", ""),
                    update.get("artifactId", ""),
                    update.get("currentVersion", ""),
                    update.get("availableVersion", ""),
                )

            console.print(table)
        else:
            console.print("[green]All dependencies are up to date![/green]")

        # Show vulnerabilities
        vulns = analysis.get("vulnerabilities", [])
        if vulns:
            table = Table(title=f"Security Vulnerabilities ({len(vulns)})")
            table.add_column("Dependency", style="cyan")
            table.add_column("CVE", style="red")
            table.add_column("Severity", style="yellow")

            for vuln in vulns:
                table.add_row(
                    vuln.get("dependency", ""), vuln.get("cve", ""), vuln.get("severity", "")
                )

            console.print(table)


if __name__ == "__main__":
    app()
