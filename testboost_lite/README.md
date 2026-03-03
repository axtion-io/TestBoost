# TestBoost Lite

Lightweight, markdown-driven test generation for Java projects.
Designed to be used through LLM CLI slash commands.

## Motivation

TestBoost is a powerful but complex platform (PostgreSQL, FastAPI, LangGraph, MCP).
TestBoost Lite takes the same core test generation capabilities and wraps them in a
simple, file-based workflow inspired by [spec-kit](https://github.com/github/spec-kit).

**Key simplifications:**
- No database - state tracked in markdown files
- No API server - direct CLI invocation
- No LangGraph orchestration - the LLM CLI orchestrates
- Interactive by default - user reviews and decides at each step

## Installation

### Option A: Run Claude Code from the TestBoost repo (recommended)

The slash commands are pre-installed in `.claude/commands/` and ready to use.

```bash
git clone https://github.com/axtion-io/TestBoost.git
cd TestBoost
python -m venv .venv && source .venv/bin/activate
pip install poetry && poetry install

# Set your LLM API key
export GOOGLE_API_KEY="..."  # or ANTHROPIC_API_KEY or OPENAI_API_KEY

# Launch Claude Code — slash commands are available immediately
claude
# Then use: /testboost.init /path/to/your/java/project
```

### Option B: Install slash commands into an existing project

If you prefer to work from your Java project directory, copy the command
templates so your LLM CLI can discover them:

```bash
# From your Java project root:
TESTBOOST_DIR="/path/to/TestBoost"

# For Claude Code
mkdir -p .claude/commands
cp "$TESTBOOST_DIR"/testboost_lite/templates/commands/testboost.*.md .claude/commands/

# For Open Code
mkdir -p .opencode/commands
cp "$TESTBOOST_DIR"/testboost_lite/templates/commands/testboost.*.md .opencode/commands/
```

> **Note:** The shell scripts inside the slash commands call
> `testboost_lite/scripts/tb-*.sh` using a relative path from `$TESTBOOST_DIR`.
> Make sure `TESTBOOST_DIR` is set correctly, or edit the paths in the copied
> command files.

### Option C: Use the CLI directly (no slash commands)

No installation needed beyond cloning, creating a venv, and `poetry install`:

```bash
cd /path/to/TestBoost
source .venv/bin/activate
python -m testboost_lite init /path/to/java/project
```

## Quick Start

### With Claude Code (from TestBoost repo)

```bash
cd /path/to/TestBoost
claude
# Then in the Claude Code session:
/testboost.init /path/to/your/java/project
/testboost.analyze /path/to/your/java/project
/testboost.gaps /path/to/your/java/project
/testboost.generate /path/to/your/java/project
/testboost.validate /path/to/your/java/project
```

### With the CLI directly (no Claude Code needed)

```bash
cd /path/to/TestBoost
python -m testboost_lite init /path/to/java/project
python -m testboost_lite analyze /path/to/java/project
python -m testboost_lite gaps /path/to/java/project
python -m testboost_lite generate /path/to/java/project
python -m testboost_lite validate /path/to/java/project
```

## Architecture

```
┌──────────────────────────────────────────────┐
│  LLM CLI (Claude Code / Open Code / ...)     │
│  ┌────────────────────────────────────────┐  │
│  │ Slash Commands (.claude/commands/*.md) │  │
│  └───────────────┬────────────────────────┘  │
│                  │ calls                     │
│  ┌───────────────▼────────────────────────┐  │
│  │ Shell Scripts (testboost_lite/scripts) │  │
│  └───────────────┬────────────────────────┘  │
│                  │ calls                     │
│  ┌───────────────▼────────────────────────┐  │
│  │ Python CLI (testboost_lite/lib/cli.py) │  │
│  └───────────────┬────────────────────────┘  │
│                  │ reuses                    │
│  ┌───────────────▼────────────────────────┐  │
│  │ TestBoost Core Functions               │  │
│  │ - analyze_project_context()            │  │
│  │ - detect_test_conventions()            │  │
│  │ - _find_source_files()                 │  │
│  │ - generate_adaptive_tests()            │  │
│  │ - MavenErrorParser                     │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘

         │ writes to
         ▼
┌──────────────────────────────────────────────┐
│  .testboost/ (in target Java project)        │
│  ├── config.yaml                             │
│  └── sessions/                               │
│      └── 001-test-generation/                │
│          ├── spec.md         (intent)        │
│          ├── analysis.md     (project info)  │
│          ├── coverage-gaps.md (what to test) │
│          ├── generation.md   (test results)  │
│          ├── validation.md   (pass/fail)     │
│          └── logs/           (detailed logs) │
└──────────────────────────────────────────────┘
```

## Workflow Steps

| Step | Command | What it does | Reuses from TestBoost |
|------|---------|-------------|----------------------|
| 1. Init | `init` | Creates `.testboost/` and session directory | - |
| 2. Analyze | `analyze` | Scans project structure, frameworks, conventions | `analyze_project_context()`, `detect_test_conventions()`, `_find_source_files()` |
| 3. Gaps | `gaps` | Identifies files without tests | File matching logic |
| 4. Generate | `generate` | Generates tests using LLM | `generate_adaptive_tests()` |
| 5. Validate | `validate` | Compiles and runs tests | `MavenErrorParser` |
| 6. Status | `status` | Shows progress | Session tracker |

## Session Tracking

Each step writes a markdown file with YAML frontmatter:

```markdown
---
status: completed
step: analysis
updated_at: 2026-03-03T10:05:23Z
completed_at: 2026-03-03T10:05:23Z
---

# Project Analysis

**Project type**: spring-boot
...
```

The `spec.md` file maintains a progress table:

```markdown
| Step | Status | Started | Completed |
|------|--------|---------|-----------|
| analysis | completed | 2026-03-03T10:00:00Z | 2026-03-03T10:05:23Z |
| coverage-gaps | completed | ... | ... |
| generation | in_progress | ... | - |
| validation | pending | - | - |
```

## Logging

Dual-output logging:
- **stdout**: Concise messages for the LLM CLI to consume
- **logs/*.md**: Detailed log entries in markdown table format

```markdown
# Logs - 2026-03-03

| Time | Level | Step | Message | Details |
|------|-------|------|---------|---------|
| 10:00:01 | INFO  | analysis | Starting project analysis... | |
| 10:00:03 | INFO  | analysis | Analysis complete: 12 source files, 45 classes | |
```

## Comparison with TestBoost

| Feature | TestBoost | TestBoost Lite |
|---------|-----------|---------------|
| State management | PostgreSQL + SQLAlchemy | Markdown files |
| API | FastAPI REST API | Direct CLI |
| Orchestration | LangGraph ReAct agents | LLM CLI (Claude Code) |
| User interaction | API-mediated | Direct conversation |
| Logging | structlog + DB events | Markdown tables |
| Correction loop | Automatic (silent) | Interactive (LLM + user) |
| Setup complexity | Docker + PostgreSQL + migrations | `python -m testboost_lite init` |
| Dependencies | ~30 Python packages | Reuses TestBoost's deps |

## Adapting for Other LLM CLIs

The command templates in `testboost_lite/templates/commands/` can be adapted for:
- **Claude Code**: Already in `.claude/commands/` of this repo — no action needed
- **Open Code**: Copy templates to `.opencode/commands/` in your project
- **Cursor**: Add as custom commands
- **Generic**: Use the shell scripts in `testboost_lite/scripts/` directly

## Configuration

Edit `.testboost/config.yaml` in the target project:

```yaml
coverage_target: 80
max_complexity: 20
mock_framework: mockito
assertion_library: assertj
max_correction_retries: 3
test_timeout_seconds: 300
```
