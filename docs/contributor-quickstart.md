# Contributor Quickstart

Set up your development environment and make your first contribution in under 15 minutes.

## Prerequisites

- **Python 3.11+** ([download](https://www.python.org/downloads/))
- **Git** ([download](https://git-scm.com/downloads))

No database, Docker, or external services required.

## Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR-USERNAME/TestBoost.git
cd TestBoost
```

### 2. Create Virtual Environment and Install Dependencies

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install poetry
poetry install
```

### 3. Verify Installation

```bash
pytest tests/
ruff check .
```

All tests should pass.

### 4. (Optional) Set Up LLM API Key

If you want to test LLM-dependent features:

```bash
export GOOGLE_API_KEY="..."   # or ANTHROPIC_API_KEY or OPENAI_API_KEY
```

Most unit tests mock the LLM calls, so this is only needed for integration testing.

## Running Tests

```bash
# All tests
pytest tests/

# TestBoost CLI tests
pytest testboost/tests/

# With coverage report
pytest --cov=src --cov=testboost --cov-report=html
# Open htmlcov/index.html in your browser

# Specific test file
pytest tests/unit/test_cli.py

# Tests matching a pattern
pytest -k "test_session"

# Verbose output
pytest -vv
```

## Code Quality Checks

```bash
# Lint
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Type checking
mypy src/

# Run everything (same as CI)
pytest && ruff check . && mypy src/
```

## Project Structure

```
TestBoost/
+-- testboost/             # CLI and session management
|   +-- lib/
|   |   +-- cli.py              # Main CLI (7 commands incl. install)
|   |   +-- session_tracker.py  # Markdown-based session tracking
|   |   +-- md_logger.py        # Dual-output logger (stdout + .md files)
|   |   +-- testboost_bridge.py # Bridge to core functions in src/
|   |   +-- integrity.py        # HMAC-SHA256 integrity token system
|   |   +-- installer.py        # Persistent installer for target projects
|   +-- scripts/                # Shell script wrappers for slash commands
|   +-- templates/commands/     # Slash command templates for installation
|   +-- tests/                  # CLI unit tests
+-- src/
|   +-- mcp_servers/
|   |   +-- test_generator/     # Core analysis and generation logic
|   +-- lib/
|   |   +-- llm.py              # LLM provider abstraction
|   |   +-- maven_error_parser.py
+-- config/prompts/             # LLM prompt templates
+-- .claude/commands/           # Claude Code slash commands
+-- .opencode/commands/         # OpenCode slash commands
+-- tests/                      # Core function tests
+-- docs/                       # Documentation
```

## Making Your First Contribution

### 1. Create a Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/short-description
```

### 2. Make Your Changes

```bash
# Edit files...
# Run tests
pytest tests/
# Run linting
ruff check --fix .
```

### 3. Commit

```bash
git add <files>
git commit -m "feat: short description of change"
```

### 4. Push and Create Pull Request

```bash
git push origin feature/short-description
# Create PR on GitHub
```

## Key Patterns

### Bridge Pattern for Mocking

All imports from `src/` go through `src/lib/testboost_bridge.py`. In tests, mock at the bridge level:

```python
@patch("testboost.lib.testboost_bridge.analyze_project_context")
async def test_analyze(mock_fn):
    mock_fn.return_value = '{"success": true}'
    # ...
```

### Session State in Markdown

Session state is stored in `.testboost/sessions/<id>/<step>.md` files with YAML frontmatter. See [Session Format](./session-format.md).

### Dual-Output Logging

The `MdLogger` writes concise output to stdout (for LLM consumption) and detailed logs to markdown files (for the user).

## Common Tasks

### Adding a New CLI Command

1. Add the command function in `src/lib/cli.py`
2. Register the subparser in the `main()` function
3. Add a shell script wrapper in `scripts/`
4. Create slash command files in `.claude/commands/` and `.opencode/commands/`
5. Add tests

### Modifying Test Generation Prompts

Edit the prompt templates in `config/prompts/testing/`. Changes take effect on the next `generate` run.

### Adding a New Core Function

1. Implement in `src/mcp_servers/test_generator/tools/`
2. Add a bridge function in `src/lib/testboost_bridge.py`
3. Call it from the relevant CLI command
4. Add tests with mocked bridge calls

## Troubleshooting

### Import Errors

```bash
# Make sure you're in the TestBoost root
pwd  # Should be .../TestBoost

# Reinstall
poetry install
```

### Tests Failing

```bash
# Clear cache
rm -rf .pytest_cache __pycache__

# Run with verbose output
pytest -vv
```

## Quick Reference

```bash
poetry install               # Install dependencies
pytest                       # Run tests
ruff check .                 # Lint
ruff check --fix .           # Auto-fix
mypy src/                    # Type check
git checkout -b feature/x    # Create branch
git commit -m "feat: ..."    # Commit
```
