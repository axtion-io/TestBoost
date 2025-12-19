# Tasks: Impact Analysis & Regression Testing

**Branch**: `003-impact-analysis-testing` | **Generated**: 2025-12-19

## Overview

| Metric | Value |
|--------|-------|
| Total Tasks | 28 |
| Parallelizable | 12 |
| User Stories | 5 |
| MVP Scope | US1 (Analyze Code Changes) |

---

## Phase 1: Setup

> Project initialization and directory structure

- [ ] T001 Create src/models/ directory structure if not exists
- [ ] T002 [P] Create impact model enums in src/models/impact.py (ChangeCategory, RiskLevel, TestType, ScenarioType)
- [ ] T003 [P] Create Impact dataclass in src/models/impact.py
- [ ] T004 [P] Create TestRequirement dataclass in src/models/impact.py
- [ ] T005 [P] Create DiffChunk dataclass in src/models/impact.py
- [ ] T006 Create ImpactReport dataclass in src/models/impact_report.py

---

## Phase 2: Foundational

> Blocking prerequisites for all user stories - MUST complete before user story phases

- [ ] T007 Implement git diff extraction tool in src/mcp_servers/git_maintenance/tools/diff.py
- [ ] T008 Register diff tool in src/mcp_servers/git_maintenance/langchain_tools.py
- [ ] T009 [P] Implement diff chunking logic in src/lib/diff_chunker.py (split_by_file, count_lines, chunk_diff)
- [ ] T010 [P] Add CRITICAL_KEYWORDS set for risk detection in src/lib/risk_keywords.py

---

## Phase 3: User Story 1 - Analyze Code Changes (P1)

> **Goal**: As a developer, when I make code changes, the system analyzes the git diff to identify what changed and what could break.
>
> **Independent Test**: Provide a git diff and verify the system identifies all change categories and potential break points.

- [ ] T011 [US1] Create impact_analysis.py workflow skeleton in src/workflows/impact_analysis.py
- [ ] T012 [US1] Implement parse_diff() function to extract file-level changes in src/workflows/impact_analysis.py
- [ ] T013 [US1] Implement categorize_change() to map file paths to ChangeCategory in src/workflows/impact_analysis.py
- [ ] T014 [US1] Implement identify_affected_components() to extract class/method names from diff in src/workflows/impact_analysis.py
- [ ] T015 [US1] Implement analyze_impacts() main entry point that orchestrates parsing and categorization in src/workflows/impact_analysis.py
- [ ] T016 [US1] Add chunking support for large diffs (>500 lines) with progress callback in src/workflows/impact_analysis.py

---

## Phase 4: User Story 2 - Generate Appropriate Test Type (P1)

> **Goal**: System automatically selects the right test type based on change category, following test pyramid principle.
>
> **Independent Test**: Provide different change types and verify correct test type is selected.
>
> **Depends on**: US1 (needs categorized impacts)

- [ ] T017 [US2] Create TEST_TYPE_MAPPING dict (ChangeCategory → TestType) in src/workflows/impact_analysis.py
- [ ] T018 [US2] Implement select_test_type() that applies test pyramid logic in src/workflows/impact_analysis.py
- [ ] T019 [US2] Update analyze_impacts() to set required_test_type on each Impact in src/workflows/impact_analysis.py

---

## Phase 5: User Story 4 - Risk Classification (P2)

> **Goal**: Impacts classified by risk level to prioritize testing efforts.
>
> **Independent Test**: Provide various changes and verify correct risk classification.
>
> **Depends on**: US1 (needs identified impacts)

- [ ] T020 [P] [US4] Implement classify_risk() with keyword-based scoring in src/workflows/impact_analysis.py
- [ ] T021 [P] [US4] Add LLM fallback for ambiguous risk cases with retry logic in src/workflows/impact_analysis.py
- [ ] T022 [US4] Update analyze_impacts() to set risk_level on each Impact in src/workflows/impact_analysis.py

---

## Phase 6: User Story 3 - Generate Required Test Cases (P1)

