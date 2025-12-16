# MCP Tools Reference

**Purpose**: Complete reference for all MCP tools available in TestBoost
**Version**: 1.0.0

---

## Overview

TestBoost exposes functionality through Model Context Protocol (MCP) servers. Each server provides domain-specific tools that can be invoked by LLM agents.

## Available Servers

| Server | Description | Tools |
|--------|-------------|-------|
| maven-maintenance | Maven project maintenance | analyze, compile, run_tests, package |
| test-generator | Test generation and analysis | analyze, generate_unit, generate_integration, generate_snapshot, conventions, analyze_mutants, killer_tests, mutation |
| docker-deployment | Docker deployment management | compose, deploy, dockerfile, health, logs |
| git-maintenance | Git operations | status, branch, commit |
| container-runtime | Container execution | execute, maven, destroy |
| pit-recommendations | PIT mutation recommendations | analyze, prioritize, recommend |

---

## Maven Maintenance Server

### `maven_analyze`

Analyzes a Maven project structure, dependencies, and configuration.

**Input Schema**:
```python
class MavenAnalyzeInput(BaseModel):
    project_path: str  # Path to Maven project root
    include_dependencies: bool = True  # Include dependency analysis
    check_outdated: bool = True  # Check for outdated dependencies
```

**Output Schema**:
```python
class MavenAnalyzeOutput(BaseModel):
    pom_path: str  # Path to pom.xml
    artifact_id: str  # Maven artifact ID
    group_id: str  # Maven group ID
    version: str  # Project version
    dependencies: list[Dependency]  # List of dependencies
    outdated_dependencies: list[OutdatedDependency]  # Outdated deps
    modules: list[str]  # Multi-module children
```

**Timeout**: 30 seconds

---

### `maven_compile`

Compiles a Maven project.

**Input Schema**:
```python
class MavenCompileInput(BaseModel):
    project_path: str  # Path to Maven project root
    clean: bool = True  # Run clean before compile
    skip_tests: bool = True  # Skip test compilation
```

**Output Schema**:
```python
class MavenCompileOutput(BaseModel):
    success: bool  # Compilation succeeded
    output: str  # Maven output
    errors: list[CompileError]  # Compilation errors
    warnings: list[str]  # Warnings
```

**Timeout**: 120 seconds (2 minutes)

---

### `maven_run_tests`

Runs Maven tests with optional filtering.

**Input Schema**:
```python
class MavenRunTestsInput(BaseModel):
    project_path: str  # Path to Maven project root
    test_class: str | None = None  # Specific test class
    test_method: str | None = None  # Specific test method
    include_integration: bool = False  # Include integration tests
```

**Output Schema**:
```python
class MavenRunTestsOutput(BaseModel):
    success: bool  # All tests passed
    total: int  # Total tests run
    passed: int  # Tests passed
    failed: int  # Tests failed
    skipped: int  # Tests skipped
    duration_seconds: float  # Total duration
    failures: list[TestFailure]  # Failed test details
```

**Timeout**: 300 seconds (5 minutes)

---

### `maven_package`

Packages a Maven project into JAR/WAR.

**Input Schema**:
```python
class MavenPackageInput(BaseModel):
    project_path: str  # Path to Maven project root
    skip_tests: bool = True  # Skip tests during packaging
```

**Output Schema**:
```python
class MavenPackageOutput(BaseModel):
    success: bool  # Packaging succeeded
    artifact_path: str  # Path to built artifact
    artifact_size_bytes: int  # Size of artifact
```

**Timeout**: 180 seconds (3 minutes)

---

## Test Generator Server

### `analyze_class`

Analyzes a Java class for test generation.

**Input Schema**:
```python
class AnalyzeClassInput(BaseModel):
    file_path: str  # Path to Java source file
    project_path: str  # Path to project root
```

**Output Schema**:
```python
class AnalyzeClassOutput(BaseModel):
    class_name: str  # Fully qualified class name
    methods: list[MethodInfo]  # Public methods
    dependencies: list[str]  # Class dependencies
    complexity: int  # Cyclomatic complexity
    test_recommendations: list[str]  # Recommended test types
```

**Timeout**: 15 seconds

