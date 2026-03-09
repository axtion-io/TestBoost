# Architecture

## Overview

TestBoost is a Python toolkit that generates tests for Java projects using LLMs. It is designed to be orchestrated by an LLM CLI (Claude Code, OpenCode) through slash commands, but can also be used directly from the command line.

```
+--------------------------------------------------+
|  LLM CLI (Claude Code / OpenCode)                |
|  +--------------------------------------------+  |
|  | Slash Commands (.claude/commands/*.md)      |  |
|  +---------------------+----------------------+  |
|                         | calls                   |
|  +---------------------v----------------------+  |
|  | Shell Scripts (testboost_lite/scripts/)     |  |
|  +---------------------+----------------------+  |
|                         | calls                   |
|  +---------------------v----------------------+  |
|  | Python CLI (testboost_lite/lib/cli.py)      |  |
|  +---------------------+----------------------+  |
|                         | uses                    |
|  +---------------------v----------------------+  |
|  | TestBoost Bridge (testboost_bridge.py)      |  |
|  +---------------------+----------------------+  |
|                         | imports                 |
|  +---------------------v----------------------+  |
|  | Core Functions (src/mcp_servers/*, src/lib) |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
         |
         | writes to
         v
+--------------------------------------------------+
|  .testboost/ (in the target Java project)         |
|  +-- config.yaml                                  |
|  +-- sessions/                                    |
|      +-- 001-test-generation/                     |
|          +-- spec.md, analysis.md, ...            |
|          +-- logs/                                |
+--------------------------------------------------+
```

## Layer by Layer

### 1. Slash Commands

Markdown files in `.claude/commands/` and `.opencode/commands/` that describe what the LLM should do for each workflow step. The LLM CLI reads these and follows the instructions.

Each command file contains:
- YAML frontmatter with `description` (and `argument-hint` for OpenCode)
- Instructions for the LLM: what script to run, what output to read, what to present to the user
- The `$ARGUMENTS` placeholder for the project path

### 2. Shell Scripts

Thin wrappers in `testboost_lite/scripts/` that call the Python CLI:

```bash
#!/bin/bash
TESTBOOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../.."
cd "$TESTBOOST_ROOT"
python -m testboost_lite <command> "$@"
```

These ensure the correct working directory and Python module path.

### 3. Python CLI

The main entry point: `testboost_lite/lib/cli.py`. Uses `argparse` to dispatch to six commands: `init`, `analyze`, `gaps`, `generate`, `validate`, `status`.

Each command:
1. Reads the current session state from `.testboost/`
2. Calls core functions via the bridge
3. Writes results as markdown to the session directory
4. Prints concise output to stdout for the LLM to consume

### 4. Session Tracker

`testboost_lite/lib/session_tracker.py` manages the `.testboost/` directory structure. It replaces the database with markdown files using YAML frontmatter for metadata.

See [Session Format](./session-format.md) for details.

### 5. Markdown Logger

`testboost_lite/lib/md_logger.py` provides dual-output logging:
- **stdout**: Concise `[+]` prefixed messages for the LLM CLI
- **log files**: Detailed markdown tables in `.testboost/sessions/<id>/logs/`

### 6. TestBoost Bridge

`testboost_lite/lib/testboost_bridge.py` is the boundary between the CLI layer and the core functions. It re-exports functions from `src/` so they can be easily mocked in tests.

| Bridge Function | Source Module |
|----------------|---------------|
| `analyze_project_context()` | `src/mcp_servers/test_generator/tools/analyze.py` |
| `detect_test_conventions()` | `src/mcp_servers/test_generator/tools/conventions.py` |
| `find_source_files()` | `src/workflows/test_generation_agent.py` |
| `generate_adaptive_tests()` | `src/mcp_servers/test_generator/tools/generate_unit.py` |
| `parse_maven_errors()` | `src/lib/maven_error_parser.py` |

### 7. Core Functions (MCP Servers)

The actual analysis and generation logic lives in `src/mcp_servers/test_generator/`:

- **analyze.py** -- Parses `pom.xml`, detects frameworks, analyzes project structure
- **conventions.py** -- Detects test naming patterns, assertion styles, mocking conventions
- **generate_unit.py** -- Generates unit tests using LLMs with project-aware prompts

These modules use the LLM abstraction in `src/lib/llm.py` which supports Google Gemini, Anthropic Claude, and OpenAI through LangChain.

## Project Structure

```
TestBoost/
+-- .claude/commands/           # Claude Code slash commands
+-- .opencode/commands/         # OpenCode slash commands
+-- testboost_lite/
|   +-- lib/
|   |   +-- cli.py              # CLI entry point (6 commands)
|   |   +-- session_tracker.py  # Markdown-based session management
|   |   +-- md_logger.py        # Dual-output logger
|   |   +-- testboost_bridge.py # Bridge to core functions
|   +-- scripts/                # Shell script wrappers
+-- src/
|   +-- mcp_servers/
|   |   +-- test_generator/     # Core analysis + generation logic
|   +-- lib/
|   |   +-- llm.py              # LLM provider abstraction
|   |   +-- maven_error_parser.py
+-- config/
|   +-- prompts/                # LLM prompt templates
+-- tests/                      # Test suite
+-- docs/                       # Documentation
```

## Design Principles

1. **Markdown as state** -- All session data is human-readable markdown. No database required.
2. **LLM-native output** -- Stdout is designed for LLM consumption (concise, structured). Detailed logs go to files.
3. **Interactive by default** -- The user reviews and decides at each step. No silent auto-correction.
4. **Reuse over rewrite** -- Core analysis and generation functions from `src/mcp_servers/` are reused via the bridge, not duplicated.
5. **Easy mocking** -- The bridge pattern centralizes all imports, making the CLI fully testable without LLM calls.
