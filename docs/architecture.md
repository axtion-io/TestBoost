# Architecture

## Overview

TestBoost is a Python toolkit that generates tests for software projects using LLMs. It supports multiple technologies through a plugin system and is designed to be orchestrated by an LLM CLI (Claude Code, OpenCode) through slash commands, but can also be used directly from the command line.

```
+--------------------------------------------------+
|  LLM CLI (Claude Code / OpenCode)                |
|  +--------------------------------------------+  |
|  | Slash Commands (.claude/commands/*.md)      |  |
|  +---------------------+----------------------+  |
|                         | calls                   |
|  +---------------------v----------------------+  |
|  | Shell Scripts (scripts/)                    |  |
|  +---------------------+----------------------+  |
|                         | calls                   |
|  +---------------------v----------------------+  |
|  | Python CLI (src/lib/cli.py)                 |  |
|  +---------------------+----------------------+  |
|                         | uses                    |
|  +---------------------v----------------------+  |
|  | Bridge (src/lib/bridge.py)                  |  |
|  +---------------------+----------------------+  |
|                         | routes via              |
|  +---------------------v----------------------+  |
|  | Plugin System (src/lib/plugins/)            |  |
|  |   JavaSpringPlugin -> src/java/*            |  |
|  |   PythonPytestPlugin -> stdlib ast          |  |
|  |   GoTestingPlugin (stub)                    |  |
|  +---------------------+----------------------+  |
|                         | calls                   |
|  +---------------------v----------------------+  |
|  | Core Functions (src/test_generation/)       |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
         |
         | writes to
         v
+--------------------------------------------------+
|  .testboost/ (in the target project)              |
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

Thin wrappers in `scripts/` that call the Python CLI:

```bash
#!/bin/bash
TESTBOOST_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../.."
cd "$TESTBOOST_ROOT"
python -m src.lib.cli <command> "$@"
```

These ensure the correct working directory and Python module path.

### 3. Python CLI

The main entry point: `src/lib/cli.py`. Uses `argparse` to dispatch to ten commands: `init`, `analyze`, `gaps`, `generate`, `validate`, `mutate`, `killer`, `status`, `install`, `verify`, plus the `--list-plugins` flag.

Each command:
1. Reads the current session state from `.testboost/`
2. Resolves the technology plugin for the session
3. Calls core functions via the bridge (routed through the plugin)
4. Writes results as markdown to the session directory
5. Prints concise output to stdout for the LLM to consume

### 4. Plugin System

`src/lib/plugins/` provides the technology abstraction layer. All technology-specific behavior is encapsulated in plugins.

**`TechnologyPlugin` (ABC in `base.py`)** defines 11 abstract members:
- Properties: `identifier`, `description`, `detection_patterns`, `prompt_template_dir`
- Methods: `find_source_files()`, `classify_source_file()`, `test_file_name()`, `test_file_pattern()`, `validation_command()`, `test_run_command()`, `build_generation_context()`

**`PluginRegistry` (`registry.py`)** manages plugin lookup:
- `detect(project_path)` — returns first plugin whose detection patterns match (priority = registration order)
- `get(identifier)` — returns plugin by ID or raises `ValueError` listing available plugins
- `list_plugins()` — returns info dicts for all registered plugins

**Registered plugins** (in `__init__.py`, priority order):
1. `JavaSpringPlugin` — detects `pom.xml`, `build.gradle`, `build.gradle.kts`; delegates to `src.java.*`
2. `PythonPytestPlugin` — detects `pyproject.toml`, `setup.py`, `setup.cfg`; uses stdlib `ast`
3. `GoTestingPlugin` — detects `go.mod` (stub proving extensibility)

**Adding a new plugin**: Create `src/lib/plugins/<name>.py` implementing `TechnologyPlugin`, add one `register()` call in `__init__.py`. No other files need to change.

### 5. Session Tracker

`src/lib/session_tracker.py` manages the `.testboost/` directory structure. It replaces the database with markdown files using YAML frontmatter for metadata. The session frontmatter includes a `technology` field storing the plugin identifier (defaults to `"java-spring"` for backward compatibility).

See [Session Format](./session-format.md) for details.

### 6. Markdown Logger

`src/lib/md_logger.py` provides dual-output logging:
- **stdout**: Concise `[+]` prefixed messages for the LLM CLI
- **log files**: Detailed markdown tables in `.testboost/sessions/<id>/logs/`

### 7. Integrity Token

`src/lib/integrity.py` implements an HMAC-SHA256 token system that proves CLI output is genuine and was not fabricated by the LLM.

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

### 8. Installer and Verify

`src/lib/installer.py` provides the `install` command that deploys TestBoost slash commands and wrapper scripts into a target project. This allows users to run TestBoost from their project directory rather than from the TestBoost repo root.

**What gets installed:**

```
<project>/
├── .claude/commands/testboost.*.md    # Claude Code slash commands
├── .opencode/commands/testboost.*.md  # OpenCode slash commands
└── .testboost/
    ├── scripts/tb-*.sh                # Wrapper scripts with absolute paths
    ├── .tb_secret                     # Integrity token secret
    └── config.yaml                    # TestBoost configuration
