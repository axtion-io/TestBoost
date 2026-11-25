---
description: Strengthen Java tests by killing the PIT mutants that survive them — each one is a code change the tests ran but did not notice. Use after a check or mutation run reports surviving mutants, or when asked to improve test quality or the mutation score.
argument-hint: "[project path]"
---

# Kill surviving mutants

1. If there is no session yet: `init`, `analyze`, then `mutate` (it lists survivors with ids).
2. `context` with `killer` on: one brief per class, with each surviving mutant (line, mutation).
3. For each mutant, write a test in the killer test file given that **fails on the mutated code and
   passes on the real code** — usually an exact assertion at a boundary or on a returned value.
4. A mutant no test can observe: do not write a useless test. Explain why to the user and, with
   their agreement, call `declare_equivalent` with that reason.
5. `register_killer_tests`, then `mutate` again (or the `check` skill) and report the measured
   score before/after.
