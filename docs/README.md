# TestBoost Documentation

AI-powered test generation for Java/Spring (and Python/pytest) projects.
Start here to find the right document for what you're trying to do.

## I want to generate tests on my machine

Read in this order:

1. [Getting Started](./getting-started.md) — prerequisites, installation,
   first run (with an LLM CLI like Claude Code, or the bare CLI)
2. [Workflow](./workflow.md) — what each step does:
   `init → analyze → gaps → generate → validate → mutate → killer`,
   plus the auxiliary and HITL commands
3. [LLM Providers](./llm-providers.md) — Gemini / Claude / OpenAI /
   local vLLM configuration, cost estimates
4. [Configuration](./configuration.md) — `.env` variables and the
   per-project `config.yaml`

## I want TestBoost in my CI (GitLab)

TestBoost runs unattended in Merge Request pipelines and **pauses on an
MR comment** when it needs human input — the developer replies, the
pipeline resumes where it stopped.

1. [GitLab Integration](./gitlab-integration.md) — the step-by-step
   setup guide: CI template, variables, resume webhook, what the
   developer experiences, security notes
2. [Async CI Integration](./ci-async-integration.md) — the mechanics
   underneath: exit code 78, batched questions, `question.json` /
   `answer.json` schemas, HMAC signing, the per-file resume cursor

## I want to understand or debug the internals

- [Architecture](./architecture.md) — the layer stack (slash commands →
  CLI facade → commands → bridge → plugins → engine), the integrity
  token system, the project-level class index
- [Session Format](./session-format.md) — everything inside
  `.testboost/`: step files, frontmatter statuses (including
  `awaiting_input`), HITL artifacts, logs
- [Prompts](./prompts.md) — every LLM prompt template
  (`src/prompts/`), their placeholders, and how detected conventions
  flow into them

## I want to contribute

- [Contributor Quickstart](./contributor-quickstart.md) — dev
  environment in 15 minutes, project structure, common tasks (new
  plugin, new CLI command)
- [CONTRIBUTING.md](../CONTRIBUTING.md) — coding standards, PR process
- [CHANGELOG.md](../CHANGELOG.md) — release history and process
- [MVP Plan](./mvp-plan.md) — project log: phase status, decisions
  taken, lessons learned, what remains open (real-world GitLab demo)

## Quick reference

| Task | Command |
|------|---------|
| Full local run | `python -m testboost init/analyze/gaps/generate/validate <project>` |
| Show a paused session's question | `python -m testboost resume <project>` |
| Resume with a signed answer | `python -m testboost resume <project> --answer-file a.json` |
| Health check | `python -m testboost doctor <project>` |
| List technology plugins | `python -m testboost --list-plugins` |
