# TestBoost — Claude Code plugin

Measured test quality for Java/Maven projects. Claude writes the tests; TestBoost compiles, runs
and judges them with JaCoCo line coverage and PIT mutation score — on the whole project or only
on the lines a change touches — so a claimed "100% covered" is checked, not trusted.

```
/plugin marketplace add axtion-io/TestBoost
/plugin install testboost@testboost
```

## Skills

- `/testboost:check` — measure the tests of a project or of a change, and explain what is missing.
- `/testboost:write-tests` — write tests from TestBoost briefs (real gaps, available test stack,
  conventions, exact signatures), then compile, run and measure them.
- `/testboost:kill-mutants` — strengthen tests until they notice the code changes PIT makes.

The `testboost` MCP server provides the tools these skills use.

## Requirements

[uv](https://docs.astral.sh/uv/) (the server is started with `uvx`), Java and Maven for the
project. PIT is declared in the project's `pom.xml` once, by the `pit_setup` tool (you review the
diff). No LLM API key: nothing in TestBoost calls a model in this mode.
