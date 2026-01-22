# CLI Reference

**Purpose**: Complete reference for TestBoost CLI commands and exit codes
**Version**: 1.0.0

---

## Installation

```bash
# Clone the repository
git clone https://github.com/cheche71/TestBoost.git
cd TestBoost

# Install in development mode
pip install -e .

# Or via poetry
poetry install
```

> **Note**: TestBoost n'est pas encore publié sur PyPI. Utilisez l'installation locale ci-dessus.

---

## Prerequisites

### PostgreSQL Database

TestBoost requires a PostgreSQL database for session management. Start it using Docker Compose:

```bash
# Start PostgreSQL only
docker compose up -d postgres

# Verify it's running
docker compose ps
```

The database will be available at `localhost:5433` with:
- **User**: `testboost`
- **Password**: `testboost`
- **Database**: `testboost`

### Environment Variables

Create a `.env` file or set these environment variables:

```bash
# Required - At least one LLM provider
export GOOGLE_API_KEY="your-google-api-key"      # For Gemini
export ANTHROPIC_API_KEY="your-anthropic-key"   # For Claude
export OPENAI_API_KEY="your-openai-key"         # For GPT-4

# Optional - API authentication
export TESTBOOST_API_KEY="your-api-key"

# Optional - LangSmith tracing
export LANGSMITH_API_KEY="your-langsmith-key"
export LANGSMITH_TRACING=true
```

### Docker (Optional)

For deployment features, ensure Docker and Docker Compose are installed and running:

```bash
docker --version
docker compose version
```

---

## Global Options

### Version

Show TestBoost version and exit.

```bash
boost --version
boost -v
```

---

## Top-Level Commands

### boost init

Initialize TestBoost for a Java project.

```bash
boost init [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to the Java project to initialize (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only, debug | interactive |
| `--force` | `-f` | Overwrite existing configuration | false |

**Example**:
```bash
# Initialize in current directory
boost init

