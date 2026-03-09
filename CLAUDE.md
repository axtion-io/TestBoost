# TestBoost -- LLM CLI Instructions

## Overview

TestBoost is an AI-powered test generation toolkit for Java projects.
It uses a local LLM served via **vLLM** (OpenAI-compatible API) and is driven
by slash commands from LLM CLIs (Claude Code, OpenCode, etc.).

## Prerequisites

- **Python 3.11+** and **Poetry** installed
- Activate the virtual environment before using the CLI:
  ```bash
  cd TestBoost
  poetry install          # first time only
  poetry shell            # activate the venv
  ```
- Launch the LLM CLI **from the TestBoost repo root** (`cd TestBoost && claude`)
- The slash commands in `.claude/commands/` (or `.opencode/commands/`) call shell scripts via relative paths
- `<path>` in every command refers to an **absolute or relative path to the Java project** you want to test

## Available Commands

| Command | Purpose |
|---------|---------|
| `/testboost.init <path>` | Initialize a session for a Java project |
| `/testboost.analyze <path>` | Analyze project structure and conventions |
| `/testboost.gaps <path>` | Identify files lacking test coverage |
| `/testboost.generate <path>` | Generate tests using LLM |
| `/testboost.validate <path>` | Compile and run generated tests |
| `/testboost.status <path>` | Show session progress and recent logs |

## Workflow

The commands follow a sequential workflow:

```
init -> analyze -> gaps -> generate -> validate
```

Each step writes results to `.testboost/sessions/<id>/<step>.md` in the target project.

## Architecture

```
LLM CLI (Claude Code / OpenCode)
  +-- slash command (.claude/commands/testboost.*.md)
      +-- shell script (testboost_lite/scripts/tb-*.sh)
          +-- Python CLI (testboost_lite/lib/cli.py)
              +-- MCP server functions (src/mcp_servers/test_generator/*)
```

## Session Tracking

Sessions are tracked via markdown files (no database):

```
<project>/.testboost/
+-- config.yaml
+-- sessions/
    +-- 001-test-generation/
        +-- spec.md              # Session intent and progress table
        +-- analysis.md          # Project analysis results
        +-- coverage-gaps.md     # Gap analysis
        +-- generation.md        # Test generation results
        +-- validation.md        # Compilation + test results
        +-- logs/
            +-- 2026-03-09.md    # Detailed execution logs
```

## Key Design Decisions

- **No database**: All state is in markdown files with YAML frontmatter
- **No API server**: Direct CLI invocation
- **Dual logging**: Concise stdout for the LLM + detailed .md logs for the user
- **Interactive correction**: When tests fail, the LLM sees the errors and works with the user to fix them
- **MCP servers**: Core analysis and generation logic lives in internal MCP server modules (`src/mcp_servers/`)

## Running the CLI Directly

Make sure the Poetry venv is active, then:

```bash
python -m testboost_lite init /path/to/java/project
python -m testboost_lite analyze /path/to/java/project
python -m testboost_lite gaps /path/to/java/project
python -m testboost_lite generate /path/to/java/project
python -m testboost_lite validate /path/to/java/project
python -m testboost_lite status /path/to/java/project
```

## Environment

Copy `.env.example` to `.env` and adjust values. Key variables:

### LLM Provider

TestBoost supports three provider modes via `LLM_PROVIDER`:

| Provider | Use case |
|----------|----------|
| `openai` | Local vLLM or any OpenAI-compatible endpoint |
| `anthropic` | Anthropic Claude API |
| `google-genai` | Google Gemini API |

**Using a local vLLM instance (recommended for air-gapped / corporate setups):**

```env
LLM_PROVIDER=openai
MODEL=/path/to/your/local/model/
OPENAI_API_BASE=https://your-internal-llm-endpoint/v1
OPENAI_API_KEY=dummy
```

vLLM serves a local model behind an OpenAI-compatible API. Point `OPENAI_API_BASE`
to the vLLM endpoint and set `MODEL` to the model path or name loaded by vLLM.

**Using a cloud provider:**

```env
# Google Gemini
GOOGLE_API_KEY=your-key
MODEL=gemini-2.5-flash-preview-09-2025

# Anthropic Claude
ANTHROPIC_API_KEY=your-key
MODEL=anthropic/claude-sonnet-4-20250514

# OpenAI
OPENAI_API_KEY=your-key
MODEL=gpt-4o
```

### Corporate Network / Proxy / SSL

When running behind a corporate proxy or firewall, configure these variables
so that Python (httpx/requests) can reach the LLM endpoint:

```env
# Bypass proxy for internal endpoints (comma-separated)
NO_PROXY=*.example.corp,10.0.0.*,127.0.0.1,localhost

# Corporate CA certificate bundle (PEM format)
# Needed when the internal endpoint uses a certificate signed by an internal CA
SSL_CERT_FILE=/path/to/corp-ca-bundle.pem
REQUESTS_CA_BUNDLE=/path/to/corp-ca-bundle.pem
```

**Creating the CA bundle:** concatenate your corporate CA certificate(s) with
the default certifi bundle:

```bash
python -c "import certifi; print(certifi.where())"   # find the default bundle
cat "$(python -c 'import certifi;print(certifi.where())')" corp-ca.pem > corp-ca-bundle.pem
```

> **Note:** Certificate files (`*.pem`, `*.crt`, `*.der`) are git-ignored and must
> be provisioned locally on each machine.
