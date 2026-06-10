# Changelog

All notable changes to TestBoost are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/); versions follow SemVer.

Release process: bump `version` in `pyproject.toml`, update this file,
tag `vX.Y.Z` on `main` after merge, and pin `TESTBOOST_PACKAGE` in the
GitLab CI template to the new tag.

## [Unreleased]

### Added
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

### Fixed
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
