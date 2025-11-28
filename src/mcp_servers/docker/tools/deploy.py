"""
Deploy compose tool.

Deploys containers using docker-compose.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def deploy_compose(
    compose_path: str,
    project_name: str = "",
    build: bool = True,
    detach: bool = True,
    force_recreate: bool = False,
) -> str:
    """
    Deploy containers using docker-compose.

    Args:
        compose_path: Path to docker-compose.yml file
        project_name: Project name for compose
        build: Build images before starting
        detach: Run in detached mode
        force_recreate: Force recreation of containers

    Returns:
        JSON string with deployment results
    """
    results: dict[str, Any] = {
        "success": False,
        "compose_path": compose_path,
        "project_name": project_name,
        "containers": [],
        "build_output": "",
        "deploy_output": "",
    }

    try:
        compose_file = Path(compose_path)

        if not compose_file.exists():
            results["error"] = f"Compose file not found: {compose_path}"
            return json.dumps(results, indent=2)

        working_dir = compose_file.parent

        # Determine if using docker-compose or docker compose
        compose_cmd = await _get_compose_command()
        if not compose_cmd:
            results["error"] = "Neither 'docker compose' nor 'docker-compose' is available"
            return json.dumps(results, indent=2)

        # Build command arguments
        base_args = compose_cmd + ["-f", str(compose_file)]

        if project_name:
            base_args.extend(["-p", project_name])
            results["project_name"] = project_name
        else:
            # Use directory name as project name
            results["project_name"] = working_dir.name

        # Build images if requested
        if build:
            build_cmd = base_args + ["build"]

            build_process = await asyncio.create_subprocess_exec(
                *build_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(working_dir)
            )

            build_stdout, _ = await build_process.communicate()
            results["build_output"] = build_stdout.decode("utf-8", errors="replace")

            if build_process.returncode != 0:
                results["error"] = "Docker build failed"
                results["build_exit_code"] = build_process.returncode
                return json.dumps(results, indent=2)

        # Deploy command
        up_cmd = base_args + ["up"]

        if detach:
            up_cmd.append("-d")
        if force_recreate:
            up_cmd.append("--force-recreate")

        up_process = await asyncio.create_subprocess_exec(
            *up_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=str(working_dir)
        )

        up_stdout, _ = await up_process.communicate()
        results["deploy_output"] = up_stdout.decode("utf-8", errors="replace")

        if up_process.returncode != 0:
            results["error"] = "Docker compose up failed"
            results["deploy_exit_code"] = up_process.returncode
            return json.dumps(results, indent=2)

        # Get container information
        ps_cmd = base_args + ["ps", "--format", "json"]

        ps_process = await asyncio.create_subprocess_exec(
            *ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(working_dir)
        )

        ps_stdout, _ = await ps_process.communicate()
        ps_output = ps_stdout.decode("utf-8", errors="replace").strip()

        # Parse container info
        containers = []
        if ps_output:
            for line in ps_output.split("\n"):
                if line.strip():
                    try:
                        container_info = json.loads(line)
                        containers.append(
                            {
                                "name": container_info.get("Name", ""),
                                "service": container_info.get("Service", ""),
                                "state": container_info.get("State", ""),
                                "status": container_info.get("Status", ""),
                                "ports": container_info.get("Ports", ""),
                            }
                        )
                    except json.JSONDecodeError:
                        # Fallback for older docker-compose versions
                        containers.append({"raw": line})

        results["containers"] = containers
        results["success"] = True
        results["message"] = f"Deployed {len(containers)} containers"

    except FileNotFoundError:
        results["error"] = "Docker executable not found. Ensure Docker is installed."
    except Exception as e:
        results["error"] = str(e)

    # Truncate large outputs
    max_output = 50000
    for key in ["build_output", "deploy_output"]:
        if len(results.get(key, "")) > max_output:
            results[key] = results[key][:max_output] + "\n... (truncated)"
            results[f"{key}_truncated"] = True

    return json.dumps(results, indent=2)


async def _get_compose_command() -> list[str]:
    """Determine which compose command is available."""
    # Try 'docker compose' first (newer)
    try:
        process = await asyncio.create_subprocess_exec(
            "docker", "compose", "version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await process.communicate()
        if process.returncode == 0:
            return ["docker", "compose"]
    except FileNotFoundError:
        pass

    # Fall back to 'docker-compose' (legacy)
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
