# Feature Specification: API Endpoints for File Modifications Tracking

**Feature Branch**: `006-file-modifications-api`
**Created**: 2026-01-10
**Status**: Clarified
**Input**: User description: "API Endpoints for File Modifications Tracking - Add artifact content download endpoint and file_modification artifact type for TestBoost-Web frontend"

## Clarifications

### Session 2026-01-10

- Q: Le nouvel endpoint content nécessite-t-il une authentification? → A: Même authentification que les autres endpoints session (API Key header)
- Q: Où stocker original_content et modified_content? → A: Dans la base de données (champ TEXT dans la table artifacts existante)
- Q: Stratégie pour fichiers >10MB? → A: Rejeter avec HTTP 413 (Payload Too Large) et message explicite
- Q: Cycle de vie des artifacts file_modification? → A: Immuables - ne peuvent être ni modifiés ni supprimés individuellement (suppression en cascade avec session uniquement)
- Q: Logging des accès pour traçabilité? → A: Logger tous les accès (session_id, artifact_id, user, timestamp) sans le contenu

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Download Artifact Content (Priority: P1)

As a frontend developer using TestBoost-Web, I want to download the actual content of an artifact so that I can display file contents to users reviewing workflow results.

**Why this priority**: Core functionality needed for the frontend to display any file content. Without this, users cannot see what TestBoost actually modified.

**Independent Test**: Can be fully tested by creating a session with artifacts, then calling the download endpoint and verifying the raw content is returned with correct Content-Type.

**Acceptance Scenarios**:

1. **Given** a session with a text artifact (Java file), **When** I request the artifact content via `GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content`, **Then** I receive the raw file content with `Content-Type: text/x-java`
2. **Given** a session with an XML artifact (pom.xml), **When** I request the artifact content, **Then** I receive the raw XML content with `Content-Type: application/xml`
3. **Given** an artifact ID that does not exist, **When** I request the artifact content, **Then** I receive a 404 error with a clear message
4. **Given** an artifact with binary content marked as non-downloadable, **When** I request the artifact content as text, **Then** I receive a 400 error explaining the artifact cannot be downloaded as text

---

### User Story 2 - Track File Modifications (Priority: P1)

As a TestBoost user, I want to see all file modifications made during a workflow so that I can review changes before applying them to my codebase.

**Why this priority**: Essential for transparency - users must understand what TestBoost changed. This aligns with the "Traçabilité Complète" constitution principle.

**Independent Test**: Can be fully tested by running a workflow that modifies files, then querying artifacts filtered by `file_modification` type and verifying all changes are captured with original content, modified content, and diff.

**Acceptance Scenarios**:

1. **Given** a Maven maintenance workflow that updates pom.xml, **When** the workflow completes, **Then** a `file_modification` artifact is created with file_path, operation, original_content, modified_content, and diff
2. **Given** a test generation workflow that creates new test files, **When** the workflow completes, **Then** a `file_modification` artifact is created with operation "create" and modified_content (original_content is null for new files)
3. **Given** a workflow that deletes a file, **When** the workflow completes, **Then** a `file_modification` artifact is created with operation "delete" and original_content (modified_content is null for deletions)

---

### User Story 3 - View File Diff in Frontend (Priority: P2)

As a frontend user, I want to see a visual diff of file changes so that I can quickly understand what was modified without comparing full file contents.

**Why this priority**: Improves user experience by providing quick visual feedback on changes, but core functionality (Stories 1 & 2) must work first.

**Independent Test**: Can be tested by retrieving a `file_modification` artifact and verifying the diff field contains valid unified diff format that can be rendered by a diff viewer.

**Acceptance Scenarios**:

1. **Given** a `file_modification` artifact with modified content, **When** I retrieve the artifact, **Then** the diff field contains a valid unified diff format showing line changes
2. **Given** a new file creation, **When** I retrieve the artifact, **Then** the diff shows all lines as additions
3. **Given** a file deletion, **When** I retrieve the artifact, **Then** the diff shows all lines as deletions

