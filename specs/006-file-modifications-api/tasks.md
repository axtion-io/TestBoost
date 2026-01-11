# Tasks: API Endpoints for File Modifications Tracking

**Input**: Design documents from `/specs/006-file-modifications-api/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/api.yaml, quickstart.md

**Tests**: Included based on plan.md (pytest, pytest-asyncio, httpx)

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Paths use single project structure: `src/`, `tests/`

---

## Phase 1: Setup

**Purpose**: No setup needed - extending existing project with new feature

> This feature extends the existing TestBoost API. No project initialization required.

**Checkpoint**: Proceed directly to Foundational phase

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: User Stories 1, 2, and 3 all depend on these foundational tasks

- [ ] T001 Create Alembic migration to add `metadata` JSONB column to artifacts table in src/db/migrations/versions/006_add_artifact_metadata.py
- [ ] T002 Run migration to apply database schema change: `alembic upgrade head`
- [ ] T003 [P] Add `metadata` field to Artifact SQLAlchemy model in src/db/models/artifact.py
- [ ] T004 [P] Create unified diff generation utility in src/lib/diff.py with `generate_unified_diff()` function
- [ ] T005 [P] Create `FileModificationMetadata` Pydantic model in src/api/models/sessions.py
- [ ] T006 [P] Update `ArtifactResponse` Pydantic model to include `metadata` field in src/api/models/sessions.py
- [ ] T007 [P] Add `is_binary_content()` helper function in src/lib/diff.py for binary detection

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Download Artifact Content (Priority: P1) 🎯 MVP

**Goal**: Enable frontend to download raw artifact content with correct Content-Type headers

**Independent Test**: Create session with artifact, call `GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content`, verify raw content returned with correct Content-Type

### Tests for User Story 1

- [ ] T008 [P] [US1] Create integration test for content download endpoint in tests/integration/test_artifact_content.py
- [ ] T009 [P] [US1] Add test case for 404 when artifact not found in tests/integration/test_artifact_content.py
- [ ] T010 [P] [US1] Add test case for 400 when binary content in tests/integration/test_artifact_content.py
- [ ] T011 [P] [US1] Add test case for 413 when content > 10MB in tests/integration/test_artifact_content.py

### Implementation for User Story 1

- [ ] T012 [US1] Add `get_artifact()` method to SessionService in src/core/session.py to fetch single artifact by session_id and artifact_id
- [ ] T013 [US1] Implement `GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content` endpoint in src/api/routers/sessions.py
- [ ] T014 [US1] Add UUID validation for session_id and artifact_id in endpoint (FR-013)
- [ ] T015 [US1] Add size check to return HTTP 413 when content exceeds 10MB (FR-015)
- [ ] T016 [US1] Add binary detection to return HTTP 400 for binary artifacts (FR-004)
- [ ] T017 [US1] Add structured logging for artifact content access (FR-017) in src/api/routers/sessions.py
- [ ] T018 [US1] Ensure API Key authentication is enforced on new endpoint (FR-014)

**Checkpoint**: User Story 1 complete - frontend can download any text artifact content

---

## Phase 4: User Story 2 - Track File Modifications (Priority: P1)

**Goal**: Automatically capture file modifications during workflows with original/modified content and diff

**Independent Test**: Run workflow that modifies files, query artifacts with `type=file_modification`, verify all changes captured with operation, original_content, modified_content, and diff

### Tests for User Story 2

- [ ] T019 [P] [US2] Create unit test for `generate_unified_diff()` function in tests/unit/test_diff.py
- [ ] T020 [P] [US2] Add unit test for diff with file creation (all additions) in tests/unit/test_diff.py
- [ ] T021 [P] [US2] Add unit test for diff with file deletion (all deletions) in tests/unit/test_diff.py
- [ ] T022 [P] [US2] Add unit test for diff with file modification in tests/unit/test_diff.py

### Implementation for User Story 2

- [ ] T023 [US2] Add `create_file_modification_artifact()` helper method to SessionService in src/core/session.py
- [ ] T024 [US2] Update existing `create_artifact()` method to accept optional `metadata` parameter in src/core/session.py
- [ ] T025 [US2] Add `ArtifactRepository.create_with_metadata()` method in src/db/repository.py if needed
- [ ] T026 [US2] Identify file modification points in Maven maintenance workflow in src/workflows/
- [ ] T027 [US2] Integrate `create_file_modification_artifact()` calls in Maven maintenance workflow (FR-011)
- [ ] T028 [US2] Identify file modification points in test generation workflow in src/workflows/
- [ ] T029 [US2] Integrate `create_file_modification_artifact()` calls in test generation workflow (FR-012)
- [ ] T030 [US2] Ensure immutability of file_modification artifacts - no update endpoint (FR-016)

**Checkpoint**: User Story 2 complete - all file modifications tracked with content and diff

---

## Phase 5: User Story 3 - View File Diff in Frontend (Priority: P2)

**Goal**: Provide unified diff in artifact metadata for frontend diff visualization

**Independent Test**: Retrieve `file_modification` artifact, verify diff field contains valid unified diff format

### Tests for User Story 3

- [ ] T031 [P] [US3] Add integration test verifying diff field in artifact response in tests/integration/test_artifact_content.py
- [ ] T032 [P] [US3] Add test case for diff format with create operation in tests/integration/test_artifact_content.py
- [ ] T033 [P] [US3] Add test case for diff format with delete operation in tests/integration/test_artifact_content.py

### Implementation for User Story 3

- [ ] T034 [US3] Ensure `metadata` field (including diff) is included in `GET /api/v2/sessions/{session_id}/artifacts` response
- [ ] T035 [US3] Add `?type=file_modification` filter support to artifacts list endpoint if not already present
- [ ] T036 [US3] Verify diff generation handles edge cases (empty files, very large files with truncation)

**Checkpoint**: User Story 3 complete - frontend can display visual diffs

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Validation, documentation, and cleanup

- [ ] T037 [P] Run all unit tests: `pytest tests/unit/test_diff.py -v`
- [ ] T038 [P] Run all integration tests: `pytest tests/integration/test_artifact_content.py -v`
- [ ] T039 Verify quickstart.md scenarios work correctly
- [ ] T040 [P] Run ruff linter on new/modified files: `ruff check src/lib/diff.py src/api/routers/sessions.py`
- [ ] T041 [P] Run mypy type check on new/modified files
- [ ] T042 Update API documentation if separate from code
- [ ] T043 Verify Constitution Check compliance (all 13 principles)

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1: Setup → N/A (no setup needed)
                  ↓
Phase 2: Foundational (T001-T007)
                  ↓
          ┌───────┴───────┐
          ↓               ↓
Phase 3: US1 (P1)   Phase 4: US2 (P1)
   T008-T018           T019-T030
          ↓               ↓
          └───────┬───────┘
                  ↓
          Phase 5: US3 (P2)
             T031-T036
                  ↓
          Phase 6: Polish
             T037-T043
```

