"""
Destroy container tool.

Stops and removes Docker containers.
"""

import asyncio
import json
import subprocess
from typing import Any


async def destroy_container(
    container_id: str, force: bool = False, remove_volumes: bool = False
) -> str:
    """
    Stop and remove a container.

    Args:
        container_id: Container ID or name
        force: Force removal of running container
        remove_volumes: Remove associated volumes

    Returns:
        JSON string with destruction results
    """
    results: dict[str, Any] = {
        "success": False,
        "container_id": container_id,
        "force": force,
        "remove_volumes": remove_volumes,
    }

    try:
        # Check if container exists
        inspect_cmd = ["docker", "inspect", container_id]
        inspect_process = await asyncio.create_subprocess_exec(
            *inspect_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        inspect_out, inspect_err = await inspect_process.communicate()

        if inspect_process.returncode != 0:
            results["error"] = f"Container '{container_id}' not found"
            return json.dumps(results, indent=2)

        # Parse container info
        container_info = json.loads(inspect_out.decode())[0]
        was_running = container_info.get("State", {}).get("Running", False)
        results["was_running"] = was_running

        # Stop container if running and not forcing
        if was_running and not force:
            stop_cmd = ["docker", "stop", container_id]
            stop_process = await asyncio.create_subprocess_exec(
                *stop_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

            _, stop_err = await stop_process.communicate()

            if stop_process.returncode != 0:
                results["warning"] = (
                    f"Failed to stop container gracefully: {stop_err.decode().strip()}"
                )

        # Remove container
        rm_cmd = ["docker", "rm"]

        if force:
            rm_cmd.append("-f")

        if remove_volumes:
            rm_cmd.append("-v")

        rm_cmd.append(container_id)

        rm_process = await asyncio.create_subprocess_exec(
            *rm_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        rm_out, rm_err = await rm_process.communicate()

        if rm_process.returncode != 0:
            results["error"] = rm_err.decode().strip()
            return json.dumps(results, indent=2)

        results["success"] = True
        results["message"] = f"Container '{container_id}' removed successfully"

        # Get container name from info
        container_name = container_info.get("Name", "").lstrip("/")
        if container_name:
            results["container_name"] = container_name

    except FileNotFoundError:
        results["error"] = "Docker executable not found. Ensure Docker is installed."
    except json.JSONDecodeError:
        results["error"] = "Failed to parse container information"
    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)
