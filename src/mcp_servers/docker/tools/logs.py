"""
Collect logs tool.

Collects logs from deployed containers.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def collect_logs(
    compose_path: str,
    project_name: str = "",
    services: list[str] | None = None,
    tail: int = 100,
    since: str = "",
    follow: bool = False,
) -> str:
    """
    Collect logs from deployed containers.

    Args:
        compose_path: Path to docker-compose.yml file
        project_name: Project name for compose
        services: Services to collect logs from (empty for all)
        tail: Number of lines to show from the end
        since: Show logs since timestamp
        follow: Follow log output

    Returns:
        JSON string with collected logs
    """
    results: dict[str, Any] = {
        "success": False,
        "compose_path": compose_path,
        "services_logged": [],
        "logs": {},
    }

    if services is None:
        services = []

    try:
        compose_file = Path(compose_path)

        if not compose_file.exists():
            results["error"] = f"Compose file not found: {compose_path}"
            return json.dumps(results, indent=2)

        working_dir = compose_file.parent

        # Determine compose command
        compose_cmd = await _get_compose_command()
        if not compose_cmd:
            results["error"] = "Neither 'docker compose' nor 'docker-compose' is available"
            return json.dumps(results, indent=2)

        # Build base command
        base_args = compose_cmd + ["-f", str(compose_file)]
        if project_name:
            base_args.extend(["-p", project_name])

        # Get list of services if not specified
        if not services:
            services = await _get_services(base_args, working_dir)

        results["services_logged"] = services

        # Collect logs for each service
        logs = {}
        for service in services:
            log_cmd = base_args + ["logs"]

            if tail > 0:
                log_cmd.extend(["--tail", str(tail)])

            if since:
                log_cmd.extend(["--since", since])

            # Note: follow is not used here as it would block
            # In a real implementation, follow would use streaming

            log_cmd.append(service)

            log_process = await asyncio.create_subprocess_exec(
                *log_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(working_dir)
            )

            log_stdout, _ = await log_process.communicate()
            log_output = log_stdout.decode("utf-8", errors="replace")

            # Parse log output
            logs[service] = {
                "content": log_output,
                "lines": len(log_output.split("\n")),
                "truncated": False,
            }

            # Truncate if too large
            max_output = 50000
            if len(log_output) > max_output:
                logs[service]["content"] = log_output[:max_output] + "\n... (truncated)"
                logs[service]["truncated"] = True

        results["logs"] = logs
        results["success"] = True
        results["message"] = f"Collected logs from {len(services)} service(s)"

    except FileNotFoundError:
        results["error"] = "Docker executable not found. Ensure Docker is installed."
    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


async def _get_compose_command() -> list[str]:
    """Determine which compose command is available."""
    try:
        process = await asyncio.create_subprocess_exec(
            "docker", "compose", "version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await process.communicate()
        if process.returncode == 0:
            return ["docker", "compose"]
    except FileNotFoundError:
        pass

    try:
        process = await asyncio.create_subprocess_exec(
            "docker-compose", "version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await process.communicate()
        if process.returncode == 0:
            return ["docker-compose"]
    except FileNotFoundError:
        pass

    return []


async def _get_services(base_args: list[str], working_dir: Path) -> list[str]:
    """Get list of services defined in compose file."""
    config_cmd = base_args + ["config", "--services"]

    config_process = await asyncio.create_subprocess_exec(
        *config_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(working_dir)
    )

    config_stdout, _ = await config_process.communicate()
    config_output = config_stdout.decode("utf-8", errors="replace").strip()

    if config_output:
        return config_output.split("\n")

    return []
