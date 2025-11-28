"""
Create Maven container tool.

Creates a Docker container configured for Maven builds.
"""

import asyncio
import json
import subprocess
from pathlib import Path
from typing import Any


async def create_maven_container(
    project_path: str,
    java_version: str = "17",
    maven_version: str = "3.9.5",
    container_name: str = "testboost-maven",
    memory_limit: str = "2g",
) -> str:
    """
    Create a Docker container for Maven builds.

    Args:
        project_path: Path to the Maven project to mount
        java_version: Java version to use
        maven_version: Maven version to use
        container_name: Name for the container
        memory_limit: Memory limit for the container

    Returns:
        JSON string with container creation results
    """
    project_dir = Path(project_path).resolve()

    if not project_dir.exists():
        return json.dumps({"success": False, "error": f"Project path not found: {project_path}"})

    results: dict[str, Any] = {
        "success": False,
        "container_name": container_name,
        "project_path": str(project_dir),
        "java_version": java_version,
        "maven_version": maven_version,
    }

    try:
        # Check if Docker is available
        docker_check = await asyncio.create_subprocess_exec(
            "docker", "version", stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        _, docker_err = await docker_check.communicate()

        if docker_check.returncode != 0:
            results["error"] = "Docker is not available or not running"
            return json.dumps(results, indent=2)

        # Check if container already exists
        ps_cmd = ["docker", "ps", "-a", "--filter", f"name={container_name}", "--format", "{{.ID}}"]
        ps_process = await asyncio.create_subprocess_exec(
            *ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        ps_out, _ = await ps_process.communicate()

        if ps_out.decode().strip():
            # Container exists, remove it
            rm_cmd = ["docker", "rm", "-f", container_name]
            rm_process = await asyncio.create_subprocess_exec(
                *rm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            await rm_process.communicate()

        # Determine the image to use
        image = f"maven:{maven_version}-eclipse-temurin-{java_version}"

        # Pull the image if needed
        pull_cmd = ["docker", "pull", image]
        pull_process = await asyncio.create_subprocess_exec(
            *pull_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        await pull_process.communicate()

        # Create the container
        create_cmd = [
            "docker",
            "create",
            "--name",
            container_name,
            "--memory",
            memory_limit,
            "--cpus",
            "2",
            "-v",
            f"{project_dir}:/project",
            "-v",
            "maven-cache:/root/.m2",
            "-w",
            "/project",
            image,
            "tail",
            "-f",
            "/dev/null",  # Keep container running
        ]

        create_process = await asyncio.create_subprocess_exec(
            *create_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        create_out, create_err = await create_process.communicate()

        if create_process.returncode != 0:
            results["error"] = create_err.decode().strip()
            return json.dumps(results, indent=2)

        container_id = create_out.decode().strip()
        results["container_id"] = container_id

        # Start the container
        start_cmd = ["docker", "start", container_id]
        start_process = await asyncio.create_subprocess_exec(
            *start_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        _, start_err = await start_process.communicate()

        if start_process.returncode != 0:
            results["error"] = f"Failed to start container: {start_err.decode().strip()}"
            return json.dumps(results, indent=2)

        # Get container info
        inspect_cmd = ["docker", "inspect", container_id, "--format", "{{.State.Status}}"]
        inspect_process = await asyncio.create_subprocess_exec(
            *inspect_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        inspect_out, _ = await inspect_process.communicate()
        results["status"] = inspect_out.decode().strip()

        results["success"] = True
        results["message"] = f"Container '{container_name}' created and started successfully"
        results["image"] = image

    except FileNotFoundError:
        results["error"] = "Docker executable not found. Ensure Docker is installed."
    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)
