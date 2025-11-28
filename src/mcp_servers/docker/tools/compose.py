"""
Create docker-compose tool.

Generates a docker-compose.yml file with application and dependencies.
"""

import json
from pathlib import Path
from typing import Any

import yaml


async def create_compose(
    project_path: str,
    service_name: str = "app",
    dependencies: list[str] | None = None,
    expose_ports: bool = True,
    output_path: str = "",
) -> str:
    """
    Generate a docker-compose.yml file.

    Args:
        project_path: Path to the Java project
        service_name: Name for the main service
        dependencies: Additional services to include
        expose_ports: Whether to expose service ports to host
        output_path: Path to write docker-compose.yml

    Returns:
        JSON string with generation results
    """
    results: dict[str, Any] = {
        "success": False,
        "project_path": project_path,
        "compose_path": "",
        "services": [],
        "compose_content": "",
    }

    if dependencies is None:
        dependencies = []

    try:
        project_dir = Path(project_path)

        if not project_dir.exists():
            results["error"] = f"Project path does not exist: {project_path}"
            return json.dumps(results, indent=2)

        # Build compose configuration
        compose_config = _build_compose_config(
            project_dir, service_name, dependencies, expose_ports
        )

        # Convert to YAML
        compose_content = yaml.dump(
            compose_config, default_flow_style=False, sort_keys=False, allow_unicode=True
        )
        results["compose_content"] = compose_content
        results["services"] = list(compose_config.get("services", {}).keys())

        # Write docker-compose.yml
        if output_path:
            compose_path = Path(output_path)
        else:
            compose_path = project_dir / "docker-compose.yml"

        with open(compose_path, "w") as f:
            f.write(compose_content)

        results["compose_path"] = str(compose_path)
        results["success"] = True
        results["message"] = f"docker-compose.yml created at {compose_path}"

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


def _build_compose_config(
    project_dir: Path, service_name: str, dependencies: list[str], expose_ports: bool
) -> dict[str, Any]:
    """Build docker-compose configuration dictionary."""

    compose: dict[str, Any] = {
        "version": "3.8",
        "services": {},
        "networks": {"app-network": {"driver": "bridge"}},
        "volumes": {},
    }

    # Main application service
    app_service: dict[str, Any] = {
        "build": {"context": ".", "dockerfile": "Dockerfile"},
        "container_name": f"{service_name}-container",
        "restart": "unless-stopped",
        "networks": ["app-network"],
        "environment": [],
        "depends_on": {},
    }

    if expose_ports:
        app_service["ports"] = ["8080:8080"]

    # Add dependency services
    dep_configs = _get_dependency_configs()

    for dep in dependencies:
        dep_lower = dep.lower()
        if dep_lower in dep_configs:
            dep_config = dep_configs[dep_lower]
            compose["services"][dep_lower] = dep_config["service"]

            if "volume" in dep_config:
                compose["volumes"][dep_config["volume"]["name"]] = dep_config["volume"]["config"]

            # Add to app dependencies
            if dep_config.get("health_check"):
                app_service["depends_on"][dep_lower] = {"condition": "service_healthy"}
            else:
                app_service["depends_on"][dep_lower] = {"condition": "service_started"}

            # Add environment variables
            if dep_config.get("env_vars"):
                app_service["environment"].extend(dep_config["env_vars"])

    # Convert environment list to proper format if not empty
    if app_service["environment"]:
        env_list = app_service["environment"]
        app_service["environment"] = env_list
    else:
        del app_service["environment"]

    # Clean up empty depends_on
    if not app_service["depends_on"]:
        del app_service["depends_on"]

    compose["services"][service_name] = app_service

    # Clean up empty volumes
    if not compose["volumes"]:
        del compose["volumes"]

    return compose


