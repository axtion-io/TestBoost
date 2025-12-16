# CLI Reference

**Purpose**: Complete reference for TestBoost CLI commands and exit codes
**Version**: 1.0.0

---

## Installation

```bash
# Install via pip
pip install testboost

# Or via poetry
poetry install
```

---

## Commands

### boost maintenance

Run Maven project maintenance workflow.

```bash
boost maintenance <project-path> [OPTIONS]
```

**Arguments**:
- `project-path`: Path to Maven project root (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--mode` | `-m` | Execution mode: interactive, autonomous, analysis_only | interactive |
| `--timeout` | `-t` | Timeout in seconds | 300 |
| `--skip-tests` | | Skip baseline test validation | false |
| `--dry-run` | | Show what would be done without applying | false |

**Example**:
```bash
# Interactive mode
boost maintenance ./my-project

# Autonomous mode with custom timeout
boost maintenance ./my-project -m autonomous -t 600

# Analysis only (no changes)
boost maintenance ./my-project -m analysis_only
```

---

### boost generate

Generate tests for Java classes.

```bash
boost generate <project-path> [OPTIONS]
```

**Arguments**:
- `project-path`: Path to Maven project root (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--class` | `-c` | Specific class to generate tests for | all |
| `--type` | `-t` | Test type: unit, integration, snapshot, all | all |
| `--coverage` | | Target coverage percentage | 80 |
| `--mutation` | | Run mutation testing after generation | false |

**Example**:
```bash
# Generate all tests
boost generate ./my-project

# Generate unit tests for specific class
boost generate ./my-project -c com.example.MyService -t unit

# Generate with mutation testing
boost generate ./my-project --mutation
```

---

### boost deploy

Deploy project using Docker.

```bash
boost deploy <project-path> [OPTIONS]
```

**Arguments**:
- `project-path`: Path to project root (required)

**Options**:
| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--compose-file` | `-f` | Docker Compose file name | docker-compose.yml |
| `--environment` | `-e` | Target environment | development |
| `--no-cache` | | Build without Docker cache | false |
| `--detach` | `-d` | Run containers in background | true |

**Example**:
```bash
# Deploy with default settings
boost deploy ./my-project

# Deploy to production
boost deploy ./my-project -e production

# Deploy with fresh build
boost deploy ./my-project --no-cache
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

### boost audit

Audit project security.

```bash
boost audit <project-path> [OPTIONS]
```

**Arguments**:
- `project-path`: Path to project root (required)

**Options**:
| Option | Description | Default |
|--------|-------------|---------|
| `--dependencies` | Check dependency vulnerabilities | true |
| `--api-keys` | Check for exposed API keys | true |
| `--output` | Output format: text, json, sarif | text |

**Example**:
```bash
# Full audit
boost audit ./my-project

# JSON output for CI
boost audit ./my-project --output json
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