> **Goal**: Comprehensive test cases including nominal, edge cases, and regression-prevention tests for each impact.
>
> **Independent Test**: Provide an impact and verify all required test cases are generated.
>
> **Depends on**: US1 + US2 + US4 (needs fully classified impacts)

- [ ] T023 [US3] Implement generate_test_requirements() that creates TestRequirement list per Impact in src/workflows/impact_analysis.py
- [ ] T024 [US3] Add nominal case generation (1 per impact) in generate_test_requirements()
- [ ] T025 [US3] Add edge case generation (1-2 per impact) in generate_test_requirements()
- [ ] T026 [US3] Add regression test generation for bug fixes (is_bug_fix=True) in generate_test_requirements()
- [ ] T027 [US3] Add invariant test generation for critical business rules in generate_test_requirements()
- [ ] T028 [US3] Implement build_impact_report() to assemble ImpactReport with all impacts and requirements in src/workflows/impact_analysis.py

---

## Phase 7: User Story 5 - Enforce Test Coverage in CI (P2)

> **Goal**: CI pipeline blocks merges when impact tests are missing or failing.
>
> **Independent Test**: Attempt merges with various coverage states.
>
> **Depends on**: US3 (needs ImpactReport JSON output)

- [ ] T029 [US5] Add `impact` subcommand to CLI in src/cli/commands/tests.py
- [ ] T030 [US5] Implement JSON output with --output flag in src/cli/commands/tests.py
- [ ] T031 [P] [US5] Create GitHub Actions workflow example in .github/workflows/impact-check.yml
- [ ] T032 [US5] Add exit code logic: 0=all covered, 1=uncovered business-critical impacts in src/cli/commands/tests.py

---

## Phase 8: Polish & Cross-Cutting

> Final integration, error handling, documentation

- [ ] T033 Add exponential backoff retry decorator for LLM calls in src/workflows/impact_analysis.py
- [ ] T034 Add progress logging for chunked processing in src/workflows/impact_analysis.py
- [ ] T035 [P] Validate ImpactReport against JSON schema before output in src/workflows/impact_analysis.py
- [ ] T036 [P] Add --verbose flag support for detailed output in src/cli/commands/tests.py
- [ ] T037 Update CLI help text and examples in src/cli/commands/tests.py
- [ ] T038 Add type hints and docstrings to all new public functions

---

## Dependencies

```
US1 (Analyze) ──┬──► US2 (Test Type) ──┐
                │                       │
                └──► US4 (Risk) ────────┼──► US3 (Generate) ──► US5 (CI)
```

### Story Completion Order

1. **US1** (P1) - Foundation, no dependencies
2. **US2 + US4** (P1 + P2) - Parallelizable after US1
3. **US3** (P1) - Requires US1, US2, US4
4. **US5** (P2) - Requires US3

---

## Parallel Execution Examples

### Per-Phase Parallelism

**Phase 1** (Setup):
```
T002, T003, T004, T005 can run in parallel (different model classes)
```

**Phase 2** (Foundational):
```
T009, T010 can run in parallel (different files)
```

**Phase 5** (US4):
```
T020, T021 can run in parallel (different aspects of risk classification)
```

**Phase 7** (US5):
```
T031 can run in parallel with T029, T030 (separate CI file)
```

---

## Implementation Strategy

### MVP Scope (Recommended)

Start with **User Story 1 only** (Phases 1-3):
- Delivers value: Developers can see what tests are needed
- Testable independently: `boost tests impact /path` outputs categorized impacts
- Foundation for remaining stories

### Incremental Delivery

| Increment | Stories | Deliverable |
|-----------|---------|-------------|
| MVP | US1 | Impact detection and categorization |
| +1 | US2 | Test type recommendations |
| +2 | US4 | Risk-based prioritization |
| +3 | US3 | Full test requirement generation |
| +4 | US5 | CI enforcement |

---

## Validation Checklist

- [x] All tasks have checkbox format `- [ ]`
- [x] All tasks have sequential IDs (T001-T038)
- [x] Story phase tasks have `[US#]` labels
- [x] Parallelizable tasks have `[P]` marker
- [x] All tasks have file paths
- [x] Dependencies documented
- [x] Independent test criteria per story