---

### Edge Cases

- What happens when an artifact file is very large (>10MB)?
  - System returns HTTP 413 (Payload Too Large) with a clear error message indicating the file exceeds the 10MB limit
- How does system handle binary files (images, compiled classes)?
  - Returns 400 error with message indicating binary files cannot be downloaded as text
- What if the session is deleted while artifact download is in progress?
  - Returns 404 with appropriate error message
- What if original_content is unavailable (file was created, not modified)?
  - original_content field is null, operation is "create"
- What if diff generation fails for very large files?
  - Store a truncated diff with a flag indicating it was truncated

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an endpoint `GET /api/v2/sessions/{session_id}/artifacts/{artifact_id}/content` that returns raw artifact content
- **FR-002**: System MUST return appropriate Content-Type headers based on the artifact's content_type field (text/x-java, application/xml, application/json, text/plain, etc.)
- **FR-003**: System MUST return HTTP 404 when the requested artifact or session does not exist
- **FR-004**: System MUST return HTTP 400 when attempting to download binary artifacts as text
- **FR-005**: System MUST support a new artifact type `file_modification` for tracking file changes
- **FR-006**: System MUST capture original_content for modified and deleted files (null for new files)
- **FR-007**: System MUST capture modified_content for modified and created files (null for deleted files)
- **FR-008**: System MUST generate unified diff format for the diff field
- **FR-009**: System MUST record the file_path relative to project root
- **FR-010**: System MUST record the operation type: "create", "modify", or "delete"
- **FR-011**: System MUST create `file_modification` artifacts automatically during Maven maintenance workflows
- **FR-012**: System MUST create `file_modification` artifacts automatically during test generation workflows
- **FR-013**: System MUST validate session_id and artifact_id are valid UUIDs before processing
- **FR-014**: System MUST require the same API Key authentication as other `/api/v2/sessions/*` endpoints for the content download endpoint
- **FR-015**: System MUST return HTTP 413 (Payload Too Large) when artifact content exceeds 10MB, with a clear error message
- **FR-016**: System MUST treat file_modification artifacts as immutable - no update or individual delete operations allowed (cascade delete with session only)
- **FR-017**: System MUST log all artifact content download requests with session_id, artifact_id, authenticated user, and timestamp (content excluded for performance)

### Key Entities

- **Artifact**: Extended to include new artifact_type "file_modification" with specific metadata structure. File modification artifacts are immutable once created (aligned with "Traçabilité Complète" principle).
- **FileModification Metadata**: Contains file_path (string), operation (enum: create/modify/delete), original_content (nullable string), modified_content (nullable string), diff (string in unified format)
- **Session**: Parent entity containing artifacts. When a session is deleted, all its file_modification artifacts are deleted in cascade.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Frontend can successfully display artifact content for 100% of text-based artifacts
- **SC-002**: All file modifications made by TestBoost workflows are captured and visible to users within 5 seconds of workflow completion
- **SC-003**: Users can view file diffs for any modification made by TestBoost
- **SC-004**: Content download completes in under 2 seconds for files up to 1MB
- **SC-005**: Zero file modifications are lost or untracked during any workflow execution
- **SC-006**: Users report understanding what TestBoost changed in 90% of cases (via diff visualization)

## Assumptions

- Artifact content (original_content, modified_content) is stored as TEXT fields in the database within the existing artifacts table metadata
- Content-Type mapping from file extensions is already available or can be derived from the artifact's content_type field
- The unified diff format is sufficient for frontend diff visualization (no need for side-by-side diff data structure)
- File modifications under 10MB are the primary use case; larger files may have truncated diffs
- All workflows that modify files will be updated to create file_modification artifacts (Maven maintenance, test generation)

## Out of Scope

- Binary file diff visualization
- File content editing through the API
- Real-time streaming of file modifications during workflow execution
- Version control integration (git commit of changes)
- Batch download of multiple artifacts
