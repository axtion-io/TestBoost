# Getting Started

## Prerequisites

- **Python 3.11+**
- **Git**
- **Build tool** for your project: Maven/Gradle (Java), pytest (Python), or go test (Go)
- **LLM API key** -- at least one of: Google Gemini, Anthropic Claude, or OpenAI

You do **not** need Docker, PostgreSQL, or any database.

## Installation

```bash
git clone https://github.com/axtion-io/TestBoost.git
cd TestBoost
python -m venv .venv && source .venv/bin/activate
pip install poetry && poetry install
```

## Configure Your LLM Provider

Set the API key for the provider you want to use:

```bash
# Google Gemini (recommended -- free tier available)
export GOOGLE_API_KEY="AIza..."

# Anthropic Claude
export ANTHROPIC_API_KEY="sk-ant-..."

# OpenAI
export OPENAI_API_KEY="sk-..."
```

Set `LLM_PROVIDER` and `MODEL` for your provider (default: `anthropic` / `claude-sonnet-4-6`):

```bash
# Google Gemini
export LLM_PROVIDER="google-genai" && export MODEL="gemini-2.0-flash"
# Anthropic Claude (default)
export LLM_PROVIDER="anthropic"    && export MODEL="claude-sonnet-4-6"
# OpenAI
export LLM_PROVIDER="openai"       && export MODEL="gpt-4o"
```

See [LLM Providers](./llm-providers.md) for a full comparison.

## Usage with Claude Code

Launch Claude Code from the TestBoost repo root:

```bash
cd TestBoost
claude
```

The slash commands are available immediately:

```
/testboost.init /path/to/your/project
/testboost.analyze /path/to/your/project
/testboost.gaps /path/to/your/project
/testboost.generate /path/to/your/project
/testboost.validate /path/to/your/project
/testboost.status /path/to/your/project
```

TestBoost auto-detects the project technology (Java/Spring, Python/pytest, etc.). Use `--tech <identifier>` to override:

```
/testboost.init /path/to/your/project --tech python-pytest
```

The LLM assistant will guide you through each step, presenting results and asking for your input before proceeding.

## Usage with OpenCode

Same workflow, just launch OpenCode instead:

```bash
cd TestBoost
opencode
```

The slash commands in `.opencode/commands/` work identically.

## Usage Without an LLM CLI

You can run the CLI directly:

```bash
cd TestBoost
source .venv/bin/activate

python -m src.lib.cli init /path/to/project
python -m src.lib.cli analyze /path/to/project
python -m src.lib.cli gaps /path/to/project
python -m src.lib.cli generate /path/to/project
python -m src.lib.cli validate /path/to/project
python -m src.lib.cli status /path/to/project

# Override auto-detection:
python -m src.lib.cli init /path/to/project --tech python-pytest

# List available plugins:
python -m src.lib.cli --list-plugins
```

## Installing TestBoost in Your Project

If you prefer to work from your project directory instead of the TestBoost repo, use the `install` command:

```bash
cd TestBoost
source .venv/bin/activate
python -m src.lib.cli install /path/to/your/project
```

This installs:
- Slash commands in `.claude/commands/` and `.opencode/commands/`
- Wrapper scripts in `.testboost/scripts/` with absolute paths to the TestBoost installation
- An integrity token secret in `.testboost/.tb_secret`

After installation, you can launch your LLM CLI directly from your project:

```bash
cd /path/to/your/project
claude   # or opencode
# /testboost.analyze .
```

The wrapper scripts handle virtualenv activation and path resolution automatically.

> **Note:** If you move the TestBoost installation directory, re-run the `install` command to update the paths.

## What Happens in Your Project

After running `init` (or `install`), TestBoost creates a `.testboost/` directory in your project:

```
your-project/
+-- .testboost/
|   +-- config.yaml
|   +-- .tb_secret              # Integrity token secret (git-ignored)
|   +-- analysis.md             # Project-level analysis (shared across sessions)
|   +-- scripts/                # Wrapper scripts (only after install)
|   |   +-- tb-init.sh
|   |   +-- tb-analyze.sh
|   |   +-- ...
|   +-- sessions/
|       +-- 001-test-generation/
|           +-- spec.md         # Includes technology: java-spring (or python-pytest, etc.)
|           +-- analysis.md
|           +-- coverage-gaps.md
|           +-- generation.md
|           +-- validation.md
|           +-- logs/
+-- src/
+-- pom.xml (or pyproject.toml, go.mod, etc.)
```

Generated test files are written directly to the appropriate test directory in your project (e.g. `src/test/java/...` for Java, `tests/...` for Python). Review them before committing.

## Next Steps

- [Workflow](./workflow.md) -- Understand what each step does in detail
- [Configuration](./configuration.md) -- Customize coverage targets and test options
- [LLM Providers](./llm-providers.md) -- Choose and configure your LLM provider
