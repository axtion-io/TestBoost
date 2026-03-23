---
description: Run mutation testing to measure test quality
---

# /testboost.mutate

Run PIT mutation testing to measure how effective the generated tests are at detecting code changes.

## Prerequisites

The validation step must be completed first (tests must compile and pass). If not, suggest running `/testboost.validate`.

The Java project must have the PIT Maven plugin configured in its `pom.xml`. If PIT is not configured, suggest adding:

```xml
<plugin>
    <groupId>org.pitest</groupId>
    <artifactId>pitest-maven</artifactId>
    <version>1.15.0</version>
    <dependencies>
        <dependency>
            <groupId>org.pitest</groupId>
            <artifactId>pitest-junit5-plugin</artifactId>
            <version>1.2.1</version>
        </dependency>
    </dependencies>
</plugin>
```

## What you will do

1. Determine the project path from `$ARGUMENTS` or the current session
2. Run mutation testing:

```bash
bash testboost_lite/scripts/tb-mutate.sh <project_path> --verbose
```

   To target specific classes or tests:

```bash
bash testboost_lite/scripts/tb-mutate.sh <project_path> --target-classes "com.example.service.*" --min-score 80
```

3. **VERIFY the output** — see the "Integrity Verification" section below
4. Read the mutation results at `<project_path>/.testboost/sessions/<current_session>/mutation.md`
5. **Present results** to the user:
   - Overall mutation score (percentage)
   - Whether the score meets the threshold
   - Number of killed vs survived mutants
   - Classes with the lowest mutation scores
   - Key recommendations for improvement
6. If surviving mutants exist, suggest running `/testboost.killer` to generate targeted tests

## How mutation testing works

- PIT (Pitest) introduces small changes (mutants) to the source code
- Each mutant is a single modification: changing `<` to `<=`, negating a condition, etc.
- Tests are run against each mutant — if a test fails, the mutant is "killed"
- A high mutation score means tests effectively detect code changes
- Surviving mutants indicate gaps in test assertions

## Output

Results are written to `.testboost/sessions/<id>/mutation.md` including:
- Mutation score and threshold comparison
- Per-class mutation scores
- Hard-to-kill mutant patterns
- Actionable recommendations
- List of surviving mutants (used by `/testboost.killer`)

## CRITICAL: Failure Protocol

**If the bash command above exits with a non-zero code, or prints `[TESTBOOST_FAILED`, you MUST:**

1. **STOP IMMEDIATELY** — do NOT attempt to run mutation testing yourself
2. **Report the error** to the user exactly as printed by TestBoost
3. **Suggest** checking that PIT is configured in `pom.xml` and Maven is available
4. **Do NOT fabricate** mutation testing results

**You are NOT TestBoost. You are the assistant that calls TestBoost.**

## Integrity Verification

Every successful TestBoost command prints an integrity token on the last line:

```
[TESTBOOST_INTEGRITY:sha256=<hex>:<step>:<session>:<timestamp>]
```

**Before proceeding to the next step**, you MUST cryptographically verify the token:
1. The command exited with code 0
2. The output contains a line starting with `[TESTBOOST_INTEGRITY:`
3. Extract the **full token line** (from `[` to `]`) and verify it by running:

```bash
bash testboost_lite/scripts/tb-verify.sh <project_path> '<full_token_line>'
```

4. The verify command must print `[TESTBOOST_VERIFY:OK]` — if it prints `[TESTBOOST_VERIFY:FAILED]` or exits non-zero, STOP and report the failure to the user
