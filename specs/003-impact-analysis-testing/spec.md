# Feature Specification: Impact Analysis & Regression Testing

**Feature Branch**: `003-impact-analysis-testing`
**Created**: 2025-12-18
**Status**: Draft
**Input**: Ameliorer la generation de tests en analysant impact des modifications de code pour generer des tests anti-regression cibles.

## Clarifications

### Session 2025-12-19

- Q: What is the primary input source for git diff analysis? → A: Uncommitted changes (working directory vs HEAD)
- Q: What format should the impact report use? → A: JSON (machine-parseable, CI-friendly)
- Q: How should the system handle changes exceeding 500 lines? → A: Chunk into batches of 500 lines, process sequentially with progress feedback
- Q: How should the system handle LLM API failures? → A: Retry with exponential backoff (3 attempts, then fail)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Analyze Code Changes Before Testing (Priority: P1)

As a developer, when I make code changes, the system analyzes the git diff to identify what changed and what could break, so I know exactly what tests are needed.

**Why this priority**: Without impact analysis, tests are generated blindly without understanding the risk areas. This is the foundation of the entire feature.

**Independent Test**: Can be tested by providing a git diff and verifying the system identifies all change categories and potential break points.

**Acceptance Scenarios**:

1. **Given** a git diff containing modified business logic, **When** impact analysis runs, **Then** the system identifies the affected business rules and marks them for unit testing
2. **Given** a git diff containing modified controller code, **When** impact analysis runs, **Then** the system identifies affected endpoints, validation rules, and HTTP concerns
3. **Given** a git diff with database migration changes, **When** impact analysis runs, **Then** the system flags persistence layer impacts
4. **Given** a git diff with no changes, **When** impact analysis runs, **Then** the system reports no impacts requiring tests

---

### User Story 2 - Generate Appropriate Test Type (Priority: P1)

As a developer, I want the system to automatically select the right test type based on the change category, following the test pyramid principle.

**Why this priority**: Generating the wrong test type wastes resources. The test pyramid ensures efficient testing.

**Independent Test**: Can be tested by providing different change types and verifying the correct test type is selected.

**Acceptance Scenarios**:

1. **Given** a business rule modification, **When** test type is selected, **Then** unit tests are generated
2. **Given** a controller/endpoint modification, **When** test type is selected, **Then** controller-level tests are generated
3. **Given** a repository/query modification, **When** test type is selected, **Then** data layer tests are generated
4. **Given** an inter-service API modification, **When** test type is selected, **Then** contract tests are generated

---

### User Story 3 - Generate Required Test Cases (Priority: P1)

As a developer, I want comprehensive test cases including nominal cases, edge cases, and regression-prevention tests for each identified impact.

**Why this priority**: Incomplete test coverage leads to regressions. Every impact must be covered by at least one test.

**Independent Test**: Can be tested by providing an impact and verifying all required test cases are generated.

**Acceptance Scenarios**:

1. **Given** an identified impact, **When** tests are generated, **Then** at least 1 nominal case test is created
2. **Given** an identified impact, **When** tests are generated, **Then** 1-2 edge case tests are created
3. **Given** a bug fix is detected, **When** tests are generated, **Then** a regression test is created
4. **Given** a critical business rule change, **When** tests are generated, **Then** invariant tests are created

---

### User Story 4 - Risk Classification (Priority: P2)

As a developer, I want impacts classified by risk level so I can prioritize testing efforts appropriately.

**Why this priority**: Not all changes carry equal risk. Classification helps focus effort on what matters most.

**Independent Test**: Can be tested by providing various changes and verifying correct risk classification.

**Acceptance Scenarios**:

1. **Given** a change to payment/financial logic, **When** risk is assessed, **Then** it is classified as business-critical
2. **Given** a change to authentication/authorization, **When** risk is assessed, **Then** it is classified as business-critical
3. **Given** a change to logging or formatting, **When** risk is assessed, **Then** it is classified as non-critical

---

### User Story 5 - Enforce Test Coverage in CI (Priority: P2)

As a team lead, I want the CI pipeline to block merges when impact tests are missing or failing.

**Why this priority**: Without enforcement, developers may skip testing. CI gates ensure consistent quality.

**Independent Test**: Can be tested by attempting merges with various coverage states.

**Acceptance Scenarios**:

1. **Given** a pull request with failing tests, **When** merge is attempted, **Then** the merge is blocked
2. **Given** a pull request with new uncovered code, **When** merge is attempted, **Then** the merge is blocked
3. **Given** a pull request with all impacts tested, **When** merge is attempted, **Then** the merge is allowed

---

### Edge Cases

- File renamed but content unchanged - No tests required for pure renames
- Changes to test files themselves - Test file changes do not require additional tests
- Change affects multiple layers - Generate tests for each affected layer
- Third-party library updates - Flag for manual review, suggest integration test
- Legacy code with no existing tests - Suggest characterization tests before modification
- Large diffs exceeding 500 lines - Chunk into batches of 500 lines, process sequentially with progress feedback
- LLM API failure - Retry with exponential backoff (3 attempts), then fail with clear error message

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST analyze git diff of uncommitted changes (working directory vs HEAD) to identify all code changes before test generation
- **FR-002**: System MUST categorize changes into: business rules, endpoints, DTOs, queries, migrations, API contracts, configuration
- **FR-003**: System MUST identify potential break points: inputs, outputs, persistence, cross-cutting concerns
- **FR-004**: System MUST classify each impact as business-critical or non-critical
- **FR-005**: System MUST select the lowest appropriate test level from the test pyramid
- **FR-006**: System MUST generate at minimum: 1 nominal case + 1-2 edge cases per impact
- **FR-007**: System MUST generate regression tests for bug fixes
- **FR-008**: System MUST generate invariant tests for critical business rules
- **FR-009**: System MUST produce an impact report in JSON format linking changes to tests (machine-parseable for CI integration)
- **FR-010**: System MUST support CI integration to block merges when tests are missing
- **FR-011**: System MUST chunk diffs exceeding 500 lines into batches and process sequentially with progress feedback
- **FR-012**: System MUST retry LLM API failures with exponential backoff (3 attempts maximum) before failing with clear error message

### Key Entities

- **Impact**: Code change and its effects (type, risk level, affected components, required test type)
- **TestRequirement**: Test to be generated (type, scenarios, priority)
- **ImpactReport**: Links changes to tests with coverage status and risk assessment
- **ChangeCategory**: Classification of change type (business rule, endpoint, query, etc.)

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of identified impacts have at least one corresponding test generated
- **SC-002**: Regression rate decreases by 50% compared to baseline
- **SC-003**: Developers can review impact analysis in under 5 minutes
- **SC-004**: 95% of generated tests correctly match the appropriate test level
- **SC-005**: CI blocks 100% of merges with uncovered new code or failing tests
- **SC-006**: Impact analysis and test generation under 2 minutes for changes under 500 lines
- **SC-007**: False positive rate stays below 5%
- **SC-008**: Developer satisfaction with test quality improves by 40%

## Assumptions

- Developers are working with git-based repositories
- The codebase follows standard patterns (services, controllers, repositories)
- Test frameworks are already configured in the target project
- CI/CD pipeline exists and can be extended with custom gates
- Developers review generated tests before committing

## Out of Scope

- Manual test case writing
- Performance/load testing generation
- UI/visual testing
- Cross-browser testing
- Security penetration testing

