# Changelog

All notable changes to TestBoost are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

Release process: bump `version` in `pyproject.toml`, update this file,
tag `vX.Y.Z` on `main` after merge, and pin `TESTBOOST_PACKAGE` in the
GitLab CI template to the new tag.

## [Unreleased]

### Added
- **Agent mode**: `testboost context` writes one generation prompt per gap (or, with `--killer`,
  per class with surviving mutants) and the expected test path; the host agent writes the tests;
  `generate --agent` / `killer --agent` register and compile them without any LLM call or API
  key. Default mode of the `/testboost.generate` and `/testboost.killer` slash commands.
- **MCP server** (`pip install "testboost[mcp]"`, `testboost-mcp`, stdio): `check`, `pit_setup`
  and the agent-mode loop as tools, each running the CLI in a subprocess; no LLM call.
- **Claude Code plugin** (`plugin/`, marketplace in `.claude-plugin/`): skills `check`,
  `write-tests`, `kill-mutants` over the MCP server; passes `claude plugin validate --profile
  directory`.
- **`testboost check`**: the judge. JaCoCo line coverage + PIT mutation score of the whole
  project or, with `--base <ref>`, of the lines changed since that ref; exit 0/1/2 for CI; writes
  an MR-ready `report.md`. A red suite is reported as such, not scored. No session, no LLM.
- `testboost gitlab post-report` / `testboost github post-report`: the check report as one sticky
  MR/PR comment (updated on each push, only TestBoost's own), and the CI templates
  `templates/{gitlab,github}/testboost-check.yml`. A `testboost` console script is installed.
- **`testboost pit-setup`**: declares `pitest-maven` 1.30.2 + `pitest-junit5-plugin` 1.2.3 in the
  root pom (formatting kept, idempotent). PIT is no longer run at Maven's "latest" version.
- `examples/java-demo`: a small public Maven project, under-tested on purpose; the `maven` CI job
  runs the real Maven/JaCoCo/PIT on it (`tests/e2e/test_check_maven.py`).
- **Equivalent mutants**: `testboost equivalent <project> <id> --reason …` declares a surviving
  mutant that no test can observe (project-level, keyed on its location so it comes back when the
  code moves). `mutate` reports an effective score without them (the threshold applies to it);
  killer steps no longer target them; in LLM mode the model can only suggest them.

### Fixed
- `mutate` read the first `mutations.xml` found — possibly a stale one, or another module's — and
  compiled nothing first: it now compiles tests, aggregates every module's fresh report, and
  refuses a JUnit 5 project whose pom lacks the PIT JUnit 5 plugin.
- The mutation report's recommendations counted every mutant of a mutator, killed ones included
  ("40 negated conditional mutants survived" with 0 survivors).
- A class holding a nested record (`class Vaud { record Ferie(…) }`) was analysed as that record,
  with no methods; comments mentioning `class X` are no longer read as declarations.

### Changed
- `gaps --coverage` (Java/Maven): gaps are the classes below `--min-coverage` JaCoCo line coverage,
  with their uncovered lines — instead of "no `FooTest` file" (4 real gaps instead of 70 on a module
  tested by feature).
- Agent mode: `context` writes a ~25-line brief (test path, available stack, conventions, exact
  dependency signatures, uncovered lines, examples to imitate) instead of the full LLM prompt; the
  agent reads the source itself. Same for `context --killer`.
- `validate` runs only the generated tests (`-Dtest=…` for Maven); `--full` runs the whole suite.
- `mutate --target-tests` no longer requires a prior `validate`: PIT checks those tests pass itself.
- `--files` (`context`, `generate`) also matches source files that are not gaps, and a pattern
  matching nothing is an error instead of silently selecting every gap.
- Agent briefs are named after the source file (`agent/Vaud.md`), not the detected class.
- Generation prompt: only the rules relevant to the class (JPA, reflection, reactive, Mockito),
  no mandatory setup method, at most 2 test examples (same package first, 80 lines each) —
  about half the size on a real module.
- Human-in-the-loop pause/resume for CI: `generate`/`validate`/`killer`
  pause with exit code 78 and an HMAC-signed `question.json`; answers are
  signed, bound to their question, TTL-checked, and consumed only after
  the answered work succeeds (crash-safe resume).
- Batched questions: one MR comment per run covering every uncertain
  file, with per-class scoped answers.
- GitLab CI integration: `templates/gitlab/testboost.yml` (orange pause
  status via `allow_failure: exit_codes`, session state committed to the
  MR branch), `testboost gitlab post-question|fetch-answer` subcommands,
  and a FastAPI resume webhook under `tools/gitlab-webhook/`.
- Operations commands: `resume`, `sign-answer`, `cleanup`, `doctor`;
  one `[TESTBOOST_METRICS:{...}]` line per command on stderr.
- `scripts/find_dead_code.py`: AST-based dead-code finder (module
  reachability + symbol references), wired into CI.

### Changed
- `src/lib/cli.py` is now a thin facade; command implementations live in
  `src/lib/commands/` (one module per command group).
- Prompt templates moved from `config/prompts/` to `src/prompts/` and
  ship inside the wheel: a pip-installed TestBoost is self-contained.
- Log directory is the working directory's `logs/` (overridable via
  `TESTBOOST_LOG_DIR`) instead of the installation directory.
