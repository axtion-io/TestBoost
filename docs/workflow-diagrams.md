# Workflow Diagrams

**Purpose**: Visual representation of TestBoost workflow state transitions
**Version**: 1.0.0

---

## Maven Maintenance Workflow

```mermaid
stateDiagram-v2
    [*] --> Pending: Session Created

    Pending --> Analysis: Start Session

    Analysis --> Planning: Analysis Complete
    Analysis --> Failed: Analysis Failed

    Planning --> Executing: Plan Approved
    Planning --> Cancelled: User Cancelled

    Executing --> Validating: Changes Applied
    Executing --> RollingBack: Execution Failed

    Validating --> Completed: Tests Pass
    Validating --> RollingBack: Tests Fail

    RollingBack --> Failed: Rollback Complete

    Completed --> [*]
    Failed --> [*]
    Cancelled --> [*]
```

### State Descriptions

| State | Description | Exit Criteria |
|-------|-------------|---------------|
| Pending | Session created, awaiting start | User triggers start |
| Analysis | Analyzing project structure and dependencies | Analysis completes or fails |
| Planning | Generating maintenance plan | User approves or rejects |
| Executing | Applying changes (pom updates, code changes) | All changes applied or error |
| Validating | Running tests to validate changes | Tests pass or fail |
| RollingBack | Reverting changes on failure | Rollback completes |
| Completed | Workflow finished successfully | - |
| Failed | Workflow failed with error | - |
| Cancelled | User cancelled workflow | - |

### Transition Conditions

| From | To | Condition |
|------|-----|-----------|
| Analysis | Planning | All dependencies analyzed, no blocking issues |
| Analysis | Failed | Cannot parse pom.xml, invalid project structure |
| Planning | Executing | User approves plan (interactive) or auto-approve (autonomous) |
| Planning | Cancelled | User explicitly cancels |
| Executing | Validating | All planned changes successfully applied |
| Executing | RollingBack | Any change fails to apply |
| Validating | Completed | `mvn test` passes |
| Validating | RollingBack | Tests fail after max 3 retry attempts |

---

## Test Generation Workflow

```mermaid
stateDiagram-v2
    [*] --> Pending: Session Created

    Pending --> ClassAnalysis: Start Generation

    ClassAnalysis --> TestPlanning: Classes Analyzed
    ClassAnalysis --> Failed: Analysis Failed

    TestPlanning --> UnitGeneration: Plan Created

    UnitGeneration --> IntegrationGeneration: Unit Tests Done
    UnitGeneration --> Validation: Skip Integration

    IntegrationGeneration --> Validation: Integration Tests Done

    Validation --> MutationAnalysis: Initial Validation Pass
    Validation --> Fixing: Tests Fail

    Fixing --> Validation: Fixes Applied
    Fixing --> Failed: Max Retries Exceeded

    MutationAnalysis --> Completed: Coverage Sufficient
    MutationAnalysis --> KillerGeneration: Need More Coverage

    KillerGeneration --> Validation: Killer Tests Generated

    Completed --> [*]
    Failed --> [*]
```

### State Descriptions

| State | Description | Exit Criteria |
|-------|-------------|---------------|
| Pending | Session created | Start triggered |
| ClassAnalysis | Analyzing target class complexity | Analysis complete |
| TestPlanning | Planning test strategy based on analysis | Plan generated |
| UnitGeneration | Generating unit tests | Tests written |
| IntegrationGeneration | Generating integration tests | Tests written |
| Validation | Running generated tests | Tests pass/fail |
| Fixing | Auto-correcting failed tests | Fixed or max retries |
| MutationAnalysis | Running PIT mutation analysis | Coverage calculated |
| KillerGeneration | Generating killer tests for surviving mutants | Tests generated |
| Completed | All tests generated and passing | - |
| Failed | Generation failed | - |

### Decision Points

1. **Skip Integration Tests**: When class has no external dependencies
2. **Need More Coverage**: Mutation score < 80% threshold
3. **Max Retries Exceeded**: 3 consecutive fix attempts failed

---

## Docker Deployment Workflow

```mermaid
stateDiagram-v2
    [*] --> Pending: Session Created

    Pending --> ImageBuild: Start Deployment

    ImageBuild --> ContainerCreate: Image Built
    ImageBuild --> Failed: Build Failed

    ContainerCreate --> HealthCheck: Containers Started
    ContainerCreate --> Cleanup: Start Failed

    HealthCheck --> Completed: All Healthy
    HealthCheck --> Retry: Health Check Failed

    Retry --> HealthCheck: Retry Attempt
    Retry --> Cleanup: Max Retries Exceeded

    Cleanup --> Failed: Cleanup Complete

    Completed --> [*]
    Failed --> [*]
```

### State Descriptions

| State | Description | Exit Criteria |
|-------|-------------|---------------|
| Pending | Session created | Start triggered |
| ImageBuild | Building Docker images | Images built successfully |
| ContainerCreate | Starting containers via docker-compose | Containers running |
| HealthCheck | Checking container health endpoints | Health passes |
| Retry | Waiting before retry | Timer expires |
| Cleanup | Stopping and removing failed containers | Containers removed |
| Completed | All containers healthy | - |
| Failed | Deployment failed | - |

### Retry Policy

- **Max retries**: 3 attempts
- **Backoff**: Exponential (1s, 2s, 4s)
- **Health check interval**: 5s
- **Health check timeout**: 30s per container

---

## Common Patterns

### Rollback Strategy

All workflows that modify files implement rollback:

```mermaid
flowchart LR
    A[Backup Files] --> B[Apply Changes]
    B --> C{Validation}
    C -->|Pass| D[Delete Backup]
    C -->|Fail| E[Restore from Backup]
    E --> F[Report Failure]
```

### Auto-Correction Loop

For test generation and maintenance:

```mermaid
flowchart LR
    A[Generate/Apply] --> B[Validate]
    B --> C{Pass?}
    C -->|Yes| D[Complete]
    C -->|No| E{Retries < 3?}
    E -->|Yes| F[Analyze Error]
    F --> G[Apply Fix]
    G --> B
    E -->|No| H[Fail]
```

---

## Session Lifecycle

```mermaid
sequenceDiagram
    participant U as User
    participant API as TestBoost API
    participant DB as Database
    participant Agent as LLM Agent
    participant MCP as MCP Tools

    U->>API: Create Session
    API->>DB: Insert Session (pending)
    API-->>U: Session ID

    U->>API: Start Session
    API->>Agent: Execute Workflow

    loop For Each Step
        Agent->>MCP: Call Tool
        MCP-->>Agent: Tool Result
        Agent->>DB: Update Step Status
    end

    Agent->>DB: Update Session (completed/failed)
    API-->>U: Session Result
```
