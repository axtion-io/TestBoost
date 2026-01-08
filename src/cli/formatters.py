"""Rich formatters for CLI output."""

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table


def format_session_table(sessions: list[dict[str, Any]], console: Console) -> None:
    """Display sessions in a Rich table.

    Args:
        sessions: List of session dictionaries
        console: Rich console instance
    """
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return

    table = Table(title="Sessions")
    table.add_column("ID", style="cyan", no_wrap=True, max_width=36)
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="bold")
    table.add_column("Project", style="dim", max_width=40)
    table.add_column("Created", style="dim")

    for session in sessions:
        # Format status with color
        status = session.get("status", "unknown")
        status_styled = _style_status(status)

        # Format created date
        created = session.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        # Truncate ID for display
        session_id = str(session.get("id", ""))[:8] + "..."

        table.add_row(
            session_id,
            session.get("session_type", "unknown"),
            status_styled,
            session.get("project_path", ""),
            created,
        )

    console.print(table)


def format_steps_table(steps: list[dict[str, Any]], console: Console) -> None:
    """Display steps in a Rich table.

    Args:
        steps: List of step dictionaries
        console: Rich console instance
    """
    if not steps:
        console.print("[yellow]No steps found.[/yellow]")
        return

    table = Table(title="Session Steps")
    table.add_column("#", style="dim", justify="right")
    table.add_column("Code", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("Status", style="bold")
    table.add_column("Started", style="dim")

    for step in sorted(steps, key=lambda s: s.get("sequence", 0)):
        status = step.get("status", "unknown")
        status_styled = _style_status(status)

        started = step.get("started_at", "")
        if started:
            try:
                dt = datetime.fromisoformat(started.replace("Z", "+00:00"))
                started = dt.strftime("%H:%M:%S")
            except Exception:
                pass

        table.add_row(
            str(step.get("sequence", 0)),
            step.get("code", ""),
            step.get("name", ""),
            status_styled,
            started or "-",
        )

    console.print(table)


def format_artifacts_table(artifacts: list[dict[str, Any]], console: Console) -> None:
    """Display artifacts in a Rich table.

    Args:
        artifacts: List of artifact dictionaries
        console: Rich console instance
    """
    if not artifacts:
        console.print("[yellow]No artifacts found.[/yellow]")
        return

    table = Table(title="Session Artifacts")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Content-Type", style="dim")
    table.add_column("Size", style="dim", justify="right")
    table.add_column("Created", style="dim")

    for artifact in artifacts:
        size = artifact.get("size_bytes", 0)
        size_str = _format_size(size)

        created = artifact.get("created_at", "")
        if created:
            try:
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass

        table.add_row(
            artifact.get("name", ""),
            artifact.get("artifact_type", ""),
            artifact.get("content_type", ""),
            size_str,
            created,
        )

    console.print(table)


def format_step_result(result: dict[str, Any], console: Console) -> None:
    """Display step execution result.

    Args:
        result: Step execution result
        console: Rich console instance
    """
    status = result.get("status", "unknown")
    message = result.get("message", "")
    code = result.get("code", "")
    name = result.get("name", "")

    # Determine panel style based on status
    if status == "in_progress":
        style = "blue"
        title = "Step Started"
    elif status == "completed":
        style = "green"
        title = "Step Completed"
    elif status == "failed":
        style = "red"
        title = "Step Failed"
    else:
        style = "yellow"
        title = f"Step: {status}"

    content = f"[bold]{name}[/bold] ({code})\n\n{message}"

    console.print(Panel(content, title=title, border_style=style))


def format_pause_result(result: dict[str, Any], console: Console) -> None:
    """Display pause result.

    Args:
        result: Pause response
        console: Rich console instance
    """
    checkpoint_id = result.get("checkpoint_id", "")
    message = result.get("message", "Session paused")

    content = f"{message}\n\n[dim]Checkpoint ID:[/dim] [cyan]{checkpoint_id}[/cyan]"
    console.print(Panel(content, title="Session Paused", border_style="yellow"))


def format_resume_result(result: dict[str, Any], console: Console) -> None:
    """Display resume result.

    Args:
        result: Resume response
        console: Rich console instance
    """
    message = result.get("message", "Session resumed")
    console.print(Panel(message, title="Session Resumed", border_style="green"))


def format_cancel_result(session_id: str, console: Console) -> None:
    """Display cancel result.

    Args:
        session_id: Cancelled session ID
        console: Rich console instance
    """
    console.print(Panel(
        f"Session [cyan]{session_id}[/cyan] has been cancelled.",
        title="Session Cancelled",
        border_style="red",
    ))


def _style_status(status: str) -> str:
    """Apply Rich styling to status string."""
    status_colors = {
        "pending": "[dim]pending[/dim]",
        "in_progress": "[blue]in_progress[/blue]",
        "completed": "[green]completed[/green]",
        "failed": "[red]failed[/red]",
        "paused": "[yellow]paused[/yellow]",
        "cancelled": "[red]cancelled[/red]",
    }
    return status_colors.get(status.lower(), status)


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
