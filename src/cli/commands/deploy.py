"""
CLI commands for Docker deployment operations.

Provides the 'boost deploy' command for Docker deployment.
"""

import asyncio
import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.lib.logging import get_logger

logger = get_logger(__name__)
console = Console()

app = typer.Typer(
    name="deploy",
    help="Docker deployment commands",
    no_args_is_help=True,
)


@app.command("run")
def run_deployment(
    mode: str = typer.Option(
        "interactive",
        "--mode",
        help="Execution mode (interactive, autonomous, analysis_only, debug)",
    ),
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    dependencies: list[str] = typer.Option(
        [],
        "--dependency",
        "-d",
        help="Additional service dependencies (postgres, mysql, redis, mongodb, rabbitmq, kafka)",
    ),
    endpoint: list[str] = typer.Option(
        [],
        "--endpoint",
        "-e",
        help="Health check endpoints (e.g., 'http://localhost:8080/health')",
    ),
    skip_health: bool = typer.Option(
        False,
        "--skip-health",
        help="Skip health check validation",
    ),
    output_format: str = typer.Option(
        "rich",
        "--format",
        "-f",
        help="Output format (rich, json)",
    ),
) -> None:
    """
    Deploy a Java project using Docker.

    Analyzes the project, generates Dockerfile and docker-compose.yml,
    builds the image, runs the containers, and validates health.
    """
    logger.info(
        "deploy_run_command",
        project_path=project_path,
        dependencies=dependencies,
        endpoints=endpoint,
    )

    # Validate project path
    project_dir = Path(project_path).resolve()
    if not project_dir.exists():
        console.print(f"[red]Error:[/red] Project path not found: {project_dir}")
        raise typer.Exit(1)

    # Check for build file
    has_maven = (project_dir / "pom.xml").exists()
    has_gradle = (project_dir / "build.gradle").exists()

    if not has_maven and not has_gradle:
        console.print(
            f"[red]Error:[/red] Not a Java project: No pom.xml or build.gradle found in {project_dir}"
        )
        raise typer.Exit(1)

    # Parse health endpoints
    health_endpoints = []
    for ep in endpoint:
        health_endpoints.append({"url": ep, "method": "GET", "expected_status": 200})

    # Run the deployment workflow
    async def _run():
        from src.workflows.docker_deployment import run_docker_deployment

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Running Docker deployment...", total=None)

            try:
                result = await run_docker_deployment(
                    str(project_dir),
                    service_dependencies=list(dependencies),
                    health_endpoints=health_endpoints if not skip_health else [],
                )

                progress.update(task, completed=True)
                return result

            except Exception as e:
                progress.stop()
                console.print(f"[red]Error:[/red] {str(e)}")
                logger.exception("deploy_run_error", error=str(e))
                raise typer.Exit(1)

    result = asyncio.run(_run())

    # Display results
    if output_format == "json":
        output = {
            "success": result.completed and len(result.errors) == 0,
            "project_path": str(project_dir),
            "project_name": result.project_name,
            "dockerfile": result.dockerfile_path,
            "compose_file": result.compose_path,
            "containers": result.containers,
            "health_status": result.health_status,
            "errors": result.errors,
            "warnings": result.warnings,
        }
        console.print_json(json.dumps(output))
    else:
        # Rich formatted output
        if result.completed and len(result.errors) == 0:
            console.print(
                Panel(
                    f"[green]Deployment Complete[/green]\n\n"
                    f"Project: {result.project_name}\n"
                    f"Containers: {len(result.containers)}\n"
                    f"Health: {'Healthy' if result.health_status.get('overall_healthy') else 'Issues detected'}",
                    title="Success",
                )
            )
        else:
            console.print(
                Panel(
                    "[red]Deployment Failed[/red]\n\n"
                    "Errors:\n" + "\n".join(f"- {e}" for e in result.errors),
                    title="Error",
                )
            )

        # Show containers table
        if result.containers:
            table = Table(title="Deployed Containers")
            table.add_column("Name", style="cyan")
            table.add_column("Service", style="magenta")
            table.add_column("State", style="green")
            table.add_column("Status", style="yellow")

            for container in result.containers:
                table.add_row(
                    container.get("name", ""),
                    container.get("service", ""),
                    container.get("state", ""),
                    container.get("status", ""),
                )

            console.print(table)

        # Show access information
        if result.completed:
            console.print("\n[bold]Access Information:[/bold]")
            console.print("  Application: http://localhost:8080")
            if result.is_spring_boot:
                console.print("  Health: http://localhost:8080/actuator/health")
            console.print("\n[bold]Commands:[/bold]")
            console.print(f"  View logs: docker compose -f {result.compose_path} logs -f")
            console.print(f"  Stop: docker compose -f {result.compose_path} down")

        # Show warnings
        if result.warnings:
            console.print("\n[yellow]Warnings:[/yellow]")
            for warning in result.warnings:
                console.print(f"  - {warning}")


@app.command("stop")
def stop_deployment(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    remove_volumes: bool = typer.Option(
        False,
        "--volumes",
        "-v",
        help="Remove associated volumes",
    ),
) -> None:
    """
    Stop a Docker deployment.

    Stops and removes all containers defined in the project's docker-compose.yml.
    """
    logger.info("deploy_stop_command", project_path=project_path)

    project_dir = Path(project_path).resolve()
    compose_file = project_dir / "docker-compose.yml"

    if not compose_file.exists():
        console.print(f"[red]Error:[/red] docker-compose.yml not found in {project_dir}")
        raise typer.Exit(1)

    async def _stop():
        import asyncio
        import subprocess

        # Determine compose command
        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "compose", "version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await process.communicate()
            compose_cmd = ["docker", "compose"] if process.returncode == 0 else ["docker-compose"]
        except FileNotFoundError:
            compose_cmd = ["docker-compose"]

        cmd = compose_cmd + ["-f", str(compose_file), "down"]
        if remove_volumes:
            cmd.append("-v")

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        stdout, _ = await process.communicate()
        return stdout.decode("utf-8", errors="replace"), process.returncode

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Stopping deployment...", total=None)
        output, returncode = asyncio.run(_stop())
        progress.update(task, completed=True)

    if returncode == 0:
        console.print("[green]Deployment stopped successfully[/green]")
    else:
        console.print(f"[red]Error stopping deployment:[/red]\n{output}")
        raise typer.Exit(1)