# Initialize with force overwrite
boost init ./my-project --force
```

---

### boost analyze

Analyze a Java project for test generation opportunities.

This is a shortcut for `boost tests analyze`.

```bash
boost analyze [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to the Java project to analyze (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--verbose` | `-v` | Show detailed output | false |

**Example**:
```bash
# Analyze current project
boost analyze

# Analyze with verbose output
boost analyze ./my-project -v
```

---

### boost generate

Generate tests for a Java project.

This is a shortcut for `boost tests generate`.

```bash
boost generate [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to the Java project (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only | interactive |
| `--target` | `-t` | Specific class or package to generate tests for | all |
| `--mutation-score` | | Target mutation score percentage | 80 |
| `--dry-run` | | Analyze without generating tests | false |

**Example**:
```bash
# Generate tests for current project
boost generate

# Generate tests for specific class
boost generate ./my-project -t com.example.MyService
```

---

### boost maven

Perform Maven maintenance tasks.

This is a shortcut for `boost maintenance run` or `boost maintenance list`.

```bash
boost maven [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to the Maven project (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode | interactive |
| `--check-updates` | `-u` | Check for dependency updates (list only) | false |
| `--dry-run` | `-n` | Analyze without applying changes | false |

**Example**:
```bash
# Run full maintenance workflow
boost maven ./my-project

# List available updates only
boost maven ./my-project -u
```

---

### boost serve

Start the TestBoost API server.

```bash
boost serve [OPTIONS]
```

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--host` | `-h` | Host to bind the server to | 0.0.0.0 |
| `--port` | `-p` | Port to bind the server to | 8000 |
| `--reload` | `-r` | Enable auto-reload for development | false |

**Example**:
```bash
# Start server with defaults
boost serve

# Start on custom port with reload
boost serve -p 3000 -r
```

---

## Maintenance Commands

### boost maintenance run

Run Maven project maintenance workflow.

```bash
boost maintenance run [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only, debug | interactive |
| `--auto-approve` | `-y` | Automatically approve all updates | false |
| `--dry-run` | `-n` | Analyze without applying changes | false |
| `--skip-tests` | | Skip test validation | false |
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# Interactive mode (default)
boost maintenance run ./my-project

# Autonomous mode with auto-approve
boost maintenance run ./my-project -m autonomous -y

# Analysis only (dry-run)
boost maintenance run ./my-project -n

# JSON output for CI/CD
boost maintenance run ./my-project -m autonomous -y -f json
```

---

### boost maintenance list

List available dependency updates for a Maven project.

```bash
boost maintenance list [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--include-snapshots` | | Include SNAPSHOT versions | false |
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# List available updates
boost maintenance list ./my-project

# Include SNAPSHOT versions
boost maintenance list ./my-project --include-snapshots

# JSON output for scripting
boost maintenance list ./my-project -f json
```

Shows all dependencies with available updates and any known security vulnerabilities.

---

### boost maintenance status

Check the status of a maintenance session.

```bash
boost maintenance status <SESSION_ID> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--watch` | `-w` | Continuously watch for updates (not yet implemented) | false |

**Example**:
```bash
# Check session status
boost maintenance status abc123-def456-ghi789
```

Use the session ID returned from `maintenance run` to track the progress of a running maintenance workflow.

---

### boost maintenance sessions

List all maintenance sessions.

```bash
boost maintenance sessions [OPTIONS]
```

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--status` | `-s` | Filter by status: pending, in_progress, completed, failed, paused | all |
| `--type` | `-t` | Filter by session type | all |
| `--limit` | `-l` | Maximum number of results | 20 |
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# List all sessions
boost maintenance sessions

# List only in-progress sessions
boost maintenance sessions -s in_progress

# JSON output
boost maintenance sessions -f json
```

---

### boost maintenance steps

List steps for a session.

```bash
boost maintenance steps <SESSION_ID> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# List steps for a session
boost maintenance steps abc123-def456
```

---

### boost maintenance step

Execute a specific step for a session.

```bash
boost maintenance step <SESSION_ID> <STEP_CODE> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)
- `STEP_CODE`: Step code to execute (e.g., analyze, apply_updates)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# Execute the analyze step
boost maintenance step abc123-def456 analyze

# Execute apply_updates step
boost maintenance step abc123-def456 apply_updates
```

---

### boost maintenance pause

Pause a running session.

```bash
boost maintenance pause <SESSION_ID> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--reason` | Reason for pausing | - |

**Example**:
```bash
# Pause a session
boost maintenance pause abc123-def456

# Pause with reason
boost maintenance pause abc123-def456 --reason "Waiting for approval"
```

---

### boost maintenance resume

Resume a paused session.

```bash
boost maintenance resume <SESSION_ID> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--checkpoint` | Checkpoint ID to resume from | latest |

**Example**:
```bash
# Resume a session
boost maintenance resume abc123-def456

# Resume from specific checkpoint
boost maintenance resume abc123-def456 --checkpoint checkpoint-xyz
```

---

### boost maintenance artifacts

Get artifacts for a session.

```bash
boost maintenance artifacts <SESSION_ID> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--type` | `-t` | Filter by artifact type | all |
| `--output` | `-o` | Save to file | - |
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# List all artifacts
boost maintenance artifacts abc123-def456

# Save artifacts to JSON file
boost maintenance artifacts abc123-def456 -o artifacts.json
```

---

### boost maintenance cancel

Cancel a running session.

```bash
boost maintenance cancel <SESSION_ID> [OPTIONS]
```

**Arguments**:
- `SESSION_ID`: Session UUID (required)

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--force` | Skip confirmation prompt | false |

**Example**:
```bash
# Cancel with confirmation
boost maintenance cancel abc123-def456

# Cancel without confirmation (CI/CD)
boost maintenance cancel abc123-def456 --force
```

---

## Test Commands

### boost tests generate

Generate tests for Java classes.

```bash
boost tests generate [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only, debug | interactive |
| `--target` | `-t` | Specific class or package to target | all |
| `--mutation-score` | | Target mutation score percentage | 80 |
| `--integration/--no-integration` | | Include integration tests | true |
| `--snapshot/--no-snapshot` | | Generate snapshot tests | true |
| `--output` | `-o` | Output directory for generated tests | auto |
| `--dry-run` | | Preview without generating | false |

**Example**:
```bash
# Generate all tests
boost tests generate ./my-project

# Generate tests for specific class
boost tests generate ./my-project -t com.example.MyService

# Generate with custom mutation score target
boost tests generate ./my-project --mutation-score 90

# Dry-run (analyze without generating)
boost tests generate ./my-project --dry-run

# With verbose output
boost tests generate ./my-project -v
```

---

### boost tests analyze

Analyze a Java project for test generation.

```bash
boost tests analyze [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--verbose` | `-v` | Show detailed output | false |

**Example**:
```bash
# Analyze project
boost tests analyze ./my-project

# Analyze with verbose output
boost tests analyze ./my-project -v
```

Displays:
- Project type and build system
- Java version and frameworks
- Number of source classes and existing tests
- Detected test naming conventions
- Assertion styles and mocking patterns

---

### boost tests mutation

Run mutation testing on a Java project.

```bash
boost tests mutation [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--classes` | `-c` | Target classes to mutate (glob pattern) | all |
| `--tests` | `-t` | Target tests to run (glob pattern) | all |
| `--verbose` | `-v` | Show detailed output | false |

**Example**:
```bash
# Run mutation testing on entire project
boost tests mutation ./my-project

# Run on specific classes
boost tests mutation ./my-project -c "com.example.service.*"

# Run with specific tests
boost tests mutation ./my-project -t "com.example.*Test"

# Verbose output
boost tests mutation ./my-project -v
```

Uses PIT mutation testing to measure test effectiveness. Reports:
- Total mutants generated
- Killed vs survived mutants
- Mutation score percentage
- Classes with low mutation scores

---

### boost tests recommendations

Show test improvement recommendations.

```bash
boost tests recommendations [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--target` | `-t` | Target mutation score percentage | 80 |
| `--strategy` | `-s` | Prioritization strategy: quick_wins, high_impact, balanced | balanced |

**Example**:
```bash
# Get recommendations with default settings
boost tests recommendations ./my-project

# Target 90% mutation score
boost tests recommendations ./my-project -t 90

# Use quick wins strategy (easiest improvements first)
boost tests recommendations ./my-project -s quick_wins

# Use high impact strategy (biggest improvements first)
boost tests recommendations ./my-project -s high_impact
```

Analyzes mutation testing results and provides prioritized recommendations for improving test effectiveness.

---

### boost tests impact

Analyze impact of uncommitted changes.

```bash
boost tests impact [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Save report to file (default: stdout) | - |
| `--verbose` | `-v` | Show progress and debug info | false |
| `--chunk-size` | | Max lines per chunk for large diffs | 500 |

**Example**:
```bash
# Analyze uncommitted changes
boost tests impact ./my-project

# Save report to file
boost tests impact ./my-project -o impact-report.json

# With verbose output
boost tests impact ./my-project -v
```

Detects uncommitted changes in your working directory, classifies each change by category and risk level, and generates an impact report with test requirements.

**Exit codes**:
- `0` - Success, all impacts covered or no business-critical uncovered
- `1` - Business-critical impacts have no tests (for CI enforcement)

---

## Deploy Commands

### boost deploy run

Deploy a Java project using Docker.

```bash
boost deploy run [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Java project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | | Execution mode: interactive, autonomous, analysis_only, debug | interactive |
| `--dependency` | `-d` | Additional service dependencies (postgres, mysql, redis, mongodb, rabbitmq, kafka) | - |
| `--endpoint` | `-e` | Health check endpoints (e.g., 'http://localhost:8080/health') | - |
| `--skip-health` | | Skip health check validation | false |
| `--format` | `-f` | Output format: rich, json | rich |

**Example**:
```bash
# Deploy with default settings
boost deploy run ./my-project

# Deploy with PostgreSQL dependency
boost deploy run ./my-project -d postgres

# Deploy with health check endpoint
boost deploy run ./my-project -e http://localhost:8080/health

# Deploy without health check validation
boost deploy run ./my-project --skip-health

# JSON output for CI/CD
boost deploy run ./my-project -f json
```

---

### boost deploy stop

Stop a Docker deployment.

```bash
boost deploy stop [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--volumes` | `-v` | Remove associated volumes | false |

**Example**:
```bash
# Stop deployment
boost deploy stop ./my-project

# Stop and remove volumes
boost deploy stop ./my-project -v
```

---

### boost deploy logs

Show logs from deployed containers.

```bash
boost deploy logs [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--service` | `-s` | Specific service to show logs for | all |
| `--tail` | `-n` | Number of lines to show | 100 |
| `--follow` | `-f` | Follow log output | false |

**Example**:
```bash
# Show logs from all containers
boost deploy logs ./my-project

# Show last 50 lines
boost deploy logs ./my-project -n 50

# Follow logs from specific service
boost deploy logs ./my-project -s app -f
```

---

### boost deploy status

Check status of deployed containers.

```bash
boost deploy status [PROJECT_PATH]
```

**Arguments**:
- `PROJECT_PATH`: Path to project root (default: current directory)

**Example**:
```bash
# Check deployment status
boost deploy status ./my-project
```

---

### boost deploy build

Build Docker image without running containers.

```bash
boost deploy build [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to project root (default: current directory)

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--no-cache` | Build without using cache | false |

**Example**:
```bash
# Build Docker image
boost deploy build ./my-project

# Build without cache
boost deploy build ./my-project --no-cache
```

---

## Config Commands

### boost config validate

Validate agent configuration(s).

```bash
boost config validate [OPTIONS]
```

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--agent` | `-a` | Specific agent to validate | all |
| `--config-dir` | `-c` | Path to agent configurations directory | config/agents |

**Example**:
```bash
# Validate all agents
boost config validate

# Validate specific agent
boost config validate -a maven_maintenance

# Validate with custom config directory
boost config validate -c ./custom-config
```

---

### boost config show

Display agent configuration details.

```bash
boost config show <AGENT_NAME> [OPTIONS]
```

**Arguments**:
- `AGENT_NAME`: Agent name to display (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config-dir` | `-c` | Path to agent configurations directory | config/agents |
| `--format` | `-f` | Output format: pretty, json, yaml | pretty |

**Example**:
```bash
# Show config in pretty format
boost config show maven_maintenance

# Show as JSON
boost config show maven_maintenance -f json

# Show as YAML
boost config show maven_maintenance -f yaml
```

---

### boost config reload

Force reload configuration(s) from disk.

```bash
boost config reload [OPTIONS]
```

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--agent` | `-a` | Specific agent to reload | - |
| `--all` | | Reload all configurations | false |
| `--config-dir` | `-c` | Path to agent configurations directory | config/agents |

**Example**:
```bash
# Reload specific agent
boost config reload -a maven_maintenance

# Reload all configurations
boost config reload --all
```

---

### boost config backup

Create a timestamped backup of an agent configuration.

```bash
boost config backup <AGENT_NAME> [OPTIONS]
```

**Arguments**:
- `AGENT_NAME`: Agent name to backup (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config-dir` | `-c` | Path to agent configurations directory | config/agents |

**Example**:
```bash
# Backup an agent configuration
boost config backup maven_maintenance
```

Backups are stored in `config/agents/.backups/` with format: `<agent_name>_YYYYMMDD_HHMMSS.yaml`

---

### boost config list-backups

List available configuration backups.

```bash
boost config list-backups [OPTIONS]
```

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--agent` | `-a` | Filter by specific agent | all |
| `--config-dir` | `-c` | Path to agent configurations directory | config/agents |

**Example**:
```bash
# List all backups
boost config list-backups

# List backups for specific agent
boost config list-backups -a maven_maintenance
```

---

### boost config rollback

Rollback agent configuration to the latest backup.

```bash
boost config rollback <AGENT_NAME> [OPTIONS]
```

**Arguments**:
- `AGENT_NAME`: Agent name to rollback (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config-dir` | `-c` | Path to agent configurations directory | config/agents |
| `--yes` | `-y` | Skip confirmation prompt | false |

**Example**:
```bash
# Rollback with confirmation
boost config rollback maven_maintenance

# Rollback without confirmation
boost config rollback maven_maintenance -y
```

This will:
1. Create a backup of the current configuration
2. Restore the latest backup
3. Invalidate the config cache

---

## Audit Commands

### boost audit scan

Scan a Maven project for security vulnerabilities.

```bash
boost audit scan [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only, debug | interactive |
| `--severity` | `-s` | Minimum severity to report: all, low, medium, high, critical | all |
| `--format` | `-f` | Output format: rich, json, sarif | rich |
| `--output` | `-o` | Output file path | - |
| `--fail-on` | | Fail if vulnerabilities found at or above this severity | - |

**Example**:
```bash
# Scan current project
boost audit scan

# Scan with minimum severity filter
boost audit scan ./my-project -s high

# Output in SARIF format for security tools
boost audit scan ./my-project -f sarif -o results.sarif

# Fail CI if high or critical vulnerabilities found
boost audit scan ./my-project --fail-on high
```

---

### boost audit report

Generate a comprehensive HTML security report.

```bash
boost audit report [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to Maven project (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--output` | `-o` | Output file path | security-report.html |
| `--include-deps/--no-deps` | | Include dependency tree | true |

**Example**:
```bash
# Generate default report
boost audit report ./my-project

# Custom output path
boost audit report ./my-project -o audit-report.html

# Without dependency tree
boost audit report ./my-project --no-deps
```

---

## Exit Codes

### Standard Codes

| Code | Name | Description | Recommended Action |
|------|------|-------------|-------------------|
| 0 | SUCCESS | Command completed successfully | - |
| 1 | ERROR | General error occurred | Check logs |
| 2 | INVALID_ARGS | Invalid arguments provided | Check command syntax |
| 3 | PROJECT_NOT_FOUND | Project path not found | Verify project path |
| 4 | PROJECT_LOCKED | Project locked by another session | Wait or cancel existing session |
| 5 | BASELINE_TESTS_FAILED | Baseline tests failed | Fix existing tests first |
| 6 | LLM_ERROR | LLM provider error | Check credentials and quotas |
| 7 | DOCKER_ERROR | Docker error | Check Docker is running |
| 8 | TIMEOUT | Operation timed out | Increase timeout or simplify |

### Extended Codes

| Code | Name | Description | Recommended Action |
|------|------|-------------|-------------------|
| 10 | WORKFLOW_ERROR | Workflow execution failed | Check session logs |
| 20 | BUILD_FAILED | Maven build failed | Fix build errors |
| 30 | CONFIG_ERROR | Configuration invalid | Run `boost config validate` |
| 31 | CONNECTION_ERROR | Connection failed | Check network/services |
| 32 | PERMISSION_DENIED | Access denied | Check file permissions |
| 33 | CANCELLED | Operation cancelled by user | - |

### Using Exit Codes

**Bash script example**:
```bash
#!/bin/bash

boost maintenance ./my-project -m autonomous

case $? in
    0)
        echo "Maintenance completed successfully"
        ;;
    5)
        echo "Baseline tests failed - fix tests before maintenance"
        exit 1
        ;;
    6)
        echo "LLM error - check API credentials"
        exit 1
        ;;
    *)
        echo "Maintenance failed with exit code $?"
        exit 1
        ;;
esac
```

**CI/CD example (GitHub Actions)**:
```yaml
- name: Run TestBoost Maintenance
  run: boost maintenance ./my-project -m autonomous
  continue-on-error: true
  id: maintenance

- name: Check Results
  run: |
    if [ ${{ steps.maintenance.outcome }} == 'failure' ]; then
      echo "Maintenance failed"
      exit 1
    fi
```

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TESTBOOST_API_KEY` | API authentication key | - |
| `ANTHROPIC_API_KEY` | Anthropic API key | - |
| `GOOGLE_API_KEY` | Google API key | - |
| `OPENAI_API_KEY` | OpenAI API key | - |
| `LANGSMITH_API_KEY` | LangSmith API key | - |
| `LANGSMITH_TRACING` | Enable LangSmith tracing | false |
| `TESTBOOST_LOG_LEVEL` | Logging level | INFO |

---

## Configuration File

Default location: `~/.testboost/config.yaml`

```yaml
# LLM Configuration
llm_provider: anthropic  # anthropic, google-genai, openai
model: claude-sonnet-4-5-20250929

# Timeout Settings
llm_timeout: 120
startup_timeout: 5

# Data Retention
session_retention_days: 365

# Database
database_url: postgresql+asyncpg://testboost:testboost@localhost:5433/testboost
```

---

## Output Formats

### Text (default)

Human-readable output with colors (when terminal supports it).

```
TestBoost Maintenance Session
=============================
Project: ./my-project
Mode: interactive
Status: completed

Steps:
  [x] Analyze project structure
  [x] Check dependencies
  [x] Update outdated dependencies
  [x] Validate changes

Result: SUCCESS
Duration: 45.2s
```

### JSON

Machine-readable JSON output for scripting/CI.

```bash
boost maintenance ./my-project --output json
```

```json
{
  "session_id": "abc-123",
  "status": "completed",
  "duration_seconds": 45.2,
  "steps": [
    {"name": "analyze", "status": "completed"},
    {"name": "update", "status": "completed"},
    {"name": "validate", "status": "completed"}
  ],
  "result": {
    "dependencies_updated": 3,
    "tests_passed": true
  }
}
```

---

## Command Summary

### Top-Level Commands
| Command | Description |
|---------|-------------|
| `boost --version` | Show version |
| `boost init` | Initialize TestBoost for a project |
| `boost analyze` | Analyze project (shortcut) |
| `boost generate` | Generate tests (shortcut) |
| `boost maven` | Maven maintenance (shortcut) |
| `boost status` | Check session status |
| `boost serve` | Start API server |

### Maintenance Commands
| Command | Description |
|---------|-------------|
| `boost maintenance run` | Run maintenance workflow |
| `boost maintenance list` | List available updates |
| `boost maintenance status` | Check session status |
| `boost maintenance sessions` | List all sessions |
| `boost maintenance steps` | List session steps |
| `boost maintenance step` | Execute a step |
| `boost maintenance pause` | Pause a session |
| `boost maintenance resume` | Resume a session |
| `boost maintenance artifacts` | Get session artifacts |
| `boost maintenance cancel` | Cancel a session |

### Test Commands
| Command | Description |
|---------|-------------|
| `boost tests generate` | Generate tests |
| `boost tests analyze` | Analyze project |
| `boost tests mutation` | Run mutation testing |
| `boost tests recommendations` | Show recommendations |
| `boost tests impact` | Analyze change impact |

### Deploy Commands
| Command | Description |
|---------|-------------|
| `boost deploy run` | Deploy with Docker |
| `boost deploy stop` | Stop deployment |
| `boost deploy logs` | Show container logs |
| `boost deploy status` | Check deployment status |
| `boost deploy build` | Build image only |

### Config Commands
| Command | Description |
|---------|-------------|
| `boost config validate` | Validate configurations |
| `boost config show` | Show agent config |
| `boost config reload` | Reload configurations |
| `boost config backup` | Backup agent config |
| `boost config list-backups` | List backups |
| `boost config rollback` | Rollback to backup |

### Audit Commands
| Command | Description |
|---------|-------------|
| `boost audit scan` | Scan for vulnerabilities |
| `boost audit report` | Generate security report |