```

### 9. TestBoost Bridge

`src/lib/bridge.py` is the boundary between the CLI layer and the core functions. It re-exports functions from `src/` so they can be easily mocked in tests. It also routes technology-specific calls through the plugin system.

| Bridge Function | Source Module |
|----------------|---------------|
| `get_plugin_for_session()` | `src/lib/plugins/` + `src/lib/session_tracker.py` |
| `find_source_files()` | Routed through session plugin |
| `classify_file()` | Routed through session plugin (fallback: `src/java/discovery.py`) |
| `analyze_project_context()` | `src/test_generation/analyze.py` |
| `detect_test_conventions()` | `src/test_generation/conventions.py` |
| `find_test_for_source()` | `src/java/discovery.py` |
| `build_class_index()` | `src/java/class_analyzer.py` |
| `extract_test_examples()` | `src/java/class_analyzer.py` |
| `generate_adaptive_tests()` | `src/test_generation/generate_unit.py` |
| `fix_compilation_errors()` | `src/test_generation/generate_unit.py` |
| `analyze_edge_cases()` | `src/test_generation/generate_unit.py` |
| `run_mutation_testing()` | `src/test_generation/mutation.py` |
| `analyze_mutants()` | `src/test_generation/analyze_mutants.py` |
| `generate_killer_tests()` | `src/test_generation/killer_tests.py` |
| `parse_maven_errors()` | `src/lib/maven_error_parser.py` |

### 10. Test Generation (`src/test_generation/`)

The LLM-based analysis and generation logic:

- **analyze.py** -- Analyzes project structure; delegates technology detection to the plugin registry
- **conventions.py** -- Detects test naming patterns, assertion styles, mocking conventions; uses `plugin.test_file_pattern()` for test file discovery
- **generate_unit.py** -- Generates unit tests using LLMs with project-aware prompts; accepts `prompt_template_dir` from the plugin for technology-specific prompts
- **mutation.py** -- Runs PIT mutation testing via Maven
- **analyze_mutants.py** -- Analyzes PIT XML reports, identifies hard-to-kill mutants
- **killer_tests.py** -- Generates targeted tests to kill surviving mutants

These modules use the LLM abstraction in `src/lib/llm.py` which supports Google Gemini, Anthropic Claude, and OpenAI through LangChain.

### 11. Java Analysis (`src/java/`)

Shared Java parsing and discovery modules with no LLM dependency:

- **parsing_utils.py** -- Low-level Java parsing: `_PRIMITIVE_TYPES`, `_is_primitive_type`, `_extract_balanced_parens`, `_parse_parameters`, `_extract_public_signatures`, `_analyze_jpa_fields`. No dependencies on other `src.*` modules.
- **discovery.py** -- Finds and classifies Java source files in Maven projects (`src/main/java`); locates existing test files
- **class_analyzer.py** -- Builds a full class index from Java source files: extracts class name, package, category, extends/implements, annotations, fields (with exact types and annotations), public methods, and dependencies. Also extracts representative test examples for LLM prompts. See [Project-Level Analysis](#project-level-analysis) below.

### 12. Shared Library (`src/lib/`)

Infrastructure modules used across the codebase:

- **plugins/** -- Technology plugin system (see section 4 above)
- **maven_error_parser.py** -- Parses Maven compilation output into structured errors with fix suggestions
- **prompt_utils.py** -- Shared `load_prompt_template()` (disk-read cached) and `render_template()` used by all LLM prompt construction; `{{placeholder}}` syntax avoids conflicts with Java `{` braces
- **llm.py** -- LLM provider abstraction (Google Gemini, Anthropic Claude, OpenAI via LangChain)
- **startup_checks.py** -- LLM connectivity check at startup with retry logic

## Project Structure

```
TestBoost/
+-- .claude/commands/           # Claude Code slash commands
+-- .opencode/commands/         # OpenCode slash commands
+-- src/
|   +-- java/
|   |   +-- parsing_utils.py    # Shared low-level Java parsers (no src.* deps)
|   |   +-- discovery.py        # Java source file finder + classifier
|   |   +-- class_analyzer.py   # Full class index builder + test example extractor
|   +-- test_generation/
|   |   +-- analyze.py          # Project structure analysis
|   |   +-- conventions.py      # Test convention detection
|   |   +-- generate_unit.py    # LLM-based unit test generation
|   |   +-- mutation.py         # PIT mutation testing runner
|   |   +-- analyze_mutants.py  # Mutation report analysis
|   |   +-- killer_tests.py     # Killer test generation
|   +-- lib/
|   |   +-- bridge.py           # Bridge to core functions (mockable boundary)
|   |   +-- cli.py              # CLI entry point (10 commands + --list-plugins)
|   |   +-- session_tracker.py  # Markdown-based session management
|   |   +-- integrity.py        # HMAC-SHA256 integrity token system
|   |   +-- installer.py        # Persistent installer for target projects
|   |   +-- plugins/            # Technology plugin system
|   |   |   +-- base.py         # TechnologyPlugin ABC
|   |   |   +-- registry.py     # PluginRegistry
|   |   |   +-- __init__.py     # Plugin registration (priority order)
|   |   |   +-- java_spring.py  # Java/Spring plugin
|   |   |   +-- python_pytest.py # Python/pytest plugin
|   |   |   +-- go_testing_stub.py # Go stub (extensibility demo)
|   |   +-- llm.py              # LLM provider abstraction
|   |   +-- maven_error_parser.py
|   |   +-- prompt_utils.py     # Shared template load + render
|   |   +-- md_logger.py        # Dual-output logger
|   |   +-- startup_checks.py   # LLM connectivity check
|   +-- workflows/
|   |   +-- test_generation_agent.py
+-- config/
|   +-- prompts/testing/        # Java/Spring LLM prompt templates
|   +-- prompts/testing/python_pytest/ # Python/pytest LLM prompt templates
+-- tests/
|   +-- unit/lib/plugins/       # Plugin unit tests
|   +-- unit/testboost/         # CLI, session, integrity, installer tests
|   +-- integration/            # Plugin detection, LLM connectivity tests
|   +-- e2e/                    # Full LLM workflow tests
+-- docs/                       # Documentation
```

## Project-Level Analysis

A key design goal is to give the LLM maximum context about the target project without re-reading files on every generation call.

### Two-level analysis files

`analyze` produces **two** output files:

| File | Location | Lifetime | Purpose |
|------|----------|----------|---------|
| `.testboost/analysis.md` | Project root | Persists across sessions | Full class index, test examples, conventions |
| `.testboost/sessions/<id>/analysis.md` | Session directory | Per session | Lightweight command overrides only |

The project-level file is built once and reused by every subsequent `generate` call (even in new sessions). The session file exists only to allow per-session customization of build flags (e.g. Maven `-P corp-profile`).

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
- **Inheritance context** -- when a tested class extends another class in the index, the parent's fields and methods are injected into the prompt as `{{inheritance_context}}`
- **Multiple test examples** -- up to 3 real test files (one service, one controller, one repository) replace the previous single 80-line truncated example

### Backward compatibility

If `.testboost/analysis.md` does not exist (project analyzed with an older version), `generate` automatically falls back to the original lazy-loading behavior. Re-running `analyze` rebuilds the project-level index.

## Design Principles

1. **Markdown as state** -- All session data is human-readable markdown. No database required.
2. **LLM-native output** -- Stdout is designed for LLM consumption (concise, structured). Detailed logs go to files.
3. **Interactive by default** -- The user reviews and decides at each step. No silent auto-correction.
4. **Reuse over rewrite** -- Core analysis and generation functions from `src/test_generation/` and `src/java/` are reused via the bridge, not duplicated.
5. **Easy mocking** -- The bridge pattern centralizes all imports, making the CLI fully testable without LLM calls.
6. **Technology-agnostic core** -- The core engine knows nothing about specific technologies; all technology-specific behavior lives in plugins.
