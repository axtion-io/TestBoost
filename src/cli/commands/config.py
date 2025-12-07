"""CLI commands for configuration management."""

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from src.agents.loader import AgentLoader
from src.cli.exit_codes import ExitCode
from src.lib.logging import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="config",
    help="Configuration management commands",
    no_args_is_help=True,
)


@app.command("validate")  # type: ignore[untyped-decorator]
def validate_config(
    agent_name: str = typer.Option(None, "--agent", "-a", help="Specific agent to validate"),
    config_dir: Path = typer.Option(
        "config/agents",
        "--config-dir",
        "-c",
        help="Path to agent configurations directory",
    ),
) -> None:
    """Validate agent configuration(s).

    Validates:
    - YAML syntax
    - Pydantic schema compliance
    - MCP server availability
    - Prompt file existence
    - LLM provider validity
    - Parameter ranges (temperature, max_tokens)
    """
    try:
        loader = AgentLoader(config_dir)

        if agent_name:
            # Validate specific agent
            console.print(f"Validating agent: [cyan]{agent_name}[/cyan]")
            is_valid, errors = loader.validate_agent_config(agent_name)

            if is_valid:
                console.print(f"[OK] [green]{agent_name}[/green] is valid")
                raise typer.Exit(ExitCode.SUCCESS)
            else:
                console.print(f"[ERROR] [red]{agent_name}[/red] validation failed:")
                for error in errors:
                    console.print(f"  - {error}")
                raise typer.Exit(ExitCode.CONFIG_ERROR)
        else:
            # Validate all agents
            console.print("Validating all agent configurations...")
            results = loader.validate_all_agents()

            # Create results table
            table = Table(title="Agent Configuration Validation")
            table.add_column("Agent", style="cyan")
            table.add_column("Status", style="bold")
            table.add_column("Errors", style="red")

            valid_count = 0
            for agent, (is_valid, errors) in results.items():
                status = "[green]OK[/green]" if is_valid else "[red]FAIL[/red]"
                error_msg = "" if is_valid else "\n".join(errors)
                table.add_row(agent, status, error_msg)

                if is_valid:
                    valid_count += 1

            console.print(table)

            # Summary
            total = len(results)
            console.print(f"\nValidation complete: [green]{valid_count}/{total}[/green] passed")

            if valid_count == total:
                raise typer.Exit(ExitCode.SUCCESS)
            else:
                raise typer.Exit(ExitCode.CONFIG_ERROR)

    except typer.Exit:
        # Re-raise typer.Exit without catching it
        raise
    except FileNotFoundError as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        raise typer.Exit(ExitCode.PROJECT_NOT_FOUND)
    except Exception as e:
        console.print(f"[ERROR] Validation error: {e}", style="red")
        logger.error("config_validation_error", error=str(e))
        raise typer.Exit(ExitCode.CONFIG_ERROR)


@app.command("reload")  # type: ignore[untyped-decorator]
def reload_config(
    agent_name: str = typer.Option(None, "--agent", "-a", help="Specific agent to reload"),
    all_configs: bool = typer.Option(False, "--all", help="Reload all configurations"),
    config_dir: Path = typer.Option(
        "config/agents",
        "--config-dir",
        "-c",
        help="Path to agent configurations directory",
    ),
) -> None:
    """Force reload configuration(s) from disk.

    This clears the cache and reloads configurations. Useful after
    making changes to YAML files or prompts without restarting.
    """
    try:
        loader = AgentLoader(config_dir)

        if all_configs:
            # Reload all
            console.print("Reloading all configurations...")
            loader.reload_all()
            console.print("[OK] [green]All configurations reloaded[/green]")
            raise typer.Exit(ExitCode.SUCCESS)

        elif agent_name:
            # Reload specific agent
            console.print(f"Reloading agent: [cyan]{agent_name}[/cyan]")
            config = loader.reload_agent(agent_name)
            console.print(f"[OK] [green]{config.name}[/green] reloaded successfully")
            console.print(f"Provider: {config.llm.provider}/{config.llm.model}")
            console.print(f"MCP Servers: {', '.join(config.tools.mcp_servers)}")
            raise typer.Exit(ExitCode.SUCCESS)

        else:
            console.print("[ERROR] Error: Specify --agent or --all", style="red")
            raise typer.Exit(ExitCode.CONFIG_ERROR)

    except FileNotFoundError as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        raise typer.Exit(ExitCode.PROJECT_NOT_FOUND)
    except Exception as e:
        console.print(f"[ERROR] Reload error: {e}", style="red")
        logger.error("config_reload_error", error=str(e))
        raise typer.Exit(ExitCode.CONFIG_ERROR)


