"""
Health check tool.

Checks health status of deployed containers with wait logic.
"""

import asyncio
import json
import subprocess
import time
from pathlib import Path
from typing import Any

import httpx


async def health_check(
    compose_path: str,
    project_name: str = "",
    timeout: int = 120,
    check_interval: int = 5,
    endpoints: list[dict[str, Any]] | None = None,
) -> str:
    """
    Check health status of deployed containers.

    Args:
        compose_path: Path to docker-compose.yml file
        project_name: Project name for compose
        timeout: Timeout in seconds to wait for healthy status
        check_interval: Interval in seconds between health checks
        endpoints: HTTP endpoints to check for health

    Returns:
        JSON string with health check results
    """
    results: dict[str, Any] = {
        "success": False,
        "compose_path": compose_path,
        "containers": [],
        "endpoint_checks": [],
        "overall_healthy": False,
        "elapsed_time": 0,
    }

    if endpoints is None:
        endpoints = []

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

        start_time = time.time()
        all_healthy = False

        # Wait for containers to be healthy
        while time.time() - start_time < timeout:
            container_status = await _check_container_health(base_args, working_dir)
            results["containers"] = container_status["containers"]

            if container_status["all_healthy"]:
                all_healthy = True
                break

            await asyncio.sleep(check_interval)

        results["elapsed_time"] = round(time.time() - start_time, 2)

        if not all_healthy:
            results["warning"] = f"Not all containers healthy after {timeout}s timeout"

        # Check HTTP endpoints if provided
        if endpoints and all_healthy:
            endpoint_results = await _check_endpoints(endpoints, timeout - results["elapsed_time"])
            results["endpoint_checks"] = endpoint_results["checks"]

            if endpoint_results["all_passed"]:
                results["overall_healthy"] = True
                results["success"] = True
                results["message"] = "All health checks passed"
            else:
                results["warning"] = "Some endpoint checks failed"
        elif all_healthy:
            results["overall_healthy"] = True
            results["success"] = True
            results["message"] = "All containers are healthy"

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


async def _check_container_health(base_args: list[str], working_dir: Path) -> dict[str, Any]:
    """Check health status of all containers."""
    result = {"containers": [], "all_healthy": False}

    # Get container status
    ps_cmd = base_args + ["ps", "--format", "json"]

    ps_process = await asyncio.create_subprocess_exec(
        *ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(working_dir)
    )

    ps_stdout, _ = await ps_process.communicate()
    ps_output = ps_stdout.decode("utf-8", errors="replace").strip()

    if not ps_output:
        return result

    containers = []
    all_healthy = True

    for line in ps_output.split("\n"):
        if not line.strip():
            continue

        try:
            container_info = json.loads(line)

            name = container_info.get("Name", "")
            service = container_info.get("Service", "")
            state = container_info.get("State", "").lower()
            health = container_info.get("Health", "").lower()
            status = container_info.get("Status", "")

            container_data = {
                "name": name,
                "service": service,
                "state": state,
                "health": health,
                "status": status,
                "healthy": False,
            }

            # Determine if container is healthy
            if state == "running":
                if health in ["healthy", ""]:
                    # No health check or healthy
                    container_data["healthy"] = True
                elif health in ["starting"]:
                    # Still starting
                    all_healthy = False
                else:
                    # Unhealthy
                    all_healthy = False
            else:
                all_healthy = False

            containers.append(container_data)

        except json.JSONDecodeError:
            # Handle non-JSON output
            containers.append({"raw": line, "healthy": False})
            all_healthy = False

    result["containers"] = containers
    result["all_healthy"] = all_healthy and len(containers) > 0

    return result


async def _check_endpoints(
    endpoints: list[dict[str, Any]], remaining_timeout: float
) -> dict[str, Any]:
    """Check HTTP endpoints for health."""
    result: dict[str, Any] = {"checks": [], "all_passed": True}

    if remaining_timeout <= 0:
        remaining_timeout = 10

    async with httpx.AsyncClient(timeout=remaining_timeout) as client:
        for endpoint in endpoints:
            url = endpoint.get("url", "")
            method = endpoint.get("method", "GET").upper()
            expected_status = endpoint.get("expected_status", 200)

            check_result = {
                "url": url,
                "method": method,
                "expected_status": expected_status,
                "passed": False,
                "actual_status": None,
                "error": None,
            }

            try:
                response = await client.request(method, url)
                check_result["actual_status"] = response.status_code

                if response.status_code == expected_status:
                    check_result["passed"] = True
                else:
                    result["all_passed"] = False

            except httpx.ConnectError as e:
                check_result["error"] = f"Connection failed: {str(e)}"
                result["all_passed"] = False
            except httpx.TimeoutException:
                check_result["error"] = "Request timed out"
                result["all_passed"] = False
            except Exception as e:
                check_result["error"] = str(e)
                result["all_passed"] = False

            result["checks"].append(check_result)

    return result
