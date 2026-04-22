# TestBoost

AI-powered test generation for Java/Spring Boot projects, driven by LLM CLI tools.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## What is TestBoost?

TestBoost analyzes your Java project, identifies files lacking test coverage, and generates unit tests using LLMs (Google Gemini, Anthropic Claude, or OpenAI). It is designed to be used interactively through LLM CLI tools like [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [OpenCode](https://opencode.ai), where the AI assistant orchestrates the workflow step by step.

The workflow is simple:

```
init --> analyze --> gaps --> generate --> validate
```

Each step produces a markdown report in your project's `.testboost/` directory, giving you full visibility into what was analyzed, what's missing, and what was generated.

## Quick Start

### Linux / macOS (Bash)

```bash
# Clone and install
git clone https://github.com/axtion-io/TestBoost.git
cd TestBoost
pip install poetry
poetry install
poetry shell                   # activate the virtual environment

# Configure your LLM (copy and edit .env)
cp .env.example .env
# Edit .env — see "LLM Providers" below

# Launch your LLM CLI from the TestBoost directory
claude                         # or: opencode
```

### Windows (PowerShell)

```powershell
# Clone and install
git clone https://github.com/axtion-io/TestBoost.git
cd TestBoost
pip install poetry
poetry install
poetry shell                   # activate the virtual environment

# Configure your LLM (copy and edit .env)
Copy-Item .env.example .env
# Edit .env — see "LLM Providers" below

# Launch your LLM CLI from the TestBoost directory
claude                         # or: opencode
```

### Use the slash commands

Once inside the LLM CLI:

```
/testboost.init /path/to/your/java/project
/testboost.analyze /path/to/your/java/project
/testboost.gaps /path/to/your/java/project
/testboost.generate /path/to/your/java/project
/testboost.validate /path/to/your/java/project
```

Or use the CLI directly (no LLM CLI needed):

```bash
python -m testboost init /path/to/java/project
python -m testboost analyze /path/to/java/project
python -m testboost gaps /path/to/java/project
python -m testboost generate /path/to/java/project
python -m testboost validate /path/to/java/project
```

### Installing into a Java project

You can install TestBoost commands directly into a Java project. The installer
copies slash commands and wrapper scripts so the LLM CLI can call TestBoost
from the target project directory.

```bash
# Install with bash wrapper scripts (default, Linux/macOS)
python -m testboost install /path/to/java/project

# Install with PowerShell wrapper scripts (Windows)
python -m testboost install /path/to/java/project --shell-type powershell
```

## How It Works

1. **Init** -- Creates a `.testboost/` session directory in your Java project
2. **Analyze** -- Scans project structure, frameworks (Spring Boot, JPA, etc.), and existing test conventions
3. **Gaps** -- Compares source files against existing tests to find what's missing
4. **Generate** -- Uses an LLM to generate JUnit 5 tests with Mockito mocks, following your project's conventions
5. **Validate** -- Compiles and runs the generated tests with Maven

All results are written to `.testboost/sessions/<id>/` as markdown files, so you can review everything before committing.

## Supported LLM CLIs

| Tool | Command directory | Status |
|------|-------------------|--------|
| [Claude Code](https://docs.anthropic.com/en/docs/claude-code) | `.claude/commands/` | Ready |
| [OpenCode](https://opencode.ai) | `.opencode/commands/` | Ready |

## LLM Providers

TestBoost supports three LLM provider modes via the `LLM_PROVIDER` variable in `.env`:

| Provider | Use case | Setup |
|----------|----------|-------|
| `openai` | **Local vLLM** or any OpenAI-compatible endpoint | `OPENAI_API_BASE`, `OPENAI_API_KEY` |
| `google-genai` | Google Gemini API | `GOOGLE_API_KEY` |
| `anthropic` | Anthropic Claude API | `ANTHROPIC_API_KEY` |

**Local vLLM (recommended for air-gapped / corporate setups):**
vLLM serves a local model behind an OpenAI-compatible API. Set `LLM_PROVIDER=openai`,
point `OPENAI_API_BASE` to the vLLM endpoint, and set `MODEL` to the model path or name.

**Corporate proxy / SSL:** if your LLM endpoint uses an internal CA certificate,
configure `SSL_CERT_FILE` and `REQUESTS_CA_BUNDLE` in `.env`.
See [CLAUDE.md](./CLAUDE.md#corporate-network--proxy--ssl) and `.env.example` for details.

Set the `MODEL` environment variable to choose a specific model. See [LLM Providers](./docs/llm-providers.md) for more.

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](./docs/getting-started.md) | Installation and first usage |
| [Workflow](./docs/workflow.md) | Detailed description of each step |
| [LLM Providers](./docs/llm-providers.md) | Provider configuration and comparison |
| [Configuration](./docs/configuration.md) | Project settings and environment variables |
| [Session Format](./docs/session-format.md) | Structure of `.testboost/` session files |
| [Architecture](./docs/architecture.md) | Internal architecture and design |
| [Prompts](./docs/prompts.md) | LLM prompts used for test generation |
| [Contributor Quickstart](./docs/contributor-quickstart.md) | Set up a development environment |

## Development

```bash
# Run tests
pytest tests/

# Lint
ruff check .

# Type check
mypy src/
```

See [CONTRIBUTING.md](./CONTRIBUTING.md) for contribution guidelines.

## License

Apache License 2.0 -- see [LICENSE](LICENSE).

Copyright 2026 TestBoost Contributors