@app.command("backup")  # type: ignore[untyped-decorator]
def backup_config(
    agent_name: str = typer.Argument(..., help="Agent name to backup"),
    config_dir: Path = typer.Option(
        "config/agents",
        "--config-dir",
        "-c",
        help="Path to agent configurations directory",
    ),
) -> None:
    """Create a timestamped backup of an agent configuration.

    Backups are stored in config/agents/.backups/ with format:
    <agent_name>_YYYYMMDD_HHMMSS.yaml
    """
    try:
        loader = AgentLoader(config_dir)

        console.print(f"Backing up agent: [cyan]{agent_name}[/cyan]")
        backup_path = loader.backup_config(agent_name)

        console.print(f"[OK] Backup created: [green]{backup_path}[/green]")
        raise typer.Exit(ExitCode.SUCCESS)

    except FileNotFoundError as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        raise typer.Exit(ExitCode.PROJECT_NOT_FOUND)
    except Exception as e:
        console.print(f"[ERROR] Backup error: {e}", style="red")
        logger.error("config_backup_error", error=str(e))
        raise typer.Exit(ExitCode.CONFIG_ERROR)


@app.command("list-backups")  # type: ignore[untyped-decorator]
def list_backups(
    agent_name: str = typer.Option(None, "--agent", "-a", help="Filter by specific agent"),
    config_dir: Path = typer.Option(
        "config/agents",
        "--config-dir",
        "-c",
        help="Path to agent configurations directory",
    ),
) -> None:
    """List available configuration backups."""
    try:
        loader = AgentLoader(config_dir)

        backups = loader.list_backups(agent_name)

        if not backups:
            if agent_name:
                console.print(f"No backups found for agent: [cyan]{agent_name}[/cyan]")
            else:
                console.print("No backups found")
            raise typer.Exit(ExitCode.SUCCESS)

        # Create backups table
        table = Table(title=f"Configuration Backups{f' for {agent_name}' if agent_name else ''}")
        table.add_column("Agent", style="cyan")
        table.add_column("Timestamp", style="yellow")
        table.add_column("Path", style="dim")

        for backup_agent, timestamp, path in backups:
            table.add_row(
                backup_agent,
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                str(path.relative_to(config_dir.parent)),
            )

        console.print(table)
        console.print(f"\nTotal backups: [green]{len(backups)}[/green]")

        raise typer.Exit(ExitCode.SUCCESS)

    except Exception as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        logger.error("config_list_backups_error", error=str(e))
        raise typer.Exit(ExitCode.CONFIG_ERROR)