- CI runs the full test suite with a 75% coverage gate, blocking ruff on
  the whole repo, and a packaging sanity job (wheel built and
  smoke-tested in a clean venv).

### Security
- Resume webhook and `gitlab fetch-answer` refuse fork MRs and MRs of
  another branch (a fork branch named like a paused member branch could
  resume and push to it with the fork author's answer).
- Generated / killer / validate-fix test writes are confined to the project;
  PIT class names are validated before becoming paths.
- `.tb_secret` is created `0600`; `.testboost/.gitignore` entries are
  idempotent (the logs entry was lost when CI seeded the secret first).
- CI security model documented (project code runs with the CI secrets in
  scope; pin `TESTBOOST_PACKAGE`; integrity tokens are a guardrail).

### Fixed
- `pom.xml` parsing on real (namespaced) POMs: java.version, coordinates
  and `activeByDefault` profiles were silently lost (falsy-Element bug).
- `spring-boot-starter-test` implies Mockito/AssertJ: the prompt told the
  LLM "Mockito is NOT available" on standard Spring Boot projects.
- `gaps` uses the session plugin's test naming (shared with `analyze`):
  `TestDataBuilder` looked untested and its test was overwritten; every
  Python file was reported untested.
- Convention detection: `@Nested`/`@ParameterizedTest` never reached the
  prompt (wrong key); the dominant naming pattern was always camelCase.
- Controller prompt sent a literal `{class_name}` to the LLM.
- Compile fixes use the plugin's prompt (pytest prompt was never used) and
  strip fences of any language (` ```python ` left `python` in the code).
- `validate`: a compile timeout crashed with UnboundLocalError.
- `killer`: no non-compiling template fallback; skipped classes reported;
  multi-module source lookup.
- Python plugin classified files relative to the CWD.
- `config.yaml` is read: `max_correction_retries`, `test_timeout_seconds`
  (the four keys nothing read are no longer written).
- `install` ships the `mutate`, `killer` and `verify` commands.
- Plugin prompt resolution: `generate` crashed on a doubled
  `config/prompts/config/prompts/...` path whenever a plugin supplied its
  prompt directory (introduced with the plugin system, masked by mocked
  LLM calls in tests).
- `cleanup` now detects real paused sessions (`emit_question` flips the
  session-level status).
- `killer_hints` are actually injected into the killer-test LLM prompt.
- The GitLab state-commit push no longer embeds the token in the remote
  URL (credential store instead), so a failing push cannot leak it into
  CI logs.

### Removed
- Go stub plugin (it handled `go.mod` projects with the Java prompts).
- Dead code found in review: logging taxonomy and unused helpers, unread
  settings (`debug`, `log_level`, `max_retries`), `consume_answer`,
  unreachable generation fallbacks, fake `estimated_coverage` metric.
- Tests that tested nothing (mocked "load tests", `assert callable(...)`,
  assertions on literal dicts) and the duplicate `ci-tests.yml` workflow.
- Dead survivors of the 001 simplification: the orphaned agent workflow,
  broken e2e suite, server-era config fields, Prometheus/Grafana/
  Alertmanager configs, LangSmith settings, and ~1,900 lines of
  unreferenced code.
- Orphaned dependencies: `langgraph`, `deepagents`, `mcp`, `typer`,
  `greenlet`.

## [0.2.0] - 2026-06-02

- Simplified architecture (spec 001): FastAPI/PostgreSQL stack replaced
  by a markdown-driven CLI (`python -m testboost`).
- Multi-technology plugin system (spec 010): Java/Spring, Python/pytest,
  Go stub.
- HMAC integrity tokens proving CLI output authenticity.
- PowerShell wrapper support for Windows.
