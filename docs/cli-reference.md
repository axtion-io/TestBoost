# CLI Reference

**Purpose**: Complete reference for TestBoost CLI commands and exit codes
**Version**: 1.0.0

---

## Installation

```bash
# Clone the repository
git clone https://github.com/axtion-io/TestBoost.git
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

## Commands

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

**Other maintenance commands**:
```bash
# List available updates
boost maintenance list ./my-project

# Check session status
boost maintenance status <session-id>
```

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
```

**Other test commands**:
```bash
# Analyze project for test opportunities
boost tests analyze ./my-project

# Run mutation testing
boost tests mutation ./my-project

# Show improvement recommendations
boost tests recommendations ./my-project

# Analyze impact of code changes
boost tests impact ./my-project
```

---

### boost deploy run

Deploy project using Docker.

```bash
boost deploy run [PROJECT_PATH] [OPTIONS]
```

**Arguments**:
- `PROJECT_PATH`: Path to project root (default: current directory)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only | interactive |
| `--compose-file` | `-f` | Docker Compose file name | docker-compose.yml |
| `--environment` | `-e` | Target environment | development |
| `--no-cache` | | Build without Docker cache | false |

**Example**:
```bash
# Deploy with default settings
boost deploy run ./my-project

# Deploy to production
boost deploy run ./my-project -e production

# Deploy with fresh build
boost deploy run ./my-project --no-cache
```

---

### boost status

Check session status.

```bash
boost status <session-id>
```

**Arguments**:
- `session-id`: Session UUID (required)

**Example**:
```bash
boost status abc123-def456-ghi789
```

---

### boost cancel

Cancel a running session.

```bash
boost cancel <session-id>
```

**Arguments**:
- `session-id`: Session UUID (required)

**Example**:
```bash
boost cancel abc123-def456-ghi789
```

---

### boost config

Manage configuration.

```bash
boost config <subcommand>
```

**Subcommands**:
| Command | Description |
|---------|-------------|
| `show` | Display current configuration |
| `set <key> <value>` | Set configuration value |
| `validate` | Validate configuration |
| `init` | Initialize configuration file |

**Example**:
```bash
# Show current config
boost config show

# Set LLM provider
boost config set llm_provider anthropic

# Validate configuration
boost config validate
```

---

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
