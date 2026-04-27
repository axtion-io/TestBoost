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

# Plugin system tests
pytest tests/unit/lib/plugins/ tests/integration/test_plugin_detection.py -v

# CLI and session tests
pytest tests/unit/testboost/ -v

# With coverage report
pytest --cov=src --cov-report=html
# Open htmlcov/index.html in your browser

# Specific test file
pytest tests/unit/testboost/test_cli.py

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

# Run everything (same as CI)
pytest && ruff check .
```

## Project Structure

```
TestBoost/
+-- src/
|   +-- java/                   # Java-specific analysis (no LLM dependency)
|   |   +-- parsing_utils.py    # Shared low-level Java parsers
|   |   +-- discovery.py        # Java source file finder + classifier
|   |   +-- class_analyzer.py   # Full class index builder + test example extractor
|   +-- test_generation/        # LLM-backed generation tools
|   |   +-- analyze.py          # Project structure analysis
|   |   +-- conventions.py      # Test convention detection
|   |   +-- generate_unit.py    # LLM-based unit test generation
|   |   +-- mutation.py         # PIT mutation testing runner
|   |   +-- analyze_mutants.py  # Mutation report analysis
|   |   +-- killer_tests.py     # Killer test generation
|   +-- lib/                    # Infrastructure layer
|   |   +-- bridge.py           # Bridge to core functions (mockable boundary)
|   |   +-- cli.py              # CLI entry point (10 commands + --list-plugins)
|   |   +-- session_tracker.py  # Markdown-based session management
|   |   +-- plugins/            # Technology plugin system
|   |   |   +-- base.py         # TechnologyPlugin ABC
|   |   |   +-- registry.py     # PluginRegistry
|   |   |   +-- java_spring.py  # Java/Spring plugin
|   |   |   +-- python_pytest.py # Python/pytest plugin
|   |   |   +-- go_testing_stub.py # Go stub (extensibility demo)
|   |   +-- llm.py              # LLM provider abstraction
|   |   +-- maven_error_parser.py
|   |   +-- prompt_utils.py     # Shared template load + render
+-- config/
|   +-- prompts/testing/        # Java/Spring LLM prompt templates
|   +-- prompts/testing/python_pytest/ # Python/pytest LLM prompt templates
+-- tests/                      # Test suite
|   +-- unit/lib/plugins/       # Plugin unit tests
|   +-- unit/testboost/         # CLI, session, integrity tests
|   +-- integration/            # Plugin detection, LLM connectivity
|   +-- e2e/                    # Full LLM workflow tests
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

All imports from `src/` go through `src/lib/bridge.py`. In tests, mock at the bridge level:

```python
@patch("src.lib.bridge.analyze_project_context")
async def test_analyze(mock_fn):
    mock_fn.return_value = '{"success": true}'
    # ...
```

### Session State in Markdown

Session state is stored in `.testboost/sessions/<id>/<step>.md` files with YAML frontmatter. The `technology` field in session `spec.md` tracks which plugin is used. See [Session Format](./session-format.md).

### Dual-Output Logging

The `MdLogger` writes concise output to stdout (for LLM consumption) and detailed logs to markdown files (for the user).

## Common Tasks

### Adding a New Technology Plugin

1. Create `src/lib/plugins/<your_plugin>.py` implementing all `TechnologyPlugin` abstract members
2. Add `_registry.register(YourPlugin())` in `src/lib/plugins/__init__.py`
3. Create prompt templates in `config/prompts/testing/<your_tech>/`
4. Add unit tests in `tests/unit/lib/plugins/test_<your_plugin>.py`
5. Add detection test cases in `tests/integration/test_plugin_detection.py`
6. No changes to the core engine (`cli.py`, `bridge.py`, `generate_unit.py`) are required

### Adding a New CLI Command

1. Add the command function in `src/lib/cli.py`
2. Register the subparser in the `main()` function
3. Add a shell script wrapper in `scripts/`
4. Create slash command files in `.claude/commands/` and `.opencode/commands/`
5. Add tests

### Modifying Test Generation Prompts

Edit the prompt templates in `config/prompts/testing/` (Java) or `config/prompts/testing/python_pytest/` (Python). Changes take effect on the next `generate` run.

### Adding a New Core Function

1. Implement in `src/test_generation/`
2. Add a bridge function in `src/lib/bridge.py`
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
git checkout -b feature/x    # Create branch
git commit -m "feat: ..."    # Commit
```
