# Configuration

TestBoost is configured through environment variables and a per-project `config.yaml` file.

## Environment Variables

### Required

Set at least one LLM API key:

| Variable | Description |
|----------|-------------|
| `GOOGLE_API_KEY` | Google Gemini API key |
| `ANTHROPIC_API_KEY` | Anthropic Claude API key |
| `OPENAI_API_KEY` | OpenAI API key |

### Optional

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL` | `claude-sonnet-4-6` | LLM model to use (default provider is `anthropic`). Examples: `gemini-2.5-flash`, `openai/gpt-4o` |
| `LLM_TIMEOUT` | `120` | Timeout in seconds for LLM requests |
| `LANGSMITH_TRACING` | `false` | Enable LangSmith tracing for LLM observability |
| `LANGSMITH_API_KEY` | -- | LangSmith API key (required if tracing is enabled) |
| `LANGSMITH_PROJECT` | `testboost` | LangSmith project name |

You can set these in a `.env` file at the TestBoost root.

## Project Configuration (config.yaml)

When you run `testboost init`, a `config.yaml` file is created in your Java project at `.testboost/config.yaml`. This file controls test generation behavior for that project.

### Default Settings

```yaml
coverage_target: 80
max_complexity: 20
mock_framework: mockito
assertion_library: assertj
max_correction_retries: 3
test_timeout_seconds: 300
```

### Settings Reference

| Setting | Default | Description |
|---------|---------|-------------|
| `coverage_target` | `80` | Target code coverage percentage for generated tests |
| `max_complexity` | `20` | Maximum cyclomatic complexity threshold for analysis |
| `mock_framework` | `mockito` | Mocking framework to use in generated tests |
| `assertion_library` | `assertj` | Assertion library to use (`assertj`, `junit`, `hamcrest`) |
| `max_correction_retries` | `3` | Number of auto-correction retries during generation |
| `test_timeout_seconds` | `300` | Maven test execution timeout in seconds |

### Customizing for Your Project

Edit `.testboost/config.yaml` after initialization to match your project's preferences:

```yaml
# Example: project using Hamcrest assertions with strict coverage
coverage_target: 90
assertion_library: hamcrest
test_timeout_seconds: 600
```

TestBoost also detects your project's existing conventions during the `analyze` step (naming patterns, assertion styles, mocking usage) and uses them when generating tests. Manual configuration is only needed to override or supplement the auto-detected settings.

## CLI Options

Most commands accept these flags:

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Show detailed output during execution |
| `--files FILE1 FILE2` | (generate only) Limit generation to specific source files |
| `--no-llm` | (generate only) Use template-based generation instead of LLM |
| `--name NAME` | (init only) Custom session name |
| `--description TEXT` | (init only) Description of what to test and why |
