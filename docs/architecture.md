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
|  +-- analysis.md        <- project-level index    |
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

The main entry point: `testboost_lite/lib/cli.py`. Uses `argparse` to dispatch to eight commands: `init`, `analyze`, `gaps`, `generate`, `validate`, `status`, `install`, `verify`.

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

### 6. Integrity Token

`testboost_lite/lib/integrity.py` implements an HMAC-SHA256 token system that proves CLI output is genuine and was not fabricated by the LLM.

**Why it exists:** When the LLM CLI runs a slash command, it calls a shell script and reads stdout. Without verification, the LLM could hallucinate a successful output instead of actually running the command. The integrity token prevents this.

**How it works:**

1. During `init`, a random 32-byte secret is generated and stored in `.testboost/.tb_secret` (git-ignored).
2. At the end of every successful CLI step, the CLI computes `HMAC-SHA256(secret, "step:session_id:timestamp")` and prints it to stdout:
   ```
   [TESTBOOST_INTEGRITY:sha256=<hex_digest>:<step>:<session_id>:<timestamp>]
   ```
3. The slash-command markdown files instruct the LLM to verify the token's presence before proceeding to the next step.
4. The LLM cannot forge the token because it does not have access to the `.tb_secret` file.

**Verification:** `verify_token()` re-computes the HMAC from the payload and compares it to the claimed digest using `hmac.compare_digest` (constant-time comparison).

### 7. Installer and Verify

`testboost_lite/lib/installer.py` provides the `install` command that deploys TestBoost slash commands and wrapper scripts into a target Java project. This allows users to run TestBoost from their Java project directory rather than from the TestBoost repo root.

**What gets installed:**

```
<java-project>/
├── .claude/commands/testboost.*.md    # Claude Code slash commands
├── .opencode/commands/testboost.*.md  # OpenCode slash commands
└── .testboost/
    ├── scripts/tb-*.sh                # Wrapper scripts with absolute paths
    ├── .tb_secret                     # Integrity token secret
    └── config.yaml                    # TestBoost configuration
```

**How it works:**

1. Reads command templates from `testboost_lite/templates/commands/`.
2. Rewrites script paths from relative (`testboost_lite/scripts/tb-*.sh`) to installed (`<project>/.testboost/scripts/tb-*.sh`).
3. Generates wrapper shell scripts that activate the TestBoost virtualenv and call the CLI with absolute paths.
4. Creates the integrity secret via `get_or_create_secret()`.

**Usage:** `python -m testboost_lite install /path/to/java/project`

The `verify` command (`testboost_lite/lib/integrity.py`) re-computes the HMAC of a token printed to stdout and exits 0 if authentic. See the Integrity Token section above for details.

### 8. TestBoost Bridge

`testboost_lite/lib/testboost_bridge.py` is the boundary between the CLI layer and the core functions. It re-exports functions from `src/` so they can be easily mocked in tests.

| Bridge Function | Source Module |
|----------------|---------------|
| `analyze_project_context()` | `src/mcp_servers/test_generator/tools/analyze.py` |
| `detect_test_conventions()` | `src/mcp_servers/test_generator/tools/conventions.py` |
| `find_source_files()` | `src/lib/java_discovery.py` |
| `classify_file()` | `src/lib/java_discovery.py` |
| `find_test_for_source()` | `src/lib/java_discovery.py` |
| `build_class_index()` | `src/lib/java_class_analyzer.py` |
| `extract_test_examples()` | `src/lib/java_class_analyzer.py` |
| `generate_adaptive_tests()` | `src/mcp_servers/test_generator/tools/generate_unit.py` |
| `fix_compilation_errors()` | `src/mcp_servers/test_generator/tools/generate_unit.py` |
| `parse_maven_errors()` | `src/lib/maven_error_parser.py` |

### 9. Core Functions (MCP Servers)

The actual analysis and generation logic lives in `src/mcp_servers/test_generator/`:

- **analyze.py** -- Parses `pom.xml`, detects frameworks, analyzes project structure
- **conventions.py** -- Detects test naming patterns, assertion styles, mocking conventions
- **generate_unit.py** -- Generates unit tests using LLMs with project-aware prompts; also handles LLM-based compilation error fixing

These modules use the LLM abstraction in `src/lib/llm.py` which supports Google Gemini, Anthropic Claude, and OpenAI through LangChain.

### 10. Shared Library (`src/lib/`)

Supporting modules used across the core:

