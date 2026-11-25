---
description: Write unit tests for the untested code of a Java/Maven project, guided by TestBoost briefs (real coverage gaps, test stack actually available, project conventions, exact signatures), then compile, run and measure them. Use when asked to add or improve tests in a Maven project.
argument-hint: "[project path] [class or file filter]"
---

# Write tests with TestBoost briefs

You write the tests; the `testboost` MCP server prepares the briefs and checks the result.

1. `init`, `analyze`, then `gaps` (coverage on: gaps are the classes below 80% line coverage,
   with their uncovered lines).
2. `context` (optionally `files` = the class names the user asked for). For each entry: read the
   brief, read the class, and write the test **at the exact path given** — nowhere else.
   - Assert exact values, both branches and the boundaries; derive expected values from the code
     or an independent source, never guess. Only the libraries the brief lists.
3. `register_tests`: fix every compilation error it reports, then call it again.
4. `validate`: the new tests must pass. A failing test is either a wrong expectation or a real
   bug — tell the user which, do not weaken the assertion silently.
5. Finish with the `check` skill on the change, and report its measured numbers.