### User Story Dependencies

| User Story | Depends On | Can Start After |
|------------|------------|-----------------|
| US1 (Download Content) | Foundational (T001-T007) | Phase 2 complete |
| US2 (Track Modifications) | Foundational (T001-T007) | Phase 2 complete |
| US3 (View Diff) | US2 (for artifact creation) | Phase 4 complete |

**Note**: US1 and US2 can run in parallel after Foundational phase completes.

### Within Each User Story

1. Tests written and FAIL before implementation (TDD)
2. Core implementation
3. Validation and error handling
4. Logging and security
5. Story complete before moving to next priority

### Parallel Opportunities

```
Phase 2 (Foundational):
  T003 [P] + T004 [P] + T005 [P] + T006 [P] + T007 [P] → all in parallel after T001-T002

Phase 3 (US1):
  T008 [P] + T009 [P] + T010 [P] + T011 [P] → all tests in parallel

Phase 4 (US2):
  T019 [P] + T020 [P] + T021 [P] + T022 [P] → all tests in parallel

Phase 5 (US3):
  T031 [P] + T032 [P] + T033 [P] → all tests in parallel

Phase 6 (Polish):
  T037 [P] + T038 [P] + T040 [P] + T041 [P] → all in parallel
```

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "T008 [P] [US1] Create integration test for content download endpoint"
Task: "T009 [P] [US1] Add test case for 404 when artifact not found"
Task: "T010 [P] [US1] Add test case for 400 when binary content"
Task: "T011 [P] [US1] Add test case for 413 when content > 10MB"

# Then implement sequentially:
Task: "T012 [US1] Add get_artifact() method to SessionService"
Task: "T013 [US1] Implement GET .../content endpoint"
# ... etc
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 2: Foundational (T001-T007)
2. Complete Phase 3: User Story 1 (T008-T018)
3. **STOP and VALIDATE**: Frontend can download artifact content
4. Deploy/demo if ready

### Incremental Delivery

1. Foundational → Foundation ready (migration, diff utility, models)
2. Add User Story 1 → Test independently → **MVP: Content Download Works**
3. Add User Story 2 → Test independently → **File Modifications Tracked**
4. Add User Story 3 → Test independently → **Diffs Visible**
5. Polish → Production ready

### Parallel Team Strategy

With 2 developers after Foundational phase:

- **Developer A**: User Story 1 (T008-T018)
- **Developer B**: User Story 2 tests (T019-T022), then wait for US1 completion
- Both complete → User Story 3 (T031-T036) → Polish (T037-T043)

---

## Task Summary

| Phase | Tasks | Parallelizable |
|-------|-------|----------------|
| Phase 1: Setup | 0 | N/A |
| Phase 2: Foundational | 7 | 5 |
| Phase 3: US1 | 11 | 4 |
| Phase 4: US2 | 12 | 4 |
| Phase 5: US3 | 6 | 3 |
| Phase 6: Polish | 7 | 4 |
| **Total** | **43** | **20** |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story independently completable and testable
- Verify tests fail before implementing (TDD approach)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Reference quickstart.md for testing scenarios
- Reference contracts/api.yaml for API contract validation
