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

## Quick Start

### With Claude Code

```bash
# In a Java project directory:
/testboost.init .
/testboost.analyze .
/testboost.gaps .
/testboost.generate .
/testboost.validate .
```

### With the CLI directly

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
- **Claude Code**: Copy to `.claude/commands/` (done by default)
- **Open Code**: Copy to `.opencode/commands/`
- **Cursor**: Add as custom commands
- **Generic**: Use the shell scripts directly

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