- **java_discovery.py** -- Finds and classifies Java source files in Maven projects (`src/main/java`); locates existing test files
- **java_class_analyzer.py** -- Builds a full class index from Java source files: extracts class name, package, category, extends/implements, annotations, fields (with exact types and annotations), public methods, and dependencies. Also extracts representative test examples for LLM prompts. See [Project-Level Analysis](#project-level-analysis) below.
- **maven_error_parser.py** -- Parses Maven compilation output into structured errors with fix suggestions
- **prompt_utils.py** -- Shared `load_prompt_template()` (disk-read cached) and `render_template()` used by all LLM prompt construction; `{{placeholder}}` syntax avoids conflicts with Java `{` braces
- **llm.py** -- LLM provider abstraction (Google Gemini, Anthropic Claude, OpenAI via LangChain)
- **startup_checks.py** -- LLM connectivity check at startup with retry logic

## Project Structure

```
TestBoost/
+-- .claude/commands/           # Claude Code slash commands
+-- .opencode/commands/         # OpenCode slash commands
+-- testboost_lite/
|   +-- lib/
|   |   +-- cli.py              # CLI entry point (7 commands incl. install)
|   |   +-- session_tracker.py  # Markdown-based session management
|   |   +-- md_logger.py        # Dual-output logger
|   |   +-- testboost_bridge.py # Bridge to core functions
|   |   +-- integrity.py        # HMAC-SHA256 integrity token system
|   |   +-- installer.py        # Persistent installer for target projects
|   +-- scripts/                # Shell script wrappers
|   +-- templates/commands/     # Slash command templates for installation
+-- src/
|   +-- mcp_servers/
|   |   +-- test_generator/     # Core analysis + generation logic
|   +-- lib/
|   |   +-- llm.py              # LLM provider abstraction
|   |   +-- java_discovery.py   # Java source file finder + classifier
|   |   +-- java_class_analyzer.py  # Full class index builder + test example extractor
|   |   +-- maven_error_parser.py
|   |   +-- prompt_utils.py     # Shared template load+render
|   +-- workflows/
|   |   +-- test_generation_agent.py  # Java test validation utilities
+-- config/
|   +-- prompts/                # LLM prompt templates
+-- tests/                      # Test suite
+-- docs/                       # Documentation
```

## Project-Level Analysis

A key design goal is to give the LLM maximum context about the target Java project without re-reading files on every generation call.

### Two-level analysis files

`analyze` produces **two** output files:

| File | Location | Lifetime | Purpose |
|------|----------|----------|---------|
| `.testboost/analysis.md` | Project root | Persists across sessions | Full class index, test examples, conventions |
| `.testboost/sessions/<id>/analysis.md` | Session directory | Per session | Lightweight Maven command overrides only |

The project-level file is built once and reused by every subsequent `generate` call (even in new sessions). The session file exists only to allow per-session customization of Maven flags (e.g. `-P corp-profile`).

### Class Index

`build_class_index()` reads every Java source file and extracts a `ClassIndexEntry` for each class:

```json
{
  "BankingServiceImpl": {
    "class_name": "BankingServiceImpl",
    "package": "com.example.service",
    "category": "service",
    "extends": "AbstractService",
    "implements": ["BankingService"],
    "annotations": ["Service", "Transactional"],
    "fields": [
      {"name": "accountRepo", "type": "AccountRepository", "annotations": ["Autowired"]}
    ],
    "methods": [
      {"name": "transfer", "return_type": "void",
       "parameters": "Long from, Long to, BigDecimal amount",
       "visibility": "public"}
    ],
    "is_jpa_entity": false,
    "jpa_info": {"id_field": null, "id_type": null, "has_generated_value": false}
  }
}
```

### Why it matters for test generation

Before this, the LLM received only the source file being tested plus lazily-loaded signatures of its direct dependencies. This led to:
- Invented method names and incorrect signatures
- Wrong field types (e.g. `BigDecimal` confused with `Double`)
- Missing parent class context when testing classes that extend another class

With the class index:
- **Exact types** for all dependency fields (e.g. `BigDecimal amount`, not `double amount`)
- **Inheritance context** — when a tested class extends another class in the index, the parent's fields and methods are injected into the prompt as `{{inheritance_context}}`
- **Multiple test examples** — up to 3 real test files (one service, one controller, one repository) replace the previous single 80-line truncated example

### Backward compatibility

If `.testboost/analysis.md` does not exist (project analyzed with an older version), `generate` automatically falls back to the original lazy-loading behavior. Re-running `analyze` rebuilds the project-level index.

## Design Principles

1. **Markdown as state** -- All session data is human-readable markdown. No database required.
2. **LLM-native output** -- Stdout is designed for LLM consumption (concise, structured). Detailed logs go to files.
3. **Interactive by default** -- The user reviews and decides at each step. No silent auto-correction.
4. **Reuse over rewrite** -- Core analysis and generation functions from `src/mcp_servers/` are reused via the bridge, not duplicated.
5. **Easy mocking** -- The bridge pattern centralizes all imports, making the CLI fully testable without LLM calls.
