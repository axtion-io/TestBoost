# Getting Started

## Prerequisites

- **Python 3.11+**
- **Git**
- **Maven** (on the Java project you want to test)
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
export LLM_PROVIDER="google-genai" && export MODEL="gemini-2.5-flash"
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
/testboost.init /path/to/your/java/project
/testboost.analyze /path/to/your/java/project
/testboost.gaps /path/to/your/java/project
/testboost.generate /path/to/your/java/project
/testboost.validate /path/to/your/java/project
/testboost.status /path/to/your/java/project
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

python -m testboost init /path/to/java/project
python -m testboost analyze /path/to/java/project
python -m testboost gaps /path/to/java/project
python -m testboost generate /path/to/java/project
python -m testboost validate /path/to/java/project
python -m testboost status /path/to/java/project
```

## Installing TestBoost in Your Java Project

If you prefer to work from your Java project directory instead of the TestBoost repo, use the `install` command:

```bash
cd TestBoost
source .venv/bin/activate

# Linux / macOS (bash wrappers -- default)
python -m testboost install /path/to/your/java/project

# Windows (PowerShell wrappers)
python -m testboost install /path/to/your/java/project --shell-type powershell
```

If you omit `--shell-type`, the command prompts you to choose.

This installs:
- Slash commands in `.claude/commands/` and `.opencode/commands/`
- Wrapper scripts in `.testboost/scripts/` (either `tb-*.sh` or `tb-*.ps1`) with absolute paths to the TestBoost installation
- An integrity token secret in `.testboost/.tb_secret`

After installation, you can launch your LLM CLI directly from your Java project:

```bash
cd /path/to/your/java/project
claude   # or opencode
# /testboost.analyze .
```

The wrapper scripts handle virtualenv activation and path resolution automatically.

> **Note:** If you move the TestBoost installation directory, re-run the `install` command to update the paths.

## What Happens in Your Java Project

After running `init` (or `install`), TestBoost creates a `.testboost/` directory in your Java project:

```
your-java-project/
+-- .testboost/
|   +-- config.yaml
|   +-- .tb_secret              # Integrity token secret (git-ignored)
|   +-- scripts/                # Wrapper scripts (only after install)
|   |   +-- tb-init.sh          # or tb-init.ps1 on Windows
|   |   +-- tb-analyze.sh       # or tb-analyze.ps1 on Windows
|   |   +-- ...
|   +-- sessions/
|       +-- 001-test-generation/
|           +-- spec.md
|           +-- analysis.md
|           +-- coverage-gaps.md
|           +-- generation.md
|           +-- validation.md
|           +-- logs/
+-- src/
+-- pom.xml
```

Generated test files are written directly to `src/test/java/...` in your project. Review them before committing.

## Next Steps

- [Workflow](./workflow.md) -- Understand what each step does in detail
- [Configuration](./configuration.md) -- Customize coverage targets and test options
- [LLM Providers](./llm-providers.md) -- Choose and configure your LLM provider
