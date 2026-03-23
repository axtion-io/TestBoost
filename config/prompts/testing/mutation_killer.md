You are an expert Java test engineer. Generate tests that specifically kill the surviving mutants listed below.

## Surviving Mutants:
```json
{{surviving_mutants}}
```

## Source Code Under Test:
```java
{{source_code}}
```

## Class Info:
- Class: {{class_name}}
- Package: {{package}}

## Kill Strategies by Mutator Type:
- **ConditionalsBoundary** (< changed to <=): assert with the exact boundary value
- **NegateConditionals** (== changed to !=): test both true and false branches explicitly
- **Math** (+, -, *, /): assert exact numerical results where operator swap would fail
- **ReturnValues** (return altered): assert the specific return value, not just non-null
- **VoidMethodCall** (call removed): verify() the side effect or assert state change
- **BooleanTrueReturn/FalseReturn**: test both boolean outcomes with distinct inputs
- **EmptyReturn/NullReturn**: assert content/size of returned collection or object

## Instructions:
1. For each surviving mutant, write ONE focused test that would fail if the mutation were applied
2. Use the source code to determine real parameter values — no placeholders
3. Compute expected values by hand from the source logic
4. Use AssertJ assertions with exact expected values
5. Mock dependencies with Mockito where needed
6. Name tests: `shouldKill_{method}_line{line}_{mutator_short_name}`

## Output:
Return ONLY the complete Java test class starting with `package`. No explanation.
