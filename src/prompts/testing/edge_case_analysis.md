Analyze this Java class and return a JSON array of edge case test scenarios. No explanation, only JSON.

## Source Code:
```java
{{source_code}}
```

## Class: {{class_name}} ({{class_type}})

## Analysis Rules:

For each public method, identify edge cases from these categories:

1. **Null inputs** — each nullable parameter passed as null individually
2. **Empty collections/strings** — empty List, Set, Map, ""
3. **Boundary values** — 0, -1, Integer.MAX_VALUE, Long.MIN_VALUE for numeric params
4. **Single-element collections** — List.of(one) when code may assume size > 1
5. **Conditional boundaries** — values at, just below, and just above any comparison threshold found in the source
6. **Exception paths** — inputs that trigger catch blocks or throw statements
7. **Concurrency** — if the class uses shared mutable state, synchronized, or AtomicX

## Output Format:
```json
[
  {
    "method": "methodName",
    "scenario": "null_input_param1",
    "description": "Pass null as first parameter",
    "input_hint": "methodName(null, validArg2)",
    "expected_behavior": "throws NullPointerException | returns empty | returns default",
    "category": "null_input"
  }
]
```

Return ONLY the JSON array. Maximum 30 scenarios, prioritized by likelihood of catching real bugs.
