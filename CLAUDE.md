# TestBoost Lite - LLM CLI Instructions

## Overview

TestBoost Lite is a lightweight, markdown-driven test generation toolkit for Java projects.
It is designed to be used through LLM CLI slash commands (Claude Code, Open Code, etc.).

## Available Commands

Use these slash commands to drive the test generation workflow:

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
init → analyze → gaps → generate → validate
```

Each step writes results to `.testboost/sessions/<id>/<step>.md` in the target project.

## Architecture

```
LLM CLI (Claude Code)
  └─ slash command (.claude/commands/testboost.*.md)
      └─ shell script (testboost_lite/scripts/tb-*.sh)
          └─ Python CLI (testboost_lite/lib/cli.py)
              └─ Reused TestBoost functions (src/mcp_servers/*, src/workflows/*, src/lib/*)
```

## Session Tracking

Sessions are tracked via markdown files (no database required):

```
<project>/.testboost/
├── config.yaml
└── sessions/
    └── 001-test-generation/
        ├── spec.md              # Session intent and progress table
        ├── analysis.md          # Project analysis results
        ├── coverage-gaps.md     # Gap analysis
        ├── generation.md        # Test generation results
        ├── validation.md        # Compilation + test results
        └── logs/
            └── 2026-03-03.md    # Detailed execution logs
```

## Key Design Decisions

- **No database**: All state is in markdown files with YAML frontmatter
- **No API server**: Direct CLI invocation, no FastAPI/PostgreSQL needed
- **Dual logging**: Concise stdout for the LLM + detailed .md logs for the user
- **Interactive correction**: When tests fail, the LLM sees the errors and works with the user to fix them (instead of silent auto-correction)
- **Reuses TestBoost core**: analyze_project_context, generate_adaptive_tests, MavenErrorParser are called directly

## Running the CLI Directly

```bash
# From the TestBoost root directory:
python -m testboost_lite init /path/to/java/project
python -m testboost_lite analyze /path/to/java/project
python -m testboost_lite gaps /path/to/java/project
python -m testboost_lite generate /path/to/java/project
python -m testboost_lite validate /path/to/java/project
python -m testboost_lite status /path/to/java/project
```

## Environment

Requires the same LLM API keys as TestBoost:
- `GOOGLE_API_KEY` for Google Gemini
- `ANTHROPIC_API_KEY` for Anthropic Claude
- `OPENAI_API_KEY` for OpenAI

Set `LLM_PROVIDER` and `MODEL` environment variables to configure.
