---
description: Measure how good the tests of a Java/Maven project are — JaCoCo line coverage and PIT mutation score, on the whole project or only on the lines a change touches. Use when asked whether tests are good enough, before opening a merge request, or after writing tests, to verify them instead of assuming.
argument-hint: "[project path] [base ref, e.g. origin/main]"
---

# Check the tests (measured, not declared)

Use the `check` tool of the `testboost` MCP server. Never claim a coverage or mutation score you did
not get from it.

1. Project path: `$ARGUMENTS` or the current directory. If a base ref is given (or the work is on a
   branch), pass it as `base` to judge only the lines changed since its merge base.
2. If the result says PIT needs its JUnit 5 plugin, call `pit_setup`, show the user the `pom.xml`
   diff, and ask before committing it. Then call `check` again.
3. Exit 2 means the measure failed (a test is red, the build breaks): report that, fix the cause
   first; there is no score to discuss.
4. Present the verdict table, then what to do:
   - **Uncovered lines**: tests that execute them are missing.
   - **Surviving mutants**: a change the tests ran but did not notice — a missing or too weak
     assertion. Offer to write the killing tests (skill `kill-mutants`).
   - A mutant no test can observe (e.g. sorting a list that is always built sorted) may be
     declared with `declare_equivalent` and a real reason — only with the user's agreement,
     never to make a number pass.
