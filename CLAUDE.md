# TestBoost -- LLM CLI Instructions

## Overview

TestBoost is an AI-powered test generation toolkit for Java projects.
It is driven by slash commands from LLM CLIs (Claude Code, OpenCode, etc.).

## Prerequisites

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

```bash
python -m testboost_lite init /path/to/java/project
python -m testboost_lite analyze /path/to/java/project
python -m testboost_lite gaps /path/to/java/project
python -m testboost_lite generate /path/to/java/project
python -m testboost_lite validate /path/to/java/project
python -m testboost_lite status /path/to/java/project
```

## Environment

Set one of these API keys depending on your LLM provider:
- `GOOGLE_API_KEY` for Google Gemini
- `ANTHROPIC_API_KEY` for Anthropic Claude
- `OPENAI_API_KEY` for OpenAI

Set `MODEL` to choose a specific model (e.g. `gemini-2.0-flash`, `anthropic/claude-sonnet-4-20250514`).
