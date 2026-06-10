# TestBoost

AI-powered test generation for Java/Spring Boot projects, driven by LLM CLI tools.

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)

## What is TestBoost?

TestBoost analyzes your Java project, identifies files lacking test coverage, and generates unit tests using LLMs (Google Gemini, Anthropic Claude, or OpenAI). It is designed to be used interactively through LLM CLI tools like [Claude Code](https://docs.anthropic.com/en/docs/claude-code) or [OpenCode](https://opencode.ai), where the AI assistant orchestrates the workflow step by step.

The workflow is simple:

```
init --> analyze --> gaps --> generate --> validate [--> mutate --> killer]
```

Each step produces a markdown report in your project's `.testboost/` directory, giving you full visibility into what was analyzed, what's missing, and what was generated. The optional `mutate`/`killer` steps run PIT mutation testing and generate targeted tests for surviving mutants.

TestBoost runs interactively from an LLM CLI, directly from the command line, or **unattended in CI** — pausing on a Merge Request comment whenever it needs human input (see [CI section](#using-testboost-in-ci-gitlab)).

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
6. **Mutate / Killer** (optional) -- Runs PIT mutation testing, then generates targeted tests to kill the surviving mutants

All results are written to `.testboost/sessions/<id>/` as markdown files, so you can review everything before committing.

## Using TestBoost in CI (GitLab)

TestBoost can run **unattended in your Merge Request pipelines**. The key
idea: instead of generating doubtful tests silently or failing the build,
a run that needs human input **pauses** — the job turns orange
(`allow_failure`, exit code 78), ONE comment listing every open question
is posted on the MR, and the pipeline resumes automatically when the
developer replies.

```
push MR ──> testboost:generate ──exit 78──> orange job + MR comment
                                                   │  developer replies
resume pipeline <── webhook <── GitLab Note Hook ◄─┘
   └─> picks up exactly where it paused (completed files are skipped)
```

Setup in three steps (full guide: [GitLab Integration](./docs/gitlab-integration.md)):

1. **Include the CI template** in your project's `.gitlab-ci.yml`
   (requires a GitLab mirror of TestBoost reachable by your instance):

   ```yaml
   include:
     - project: 'axtion-io/testboost'
       ref: 'main'
       file: 'templates/gitlab/testboost.yml'

   stages: [test]
   ```

   The jobs `pip install` TestBoost — no checkout or vendoring needed.

2. **Set the CI/CD variables**: `GITLAB_TOKEN` (Project Access Token,
   scopes `api` + `write_repository`), `TESTBOOST_TB_SECRET`
   (`openssl rand -hex 32`), and your LLM API key.

3. **Deploy the resume webhook** (`tools/gitlab-webhook/`, a small
   FastAPI app) and register it on **Comments** events.

What you get on every MR: project analysis, gap detection, test
generation with compile-fix retries, and the pause/resume loop. Answers
posted on the MR are HMAC-signed and bound to their question; the paused
session state travels between pipelines as a `[skip ci]` commit on the
MR branch. See [Async CI Integration](./docs/ci-async-integration.md)
for the underlying mechanics (exit codes, `question.json`/`answer.json`
schemas, signing).

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
See `.env.example` for details.

Set the `MODEL` environment variable to choose a specific model. See [LLM Providers](./docs/llm-providers.md) for more.

## Documentation

Full index with reading paths: [docs/README.md](./docs/README.md). Highlights:

| Document | Description |
|----------|-------------|
| [Getting Started](./docs/getting-started.md) | Installation and first usage |
| [Workflow](./docs/workflow.md) | Detailed description of each step |
| [GitLab Integration](./docs/gitlab-integration.md) | Run TestBoost in MR pipelines, step by step |
| [Async CI Integration](./docs/ci-async-integration.md) | The pause/resume mechanics (exit 78, signed answers) |
| [LLM Providers](./docs/llm-providers.md) | Provider configuration and comparison |
| [Architecture](./docs/architecture.md) | Internal architecture and design |
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
