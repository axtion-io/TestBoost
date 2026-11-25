# java-demo

A small Maven project, **deliberately under-tested**, to see what `testboost check` measures:

```bash
testboost check examples/java-demo
```

- `Shipping` has two tests that pass but check neither boundary (1 kg, 50.00): line coverage is
  almost complete, yet several mutants survive.
- `PromoCode` has no test at all.

PIT is declared in `pom.xml` by `testboost pit-setup` (pitest-maven + pitest-junit5-plugin).
CI runs the real Maven, JaCoCo and PIT on a copy of this project: `tests/e2e/test_check_maven.py`.