@app.command("rollback")  # type: ignore[untyped-decorator]
def rollback_config(
    agent_name: str = typer.Argument(..., help="Agent name to rollback"),
    config_dir: Path = typer.Option(
        "config/agents",
        "--config-dir",
        "-c",
        help="Path to agent configurations directory",
    ),
    confirm: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation prompt",
    ),
) -> None:
    """Rollback agent configuration to the latest backup.

    This will:
    1. Create a backup of the current configuration
    2. Restore the latest backup
    3. Invalidate the config cache
    """
    try:
        loader = AgentLoader(config_dir)

        # Check if backups exist
        backups = loader.list_backups(agent_name)
        if not backups:
            console.print(f"[ERROR] No backups found for agent: [cyan]{agent_name}[/cyan]", style="red")
            raise typer.Exit(ExitCode.PROJECT_NOT_FOUND)

        latest_backup = backups[0]
        timestamp_str = latest_backup[1].strftime("%Y-%m-%d %H:%M:%S")

        # Confirm rollback
        if not confirm:
            console.print(
                f"[WARNING]  This will rollback [cyan]{agent_name}[/cyan] to backup from {timestamp_str}"
            )
            console.print("   Current configuration will be backed up first.")
            confirm_input = typer.confirm("Continue?")

            if not confirm_input:
                console.print("Rollback cancelled")
                raise typer.Exit(ExitCode.SUCCESS)

        # Perform rollback
        console.print(f"Rolling back [cyan]{agent_name}[/cyan] to {timestamp_str}...")
        restored_path = loader.rollback_config(agent_name)

        console.print(f"[OK] Rollback complete")
        console.print(f"   Restored from: [green]{restored_path.name}[/green]")
        console.print(f"   Current config backed up to .backups/")

        raise typer.Exit(ExitCode.SUCCESS)

    except FileNotFoundError as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        raise typer.Exit(ExitCode.PROJECT_NOT_FOUND)
    except Exception as e:
        console.print(f"[ERROR] Rollback error: {e}", style="red")
        logger.error("config_rollback_error", error=str(e))
        raise typer.Exit(ExitCode.CONFIG_ERROR)


@app.command("show")  # type: ignore[untyped-decorator]
def show_config(
    agent_name: str = typer.Argument(..., help="Agent name to display"),
    config_dir: Path = typer.Option(
        "config/agents",
        "--config-dir",
        "-c",
        help="Path to agent configurations directory",
    ),
    format: str = typer.Option(
        "pretty",
        "--format",
        "-f",
        help="Output format: pretty, json, yaml",
    ),
) -> None:
    """Display agent configuration details."""
    try:
        loader = AgentLoader(config_dir)
        config = loader.load_agent(agent_name)

        if format == "json":
            # JSON output
            console.print(json.dumps(config.model_dump(), indent=2))
        elif format == "yaml":
            # YAML output
            import yaml  # type: ignore[import-untyped]
            console.print(yaml.dump(config.model_dump(), default_flow_style=False))
        else:
            # Pretty table output
            table = Table(title=f"Agent Configuration: {config.name}")
            table.add_column("Property", style="cyan")
            table.add_column("Value", style="green")

            table.add_row("Name", config.name)
            table.add_row("Description", config.description)
            table.add_row("Role", config.identity.role)
            table.add_row("Persona", config.identity.persona)
            table.add_row("LLM Provider", config.llm.provider)
            table.add_row("LLM Model", config.llm.model)
            table.add_row("Temperature", str(config.llm.temperature))
            table.add_row("Max Tokens", str(config.llm.max_tokens or "auto"))
            table.add_row("MCP Servers", ", ".join(config.tools.mcp_servers))
            table.add_row("System Prompt", config.prompts.system)
            table.add_row("Workflow Graph", config.workflow.graph_name)
            table.add_row("Workflow Node", config.workflow.node_name)
            table.add_row("Max Retries", str(config.error_handling.max_retries))
            table.add_row("Timeout", f"{config.error_handling.timeout_seconds}s")

            console.print(table)

        raise typer.Exit(ExitCode.SUCCESS)

    except FileNotFoundError as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        raise typer.Exit(ExitCode.PROJECT_NOT_FOUND)
    except Exception as e:
        console.print(f"[ERROR] Error: {e}", style="red")
        logger.error("config_show_error", error=str(e))
        raise typer.Exit(ExitCode.CONFIG_ERROR)


if __name__ == "__main__":
    app()
