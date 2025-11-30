"""Pytest configuration and fixtures."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


# Load .env file before running tests
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)


@pytest.fixture(scope="session")
def sample_java_project(tmp_path_factory):
    """Create a sample Java Maven project for testing."""
    project_path = tmp_path_factory.mktemp("test-project")

    # Create pom.xml
    pom_xml = project_path / "pom.xml"
    pom_xml.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <groupId>com.example</groupId>
    <artifactId>test-project</artifactId>
    <version>1.0.0</version>

    <properties>
        <java.version>17</java.version>
        <maven.compiler.source>17</maven.compiler.source>
        <maven.compiler.target>17</maven.compiler.target>
    </properties>

    <dependencies>
        <!-- Intentionally old version for testing -->
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-core</artifactId>
            <version>5.0.0.RELEASE</version>
        </dependency>
        <dependency>
            <groupId>junit</groupId>
            <artifactId>junit</artifactId>
            <version>4.12</version>
            <scope>test</scope>
        </dependency>
    </dependencies>
</project>
""")

    # Create basic Java source file
    src_dir = project_path / "src" / "main" / "java" / "com" / "example"
    src_dir.mkdir(parents=True)

    java_file = src_dir / "HelloWorld.java"
    java_file.write_text("""package com.example;

public class HelloWorld {
    public String sayHello() {
        return "Hello, World!";
    }
}
""")

    return project_path
