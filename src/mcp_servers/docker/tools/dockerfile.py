"""
Create Dockerfile tool.

Generates a Dockerfile for Java projects based on detected configuration.
"""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


async def create_dockerfile(
    project_path: str, java_version: str = "", base_image: str = "", output_path: str = ""
) -> str:
    """
    Generate a Dockerfile for a Java project.

    Args:
        project_path: Path to the Java project
        java_version: Java version to use (auto-detected if not specified)
        base_image: Base Docker image to use
        output_path: Path to write the Dockerfile

    Returns:
        JSON string with generation results
    """
    results: dict[str, Any] = {
        "success": False,
        "project_path": project_path,
        "dockerfile_path": "",
        "detected_config": {},
        "dockerfile_content": "",
    }

    try:
        project_dir = Path(project_path)

        if not project_dir.exists():
            results["error"] = f"Project path does not exist: {project_path}"
            return json.dumps(results, indent=2)

        # Detect project configuration
        config = await _detect_project_config(project_dir)
        results["detected_config"] = config

        # Override with provided values
        if java_version:
            config["java_version"] = java_version
        if base_image:
            config["base_image"] = base_image

        # Generate Dockerfile content
        dockerfile_content = _generate_dockerfile(config)
        results["dockerfile_content"] = dockerfile_content

        # Write Dockerfile
        if output_path:
            dockerfile_path = Path(output_path)
        else:
            dockerfile_path = project_dir / "Dockerfile"

        with open(dockerfile_path, "w") as f:
            f.write(dockerfile_content)

        results["dockerfile_path"] = str(dockerfile_path)
        results["success"] = True
        results["message"] = f"Dockerfile created at {dockerfile_path}"

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, indent=2)


async def _detect_project_config(project_dir: Path) -> dict[str, Any]:
    """Detect Java project configuration from pom.xml or build.gradle."""
    config: dict[str, Any] = {
        "java_version": "17",
        "build_tool": "maven",
        "artifact_type": "jar",
        "artifact_name": "app",
        "base_image": "",
        "port": 8080,
    }

    # Check for pom.xml (Maven)
    pom_file = project_dir / "pom.xml"
    if pom_file.exists():
        config["build_tool"] = "maven"

        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            ns = {"maven": "http://maven.apache.org/POM/4.0.0"}

            # Detect Java version
            for prop_path in [
                ".//maven:properties/maven:java.version",
                ".//maven:properties/maven:maven.compiler.source",
                ".//properties/java.version",
                ".//properties/maven.compiler.source",
            ]:
                prop = root.find(prop_path, ns)
                if prop is not None and prop.text:
                    config["java_version"] = prop.text.strip()
                    break

            # Detect artifact ID
            artifact_id = root.find("maven:artifactId", ns) or root.find("artifactId")
            if artifact_id is not None and artifact_id.text:
                config["artifact_name"] = artifact_id.text

            # Detect packaging type
            packaging = root.find("maven:packaging", ns) or root.find("packaging")
            if packaging is not None and packaging.text:
                config["artifact_type"] = packaging.text.lower()

            # Detect version
            version = root.find("maven:version", ns) or root.find("version")
            if version is not None and version.text:
                config["artifact_version"] = version.text

            # Check for Spring Boot
            for dep in root.findall(".//maven:dependency", ns) + root.findall(".//dependency"):
                group_id = dep.find("maven:groupId", ns) or dep.find("groupId")
                if group_id is not None and group_id.text:
                    if "spring-boot" in group_id.text:
                        config["is_spring_boot"] = True
                        break

        except ET.ParseError as e:
            config["parse_error"] = str(e)

    # Check for build.gradle (Gradle)
    gradle_file = project_dir / "build.gradle"
    if gradle_file.exists():
        config["build_tool"] = "gradle"

        try:
            with open(gradle_file) as f:
                content = f.read()

            # Simple detection of Java version
            if "sourceCompatibility" in content:
                import re

                match = re.search(r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?", content)
                if match:
                    config["java_version"] = match.group(1)

            # Check for Spring Boot plugin
            if "org.springframework.boot" in content:
                config["is_spring_boot"] = True

        except Exception as e:
            config["parse_error"] = str(e)

    # Set appropriate base image
    java_ver = config["java_version"]
    if not config.get("base_image"):
        config["base_image"] = f"eclipse-temurin:{java_ver}-jre-alpine"

    return config


def _generate_dockerfile(config: dict[str, Any]) -> str:
    """Generate Dockerfile content based on configuration."""
    java_version = config.get("java_version", "17")
    build_tool = config.get("build_tool", "maven")
    artifact_type = config.get("artifact_type", "jar")
    artifact_name = config.get("artifact_name", "app")
    port = config.get("port", 8080)
    is_spring_boot = config.get("is_spring_boot", False)

    # Build stage
    if build_tool == "maven":
        build_stage = f"""# Build stage
FROM maven:3.9-eclipse-temurin-{java_version} AS build
WORKDIR /app
COPY pom.xml .
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn package -DskipTests -B"""
    else:  # Gradle
        build_stage = f"""# Build stage
FROM gradle:8-jdk{java_version} AS build
WORKDIR /app
COPY build.gradle settings.gradle* ./
COPY gradle ./gradle
RUN gradle dependencies --no-daemon
COPY src ./src
RUN gradle build -x test --no-daemon"""

    # Runtime stage
    base_image = config.get("base_image", f"eclipse-temurin:{java_version}-jre-alpine")

    if artifact_type == "war":
        # WAR deployment (Tomcat)
        runtime_stage = f"""# Runtime stage
FROM tomcat:10-jdk{java_version}
WORKDIR /usr/local/tomcat
COPY --from=build /app/target/*.war ./webapps/ROOT.war
EXPOSE {port}
CMD ["catalina.sh", "run"]"""
    else:
        # JAR deployment
        if is_spring_boot:
            # Spring Boot layered JAR
            runtime_stage = f"""# Runtime stage
FROM {base_image}
WORKDIR /app

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# Copy the JAR
COPY --from=build /app/target/*.jar app.jar

# Spring Boot optimizations
ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

EXPOSE {port}
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \\
    CMD wget -q --spider http://localhost:{port}/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]"""
        else:
            # Standard JAR
            runtime_stage = f"""# Runtime stage
FROM {base_image}
WORKDIR /app

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup
USER appuser

# Copy the JAR
COPY --from=build /app/target/*.jar app.jar

ENV JAVA_OPTS="-XX:+UseContainerSupport -XX:MaxRAMPercentage=75.0"

EXPOSE {port}

ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]"""

    dockerfile = f"""{build_stage}

{runtime_stage}
"""

    return dockerfile
