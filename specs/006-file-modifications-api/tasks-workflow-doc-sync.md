# Tasks: Workflow Documentation Synchronization

**Input**: Analyse des écarts entre `docs/workflow-diagrams.md` et l'implémentation API
**Date**: 2026-01-10
**Type**: Documentation & Alignement

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

---

## Phase 1: Docker Deployment Workflow (Priorité HAUTE)

**Goal**: Aligner la documentation Docker avec l'implémentation réelle

**Écart identifié**:
- Documentation: ImageBuild → ContainerCreate → HealthCheck → Retry → Cleanup
- Implémentation: analyze_dockerfile → optimize_image → generate_compose → validate_deployment

- [x] T001 [P] Update Docker Deployment state diagram in docs/workflow-diagrams.md lines 123-145
- [x] T002 [P] Update Docker State Descriptions table in docs/workflow-diagrams.md lines 148-158
- [x] T003 Update Docker Transition Conditions (if exists) in docs/workflow-diagrams.md
- [x] T004 Verify alignment with WORKFLOW_STEPS["docker_deployment"] in src/core/session.py:72-93

**Checkpoint**: ✅ Docker workflow documentation matches implementation

---

## Phase 2: Test Generation Workflow (Priorité MOYENNE)

**Goal**: Consolider la documentation Test Generation pour refléter les 4 steps réels

**Écart identifié**:
- Documentation: 9 états détaillés (ClassAnalysis, TestPlanning, UnitGeneration, IntegrationGeneration, Validation, Fixing, MutationAnalysis, KillerGeneration)
- Implémentation: 4 steps (analyze_project, identify_coverage_gaps, generate_tests, validate_tests)

- [x] T005 [P] Simplify Test Generation state diagram in docs/workflow-diagrams.md lines 66-95
- [x] T006 [P] Update Test Generation State Descriptions table in docs/workflow-diagrams.md lines 97-111
- [x] T007 Update Decision Points section in docs/workflow-diagrams.md lines 113-117
- [x] T008 Document that agent handles internal complexity (mutation, auto-correction) in docs/workflow-diagrams.md
- [x] T009 Verify alignment with WORKFLOW_STEPS["test_generation"] in src/core/session.py:50-71

**Checkpoint**: ✅ Test Generation workflow documentation matches 4-step implementation

---

## Phase 3: Maven Maintenance - RollingBack Decision (Priorité MOYENNE)

**Goal**: Clarifier et documenter la stratégie de rollback

**Écart identifié**:
- Documentation montre un état explicite "RollingBack"
- Implémentation utilise ModificationStatus.ROLLED_BACK au niveau modification

**Decision**: Option A - Documenter l'implémentation actuelle (ModificationStatus)

- [x] T010 Update Maven Maintenance diagram to remove RollingBack as session state in docs/workflow-diagrams.md lines 10-33
- [x] T011 [P] Add note about ModificationStatus.ROLLED_BACK handling in docs/workflow-diagrams.md
- [x] T012 [P] Document rollback strategy via ModificationStatus in docs/workflow-diagrams.md section "Rollback Strategy"

**Checkpoint**: ✅ Maven rollback strategy is documented and consistent

---

## Phase 4: Common Patterns Documentation (Priorité BASSE)

**Goal**: Documenter les constantes et patterns réels utilisés dans les agents

- [x] T013 [P] Add retry constants section in docs/workflow-diagrams.md
  - MAX_CORRECTION_RETRIES = 3 (from test_generation_agent.py)
  - MAX_TEST_ITERATIONS = 5 (from test_generation_agent.py)
- [x] T014 [P] Document backoff exponentiel pattern in docs/workflow-diagrams.md
- [x] T015 Update "Auto-Correction Loop" flowchart with actual retry count in docs/workflow-diagrams.md lines 188-198
- [x] T016 Document ModificationStatus lifecycle in docs/workflow-diagrams.md

**Checkpoint**: ✅ All implementation patterns are documented

---

## Phase 5: Documentation Conformance Tests (Priorité BASSE)

**Goal**: Ajouter des tests pour détecter les drifts futurs

- [x] T017 Create test_workflow_documentation.py in tests/unit/test_workflow_documentation.py
- [x] T018 [P] Add test: WORKFLOW_STEPS keys match documented workflow types
- [x] T019 [P] Add test: Each workflow has expected number of steps
- [x] T020 [P] Add test: Step codes match documented state names (or have mapping)
- [x] T021 Add test: SessionStatus enum values are documented

**Checkpoint**: ✅ Future documentation drift will be detected by tests

---

## Phase 6: Final Review

- [x] T022 Review all changes in docs/workflow-diagrams.md for consistency
- [x] T023 Run existing workflow tests to ensure no regressions (133 tests passed)
- [x] T024 Update CLAUDE.md if any workflow changes affect development guidelines (N/A - no changes needed)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Docker)**: No dependencies - can start immediately
- **Phase 2 (Test Gen)**: No dependencies - can start immediately (parallel with Phase 1)
- **Phase 3 (Maven)**: Requires decision on Option A vs B before starting
- **Phase 4 (Patterns)**: Can start after Phases 1-3 for context
- **Phase 5 (Tests)**: Should start after Phases 1-3 to test final state
- **Phase 6 (Review)**: Depends on all previous phases

### Parallel Opportunities

```bash
# Phase 1 & 2 can run in parallel:
Task: T001, T002, T003, T004 (Docker)
Task: T005, T006, T007, T008, T009 (Test Gen)

# Within Phase 4, all tasks can run in parallel:
Task: T013, T014, T015, T016

# Within Phase 5, test tasks can run in parallel:
Task: T018, T019, T020, T021
```

---

## Implementation Strategy

### MVP (Quick Win)

1. Complete Phase 1 (Docker) - High impact, independent
2. Complete Phase 2 (Test Gen) - Medium impact, independent
3. **STOP and VALIDATE**: Documentation now matches implementation for 2/3 workflows

### Full Implementation

1. Phases 1 & 2 in parallel
2. Decision on Phase 3 (Maven rollback strategy)
3. Phase 3 based on decision
4. Phase 4 (patterns documentation)
5. Phase 5 (conformance tests)
6. Phase 6 (final review)

---

## Summary

| Phase | Tasks | Priority | Effort |
|-------|-------|----------|--------|
| 1. Docker | 4 | HAUTE | ~1h |
| 2. Test Gen | 5 | MOYENNE | ~1h |
| 3. Maven | 3 | MOYENNE | ~30min |
| 4. Patterns | 4 | BASSE | ~30min |
| 5. Tests | 5 | BASSE | ~2h |
| 6. Review | 3 | - | ~30min |
| **TOTAL** | **24** | - | **~5.5h** |

---

## Notes

- All documentation changes are in `docs/workflow-diagrams.md`
- Code changes minimal (only if Option B chosen for Phase 3)
- Tests in Phase 5 prevent future drift
- Can be done incrementally - each phase delivers value