def _get_dependency_configs() -> dict[str, Any]:
    """Get configurations for common dependencies."""
    return {
        "postgres": {
            "service": {
                "image": "postgres:15-alpine",
                "container_name": "postgres-db",
                "restart": "unless-stopped",
                "networks": ["app-network"],
                "environment": ["POSTGRES_USER=app", "POSTGRES_PASSWORD=app", "POSTGRES_DB=appdb"],
                "ports": ["5432:5432"],
                "volumes": ["postgres-data:/var/lib/postgresql/data"],
                "healthcheck": {
                    "test": ["CMD-SHELL", "pg_isready -U app -d appdb"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                },
            },
            "volume": {"name": "postgres-data", "config": {"driver": "local"}},
            "health_check": True,
            "env_vars": [
                "SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/appdb",
                "SPRING_DATASOURCE_USERNAME=app",
                "SPRING_DATASOURCE_PASSWORD=app",
            ],
        },
        "mysql": {
            "service": {
                "image": "mysql:8",
                "container_name": "mysql-db",
                "restart": "unless-stopped",
                "networks": ["app-network"],
                "environment": [
                    "MYSQL_ROOT_PASSWORD=root",
                    "MYSQL_USER=app",
                    "MYSQL_PASSWORD=app",
                    "MYSQL_DATABASE=appdb",
                ],
                "ports": ["3306:3306"],
                "volumes": ["mysql-data:/var/lib/mysql"],
                "healthcheck": {
                    "test": ["CMD", "mysqladmin", "ping", "-h", "localhost", "-u", "app", "-papp"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                },
            },
            "volume": {"name": "mysql-data", "config": {"driver": "local"}},
            "health_check": True,
            "env_vars": [
                "SPRING_DATASOURCE_URL=jdbc:mysql://mysql:3306/appdb",
                "SPRING_DATASOURCE_USERNAME=app",
                "SPRING_DATASOURCE_PASSWORD=app",
            ],
        },
        "redis": {
            "service": {
                "image": "redis:7-alpine",
                "container_name": "redis-cache",
                "restart": "unless-stopped",
                "networks": ["app-network"],
                "ports": ["6379:6379"],
                "volumes": ["redis-data:/data"],
                "healthcheck": {
                    "test": ["CMD", "redis-cli", "ping"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                },
            },
            "volume": {"name": "redis-data", "config": {"driver": "local"}},
            "health_check": True,
            "env_vars": ["SPRING_REDIS_HOST=redis", "SPRING_REDIS_PORT=6379"],
        },
        "mongodb": {
            "service": {
                "image": "mongo:6",
                "container_name": "mongodb",
                "restart": "unless-stopped",
                "networks": ["app-network"],
                "environment": [
                    "MONGO_INITDB_ROOT_USERNAME=app",
                    "MONGO_INITDB_ROOT_PASSWORD=app",
                    "MONGO_INITDB_DATABASE=appdb",
                ],
                "ports": ["27017:27017"],
                "volumes": ["mongodb-data:/data/db"],
                "healthcheck": {
                    "test": ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                },
            },
            "volume": {"name": "mongodb-data", "config": {"driver": "local"}},
            "health_check": True,
            "env_vars": [
                "SPRING_DATA_MONGODB_URI=mongodb://app:app@mongodb:27017/appdb?authSource=admin"
            ],
        },
        "rabbitmq": {
            "service": {
                "image": "rabbitmq:3-management-alpine",
                "container_name": "rabbitmq",
                "restart": "unless-stopped",
                "networks": ["app-network"],
                "environment": ["RABBITMQ_DEFAULT_USER=app", "RABBITMQ_DEFAULT_PASS=app"],
                "ports": ["5672:5672", "15672:15672"],
                "volumes": ["rabbitmq-data:/var/lib/rabbitmq"],
                "healthcheck": {
                    "test": ["CMD", "rabbitmq-diagnostics", "-q", "ping"],
                    "interval": "10s",
                    "timeout": "5s",
                    "retries": 5,
                    "start_period": "30s",
                },
            },
            "volume": {"name": "rabbitmq-data", "config": {"driver": "local"}},
            "health_check": True,
            "env_vars": [
                "SPRING_RABBITMQ_HOST=rabbitmq",
                "SPRING_RABBITMQ_PORT=5672",
                "SPRING_RABBITMQ_USERNAME=app",
                "SPRING_RABBITMQ_PASSWORD=app",
            ],
        },
        "kafka": {
            "service": {
                "image": "confluentinc/cp-kafka:7.5.0",
                "container_name": "kafka",
                "restart": "unless-stopped",
                "networks": ["app-network"],
                "environment": [
                    "KAFKA_NODE_ID=1",
                    "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT",
                    "KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092",
                    "KAFKA_PROCESS_ROLES=broker,controller",
                    "KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka:29093",
                    "KAFKA_LISTENERS=PLAINTEXT://kafka:29092,CONTROLLER://kafka:29093,PLAINTEXT_HOST://0.0.0.0:9092",
                    "KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT",
                    "KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER",
                    "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1",
                    "CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk",
                ],
                "ports": ["9092:9092"],
                "volumes": ["kafka-data:/var/lib/kafka/data"],
                "healthcheck": {
                    "test": [
                        "CMD",
                        "kafka-broker-api-versions",
                        "--bootstrap-server",
                        "localhost:9092",
                    ],
                    "interval": "10s",
                    "timeout": "10s",
                    "retries": 5,
                    "start_period": "30s",
                },
            },
            "volume": {"name": "kafka-data", "config": {"driver": "local"}},
            "health_check": True,
            "env_vars": ["SPRING_KAFKA_BOOTSTRAP_SERVERS=kafka:29092"],
        },
    }
