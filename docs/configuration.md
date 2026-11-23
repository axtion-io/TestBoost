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

You can set these in a `.env` file at the TestBoost root.

## Project Configuration (config.yaml)

`testboost init` creates `.testboost/config.yaml` in your project. It holds the
budgets of the generation loops — the only two settings TestBoost reads:

```yaml
max_correction_retries: 3
test_timeout_seconds: 300
```

| Setting | Default | Read by | Description |
|---------|---------|---------|-------------|
| `max_correction_retries` | `3` | `generate`, `killer` | Compile checks per generated test; at most `N - 1` LLM fixes run (a developer hint caps it to one fix) |
| `test_timeout_seconds` | `300` | `generate` (runtime check), `validate` | Timeout of one test run (`mvn test`, `pytest`) |

Unknown keys, non-integer or non-positive values are ignored (the default
applies), so a typo never breaks a run.

Test *style* is not configured: `analyze` detects your project's conventions
(naming pattern, assertion library, Mockito vs `@MockBean`, `@Nested`,
`@ParameterizedTest`) and the test dependencies declared in `pom.xml`
(JUnit 4/5, Mockito, AssertJ — implied by `spring-boot-starter-test`), and the
generation prompt follows them.

Build flags (Maven profiles, `-D` properties) are set per session in
`sessions/<id>/analysis.md` (`maven_compile_cmd` / `maven_test_cmd`);
`activeByDefault` profiles and `.mvn/maven.config` are picked up automatically.

## CLI Options

Most commands accept these flags:

| Flag | Description |
|------|-------------|
| `--verbose` / `-v` | Show detailed output during execution |
| `--files FILE1 FILE2` | (generate only) Limit generation to specific source files |
| `--name NAME` | (init only) Custom session name |
| `--description TEXT` | (init only) Description of what to test and why |
| `--tech IDENTIFIER` | (init only) Override auto-detected technology plugin (e.g. `java-spring`, `python-pytest`) |
| `--min-score FLOAT` | (mutate only) Minimum mutation score threshold (default: 80) |
| `--max-tests INT` | (killer only) Maximum number of killer tests to generate (default: 10) |
