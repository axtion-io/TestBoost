# Session Format

TestBoost tracks all state in markdown files inside a `.testboost/` directory created in your Java project. No database is needed.

## Directory Structure

```
your-java-project/
+-- .testboost/
|   +-- config.yaml                       # Project-level settings
|   +-- analysis.md                       # Project-level class index (shared across sessions)
|   +-- .gitignore                        # Ignores large log files
|   +-- .tb_secret                        # Integrity token secret (git-ignored)
|   +-- scripts/                          # Wrapper scripts (created by install)
|   |   +-- tb-init.sh
|   |   +-- tb-analyze.sh
|   |   +-- tb-gaps.sh
|   |   +-- tb-generate.sh
|   |   +-- tb-validate.sh
|   |   +-- tb-status.sh
|   |   +-- tb-verify.sh
|   +-- sessions/
|       +-- 001-test-generation/          # First session
|       |   +-- spec.md                   # Session intent and progress
|       |   +-- analysis.md               # Maven command overrides (lightweight)
|       |   +-- coverage-gaps.md          # Gap analysis
|       |   +-- generation.md             # Test generation results
|       |   +-- validation.md             # Compilation + test results
|       |   +-- logs/
|       |       +-- 2026-03-09.md         # Daily execution log
|       +-- 002-test-generation/          # Second session (if any)
|           +-- ...
```

## Project-Level Analysis File

`.testboost/analysis.md` is created by `analyze` and **shared across all sessions**. It contains:

- A full class index for every Java source file (class name, package, category, extends/implements, annotations, fields with exact types, public methods)
- Up to 3 representative test examples extracted from the project (one service, one controller, one repository)
- Detected test conventions
- Maven compile and test commands

This file persists between runs of `analyze`. The `generate` command reads it to give the LLM precise context about the whole project — not just the class being tested.

The **session-level** `analysis.md` (under `sessions/<id>/`) is intentionally lightweight: it only stores Maven command overrides (`maven_compile_cmd`, `maven_test_cmd`). Edit those values to add profiles (`-P`) or properties (`-D`) that are specific to this session, without affecting other sessions.

See [Architecture](./architecture.md#project-level-analysis) for the full design rationale.

## Integrity Token Secret

The `.tb_secret` file contains a random 32-byte hex-encoded secret generated during `init` or `install`. It is used by the integrity token system to produce HMAC-SHA256 signatures that prove CLI output is authentic. This file is always git-ignored.

See [Architecture](./architecture.md) for details on how the integrity token system works.

## Session Numbering

Sessions are numbered sequentially: `001-test-generation`, `002-test-generation`, etc. The `status` command always operates on the latest session.

## Step Files

Each workflow step writes a markdown file with YAML frontmatter:

```markdown
---
status: completed
step: analysis
started_at: 2026-03-09T10:00:00Z
updated_at: 2026-03-09T10:05:23Z
completed_at: 2026-03-09T10:05:23Z
---

# Project Analysis

**Project type**: spring-boot
**Build system**: maven
...
```

### Frontmatter Fields

| Field | Values | Description |
|-------|--------|-------------|
| `status` | `pending`, `in_progress`, `completed`, `failed` | Current step status |
| `step` | `analysis`, `coverage-gaps`, `generation`, `validation` | Step name |
| `started_at` | ISO 8601 timestamp | When the step started |
| `updated_at` | ISO 8601 timestamp | Last update |
| `completed_at` | ISO 8601 timestamp | When the step finished |

### JSON Data Blocks

Step files may contain a fenced JSON block at the end with structured data for the next step to consume:

````markdown
```json
{
  "source_files": ["src/main/java/com/example/UserService.java", ...],
  "conventions": { "naming": { "dominant_pattern": "shouldVerb" }, ... }
}
```
````

This is how data flows between steps: `analyze` writes source files and conventions, `gaps` reads them to identify missing tests, `generate` reads conventions to inform the LLM prompt.

## spec.md

The `spec.md` file tracks overall session progress:

```markdown
---
session_id: "001"
session_name: test-generation
created_at: 2026-03-09T10:00:00Z
---

# Session 001 - Test Generation

## Progress

| Step | Status | Started | Completed |
|------|--------|---------|-----------|
| analysis | completed | 2026-03-09T10:00:00Z | 2026-03-09T10:05:23Z |
| coverage-gaps | completed | 2026-03-09T10:06:00Z | 2026-03-09T10:06:15Z |
| generation | in_progress | 2026-03-09T10:07:00Z | - |
| validation | pending | - | - |
```

## Log Files

Each step writes detailed logs to `logs/<date>.md` as a markdown table:

```markdown
# Logs - 2026-03-09

| Time | Level | Step | Message | Details |
|------|-------|------|---------|---------|
| 10:00:01 | INFO | analysis | Starting project analysis... | |
| 10:00:03 | INFO | analysis | Analysis complete: 12 source files | |
| 10:05:00 | ERROR | generation | Failed to generate tests for Foo.java | LLM timeout |
```

Logs are appended throughout the session. The `--verbose` flag on CLI commands adds more detail to the log output.

## config.yaml

Project-level configuration created during `init`:

```yaml
coverage_target: 80
max_complexity: 20
mock_framework: mockito
assertion_library: assertj
max_correction_retries: 3
test_timeout_seconds: 300
```

See [Configuration](./configuration.md) for all available settings.