@app.command("logs")
def show_logs(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    service: str = typer.Option(
        "",
        "--service",
        "-s",
        help="Specific service to show logs for",
    ),
    tail: int = typer.Option(
        100,
        "--tail",
        "-n",
        help="Number of lines to show",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
        "-f",
        help="Follow log output",
    ),
) -> None:
    """
    Show logs from deployed containers.
    """
    logger.info("deploy_logs_command", project_path=project_path)

    project_dir = Path(project_path).resolve()
    compose_file = project_dir / "docker-compose.yml"

    if not compose_file.exists():
        console.print(f"[red]Error:[/red] docker-compose.yml not found in {project_dir}")
        raise typer.Exit(1)

    async def _logs():
        from src.mcp_servers.docker.tools.logs import collect_logs

        result = await collect_logs(
            str(compose_file), services=[service] if service else [], tail=tail, follow=follow
        )

        return json.loads(result)

    logs_result = asyncio.run(_logs())

    if not logs_result.get("success"):
        console.print(f"[red]Error:[/red] {logs_result.get('error', 'Failed to collect logs')}")
        raise typer.Exit(1)

    # Display logs
    for svc_name, log_data in logs_result.get("logs", {}).items():
        console.print(f"\n[bold cyan]--- {svc_name} ---[/bold cyan]")
        console.print(log_data.get("content", "No logs available"))


@app.command("status")
def check_status(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
) -> None:
    """
    Check status of deployed containers.
    """
    logger.info("deploy_status_command", project_path=project_path)

    project_dir = Path(project_path).resolve()
    compose_file = project_dir / "docker-compose.yml"

    if not compose_file.exists():
        console.print(f"[red]Error:[/red] docker-compose.yml not found in {project_dir}")
        raise typer.Exit(1)

    async def _status():
        from src.mcp_servers.docker.tools.health import health_check

        result = await health_check(str(compose_file), timeout=10, check_interval=2)

        return json.loads(result)

    status_result = asyncio.run(_status())

    # Display status
    containers = status_result.get("containers", [])

    if not containers:
        console.print("[yellow]No containers found[/yellow]")
        return

    table = Table(title="Container Status")
    table.add_column("Name", style="cyan")
    table.add_column("Service", style="magenta")
    table.add_column("State", style="green")
    table.add_column("Health", style="yellow")

    for container in containers:
        health = container.get("health", "")
        health_style = "green" if container.get("healthy") else "red"

        table.add_row(
            container.get("name", ""),
            container.get("service", ""),
            container.get("state", ""),
            f"[{health_style}]{health or 'N/A'}[/{health_style}]",
        )

    console.print(table)

    # Overall health
    if status_result.get("overall_healthy"):
        console.print("\n[green]All containers healthy[/green]")
    else:
        console.print("\n[yellow]Some containers may have health issues[/yellow]")


@app.command("build")
def build_only(
    project_path: str = typer.Argument(
        ".",
        help="Path to the Java project",
    ),
    no_cache: bool = typer.Option(
        False,
        "--no-cache",
        help="Build without using cache",
    ),
) -> None:
    """
    Build Docker image without running containers.

    Useful for verifying the build process.
    """
    logger.info("deploy_build_command", project_path=project_path)

    project_dir = Path(project_path).resolve()

    # Check for Dockerfile or generate one
    dockerfile = project_dir / "Dockerfile"
    compose_file = project_dir / "docker-compose.yml"

    async def _build():
        import subprocess

        # Generate files if needed
        if not dockerfile.exists():
            from src.mcp_servers.docker.tools.dockerfile import create_dockerfile

            result = await create_dockerfile(str(project_dir))
            df_result = json.loads(result)
            if not df_result.get("success"):
                return {"success": False, "error": df_result.get("error")}

        if not compose_file.exists():
            from src.mcp_servers.docker.tools.compose import create_compose

            result = await create_compose(str(project_dir))
            compose_result = json.loads(result)
            if not compose_result.get("success"):
                return {"success": False, "error": compose_result.get("error")}

        # Determine compose command
        import asyncio

        try:
            process = await asyncio.create_subprocess_exec(
                "docker", "compose", "version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await process.communicate()
            compose_cmd = ["docker", "compose"] if process.returncode == 0 else ["docker-compose"]
        except FileNotFoundError:
            compose_cmd = ["docker-compose"]

        # Build
        cmd = compose_cmd + ["-f", str(compose_file), "build"]
        if no_cache:
            cmd.append("--no-cache")

        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(project_dir)
        )

        stdout, _ = await process.communicate()

        return {
            "success": process.returncode == 0,
            "output": stdout.decode("utf-8", errors="replace"),
            "exit_code": process.returncode,
        }

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Building Docker image...", total=None)
        result = asyncio.run(_build())
        progress.update(task, completed=True)

    if result.get("success"):
        console.print("[green]Build completed successfully[/green]")
    else:
        console.print(
            f"[red]Build failed:[/red]\n{result.get('output', result.get('error', 'Unknown error'))}"
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
