"""
Execute in container tool.

Executes commands inside a running Docker container.
"""

import asyncio
import json
import subprocess
from typing import Any


async def execute_in_container(
    container_id: str, command: list[str], workdir: str = "/project", timeout: int = 300
) -> str:
    """
    Execute a command inside a running container.

    Args:
        container_id: Container ID or name
        command: Command and arguments to execute
        workdir: Working directory inside container
        timeout: Timeout in seconds

    Returns:
        JSON string with execution results
    """
    results: dict[str, Any] = {
        "success": False,
        "container_id": container_id,
        "command": command,
        "workdir": workdir,
        "stdout": "",
        "stderr": "",
        "exit_code": -1,
    }

    try:
        # Check if container is running
        ps_cmd = [
            "docker",
            "ps",
            "--filter",
            f"id={container_id}",
            "--filter",
            "status=running",
            "--format",
            "{{.ID}}",
        ]
        ps_process = await asyncio.create_subprocess_exec(
            *ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        ps_out, _ = await ps_process.communicate()

        if not ps_out.decode().strip():
            # Try by name
            ps_cmd = [
                "docker",
                "ps",
                "--filter",
                f"name={container_id}",
                "--filter",
                "status=running",
                "--format",
                "{{.ID}}",
            ]
            ps_process = await asyncio.create_subprocess_exec(
                *ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
            ps_out, _ = await ps_process.communicate()

            if not ps_out.decode().strip():
                results["error"] = f"Container '{container_id}' is not running"
                return json.dumps(results, indent=2)

        # Execute command in container
        exec_cmd = ["docker", "exec", "-w", workdir, container_id] + command

        exec_process = await asyncio.create_subprocess_exec(
            *exec_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        try:
            stdout, stderr = await asyncio.wait_for(exec_process.communicate(), timeout=timeout)

            results["stdout"] = stdout.decode("utf-8", errors="replace")
            results["stderr"] = stderr.decode("utf-8", errors="replace")
            results["exit_code"] = exec_process.returncode

            if exec_process.returncode == 0:
                results["success"] = True
                results["message"] = "Command executed successfully"
            else:
                results["message"] = f"Command failed with exit code {exec_process.returncode}"

        except TimeoutError:
            # Kill the process
            exec_process.kill()
            results["error"] = f"Command timed out after {timeout} seconds"
            results["timed_out"] = True

    except FileNotFoundError:
        results["error"] = "Docker executable not found. Ensure Docker is installed."
    except Exception as e:
        results["error"] = str(e)

    # Truncate output if too large
    max_output = 50000
    if len(results.get("stdout", "")) > max_output:
        results["stdout"] = results["stdout"][:max_output] + "\n... (truncated)"
        results["output_truncated"] = True

    if len(results.get("stderr", "")) > max_output:
        results["stderr"] = results["stderr"][:max_output] + "\n... (truncated)"
        results["stderr_truncated"] = True

    return json.dumps(results, indent=2)