---

### `generate_unit_tests`

Generates unit tests for a Java class.

**Input Schema**:
```python
class GenerateUnitTestsInput(BaseModel):
    file_path: str  # Path to Java source file
    project_path: str  # Path to project root
    coverage_target: float = 0.8  # Target line coverage (0.0-1.0)
```

**Output Schema**:
```python
class GenerateUnitTestsOutput(BaseModel):
    test_file_path: str  # Path to generated test file
    test_count: int  # Number of tests generated
    estimated_coverage: float  # Estimated coverage
```

**Timeout**: 60 seconds

---

### `generate_integration_tests`

Generates integration tests for a class with dependencies.

**Input Schema**:
```python
class GenerateIntegrationTestsInput(BaseModel):
    file_path: str  # Path to Java source file
    project_path: str  # Path to project root
    dependencies_to_test: list[str] | None = None  # Specific deps
```

**Output Schema**:
```python
class GenerateIntegrationTestsOutput(BaseModel):
    test_file_path: str  # Path to generated test file
    test_count: int  # Number of tests generated
    mocked_dependencies: list[str]  # Dependencies mocked
```

**Timeout**: 90 seconds

---

## Docker Deployment Server

### `docker_deploy`

Deploys a project using Docker Compose.

**Input Schema**:
```python
class DockerDeployInput(BaseModel):
    project_path: str  # Path to project root
    compose_file: str = "docker-compose.yml"  # Compose file name
    environment: str = "development"  # Target environment
```

**Output Schema**:
```python
class DockerDeployOutput(BaseModel):
    success: bool  # Deployment succeeded
    containers: list[ContainerInfo]  # Deployed containers
    network: str  # Docker network name
    health_status: dict[str, str]  # Container health statuses
```

**Timeout**: 300 seconds (5 minutes)

---

### `docker_health`

Checks health of deployed containers.

**Input Schema**:
```python
class DockerHealthInput(BaseModel):
    project_path: str  # Path to project root
    container_name: str | None = None  # Specific container
```

**Output Schema**:
```python
class DockerHealthOutput(BaseModel):
    containers: list[ContainerHealth]  # Health per container
    overall_status: str  # "healthy", "unhealthy", "starting"
```

**Timeout**: 30 seconds

---

## Git Maintenance Server

### `git_status`

Gets current Git repository status.

**Input Schema**:
```python
class GitStatusInput(BaseModel):
    project_path: str  # Path to Git repository
```

**Output Schema**:
```python
class GitStatusOutput(BaseModel):
    branch: str  # Current branch name
    staged: list[str]  # Staged file paths
    modified: list[str]  # Modified file paths
    untracked: list[str]  # Untracked file paths
    ahead: int  # Commits ahead of remote
    behind: int  # Commits behind remote
```

**Timeout**: 10 seconds

---

### `git_commit`

Creates a Git commit with specified files.

**Input Schema**:
```python
class GitCommitInput(BaseModel):
    project_path: str  # Path to Git repository
    message: str  # Commit message
    files: list[str] | None = None  # Files to stage (None = all)
```

**Output Schema**:
```python
class GitCommitOutput(BaseModel):
    commit_hash: str  # New commit SHA
    files_committed: list[str]  # Files included
    branch: str  # Branch committed to
```

**Timeout**: 30 seconds

---

## Error Handling

All tools follow consistent error handling:

```python
class ToolError(BaseModel):
    error_code: str  # Machine-readable error code
    message: str  # Human-readable message
    context: dict  # Additional context for debugging
```

Common error codes:
- `INVALID_INPUT`: Input validation failed
- `TIMEOUT`: Operation timed out
- `NOT_FOUND`: Resource not found
- `PERMISSION_DENIED`: Access denied
- `EXTERNAL_ERROR`: External service error (Maven, Docker, etc.)

---

## Timeout Categories

| Category | Default | Max | Examples |
|----------|---------|-----|----------|
| Quick | 10s | 30s | git_status, analyze_class |
| Standard | 60s | 120s | compile, generate_unit |
| Extended | 300s | 600s | run_tests, deploy |

Timeouts are configurable per-tool via agent YAML configuration.
