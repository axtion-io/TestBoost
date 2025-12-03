# Feature Specification: DeepAgents LLM Integration

**Feature Branch**: `002-deepagents-integration`
**Created**: 2025-11-28
**Status**: Draft
**Input**: User description: "Integrate DeepAgents LLM framework into TestBoost workflows to enable real AI agent reasoning and decision-making, replacing current deterministic workflow logic with LLM-powered agents that use MCP tools, YAML configurations, and Markdown prompts."

## User Scenarios & Testing

### User Story 1 - Application Startup Validation (Priority: P1)

As a TestBoost user, when I start the application (API or CLI), the system must verify that configured LLM providers are accessible before accepting any commands, ensuring I never experience silent failures or simulated results.

**Why this priority**: This is the most critical fix to respect the "Zéro Complaisance" constitutional principle. Currently, TestBoost runs workflows without any LLM calls, giving the false impression that AI agents are working when they're not.

**Independent Test**: Can be fully tested by starting the application with invalid/missing LLM API keys and verifying it fails immediately with clear error messages.

**Acceptance Scenarios**:

1. **Given** GOOGLE_API_KEY is not configured, **When** I start the API server, **Then** it fails with error "LLM not available: GOOGLE_API_KEY not configured"
2. **Given** GOOGLE_API_KEY is invalid, **When** I run a CLI command, **Then** it exits with error "LLM connection failed: 403 Forbidden"
3. **Given** valid API key, **When** I start the application, **Then** startup logs show "llm_connection_ok" with model name

---

### User Story 2 - Maven Maintenance with Real LLM Agent (Priority: P2)

As a developer, when I run Maven dependency maintenance, I want an LLM agent to analyze my project's dependencies and reason about update priorities based on security risks and breaking changes.

**Why this priority**: This demonstrates the first complete end-to-end workflow with real LLM agent value. Maven maintenance is simpler than test generation, making it ideal for validating the DeepAgents integration pattern.

**Independent Test**: Can be fully tested by running maintenance on a Java project and verifying LangSmith traces show actual LLM invocations with tool calls.

**Acceptance Scenarios**:

1. **Given** a Java project with outdated dependencies, **When** I run maintenance, **Then** the LLM agent calls analyze-dependencies MCP tool and provides prioritized update strategy
2. **Given** updates include breaking changes, **When** agent analyzes, **Then** response includes risk assessment from dependency_update.md prompt
3. **Given** LangSmith tracing enabled, **When** workflow runs, **Then** dashboard shows agent invocations and tool calls
4. **Given** security vulnerabilities exist, **When** agent analyzes, **Then** vulnerable dependencies are prioritized as "HIGH"

---

### User Story 3 - Agent Configuration Management (Priority: P3)

As a TestBoost administrator, I want to configure agent behavior through YAML files and Markdown templates without modifying Python code.

**Why this priority**: Enables non-developers to tune agent behavior. Lower priority because YAML configs exist and just need connection.

**Independent Test**: Can be tested by modifying maven_maintenance_agent.yaml temperature and verifying changes take effect.

**Acceptance Scenarios**:

1. **Given** I update YAML temperature, **When** workflow runs, **Then** LLM uses new temperature
2. **Given** I modify prompt template, **When** agent runs, **Then** it follows new validation rules
3. **Given** I add new MCP tool, **When** agent loads, **Then** tool is bound and available
4. **Given** YAML has error, **When** app starts, **Then** it fails with clear error message

---

### User Story 4 - Test Generation with Real LLM Agent (Priority: P2)

As a developer, when I run test generation, I want an LLM agent to analyze my Java code and generate contextually appropriate tests based on class type and existing patterns.

**Why this priority**: Same priority as Maven maintenance (P2) - both are core workflows that need agent reasoning. Test generation requires AI to understand code context, not just template filling.

**Independent Test**: Run test generation on Java project and verify LangSmith traces show ≥3 real LLM API calls with analysis tool invocations.

**Acceptance Scenarios**:

1. **Given** a Java/Spring Boot project, **When** I run test generation, **Then** the LLM agent calls analyze-project MCP tool and classifies classes (Controller, Service, Repository)
2. **Given** classes classified, **When** agent generates tests, **Then** it follows existing project conventions (imports, assertions, mocking patterns)
3. **Given** tests generated with compilation errors, **When** agent detects errors, **Then** it retries with auto-correction (max 3 attempts) using LLM reasoning
4. **Given** LangSmith tracing enabled, **When** workflow runs, **Then** dashboard shows agent invocations analyzing class structure and test patterns

---

### User Story 5 - Docker Deployment with Real LLM Agent (Priority: P2)

As a developer, when I deploy my application to Docker, I want an LLM agent to analyze my project type and generate optimal Dockerfile and docker-compose configuration.

**Why this priority**: Same priority as Maven and test generation (P2) - deployment workflow requires AI to detect project type and dependencies, not hardcoded templates.

**Independent Test**: Run Docker deployment on Java project and verify LangSmith traces show ≥3 real LLM API calls with project analysis tool invocations.

**Acceptance Scenarios**:

1. **Given** a packaged Java project, **When** I run deployment, **Then** the LLM agent calls detect-project-type MCP tool and identifies JAR/WAR/JSP type
2. **Given** project type detected, **When** agent generates Dockerfile, **Then** it includes detected dependencies (PostgreSQL, Redis) via docker-compose
3. **Given** containers starting, **When** agent monitors health, **Then** it waits for health check OK before declaring success
4. **Given** LangSmith tracing enabled, **When** workflow runs, **Then** dashboard shows agent invocations analyzing project structure and dependencies

---

### Edge Cases

- **LLM API rate limits exceeded**: Workflow MUST abort immediately with explicit error message: "LLM rate limit exceeded by {provider_name}. Retry after {seconds} seconds. Workflow aborted. Zero results generated." No silent degradation, no vague "failed" messages (respects "Zéro Complaisance" - principle of zero tolerance for misleading outputs).
- **LLM doesn't call expected MCP tools**: Agent invocation retries with modified prompt instructing tool use (max 3 attempts). If tools still not called, workflow fails with error listing expected vs actual tool calls.
- **YAML config changes during paused workflow**: OUT OF SCOPE for this feature. Workflow pause/resume functionality deferred to future work. Current implementation: workflows execute atomically without pause capability.
- **Intermittent LLM connectivity**: Agent invocations use retry logic with exponential backoff (3 attempts, 1s-10s wait). Network errors trigger automatic retry. Persistent failures abort workflow.
- **Malformed tool calls or invalid JSON**: Agent invocation validates JSON responses. JSONDecodeError or ToolCallError triggers retry (max 3 attempts). Malformed responses logged to artifacts. All retries exhausted → workflow fails.
- **Prompts exceeding context windows**: DeepAgents automatic summarization handles this (170k token threshold). No explicit validation needed. Token counts monitored in cost analysis.

## Requirements

### Functional Requirements

- **FR-001**: Application MUST verify LLM provider connectivity at startup before accepting commands
- **FR-002**: Application MUST fail immediately with clear errors if LLM provider is not accessible. Error messages MUST include: (1) root cause, (2) specific action required, (3) context (e.g., "LLM provider: google, API key: missing"). Format: "{Action failed}: {Root cause}. Action: {What user must do}."
- **FR-003**: Maven maintenance workflow MUST use create_deep_agent() to create LLM-powered agent nodes
- **FR-004**: Agent workflows MUST load configuration from config/agents/*.yaml files
- **FR-005**: Agent workflows MUST load system prompts from config/prompts/**/*.md templates
- **FR-006**: Agent nodes MUST invoke LLMs with MCP tools bound
- **FR-007**: Agent decisions MUST be logged to LangSmith when enabled
- **FR-008**: Agent responses MUST be stored in session artifacts table
- **FR-009**: Workflows MUST handle LLM errors with retry logic and graceful degradation
- **FR-010**: Application MUST NOT execute workflows if LLM connectivity check fails
- **FR-011**: CLI and API MUST log LLM metrics (duration, tokens, model)
- **FR-012**: Test generation and deployment workflows MUST follow same agent integration pattern
- **FR-013**: Application MUST support switching between Google Gemini/Anthropic Claude/OpenAI GPT-4o via environment variables: `LLM_PROVIDER=google|anthropic|openai` (default: google) and corresponding API key `GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY`. Switching requires only env var change and application restart (zero code changes).
- **FR-014**: Workflows MUST use existing MCP servers as tools for agents
- **FR-015**: Agent tool calls MUST be traced with input arguments and output results

### Key Entities

- **LLM Agent**: Configured AI agent with model, tools, prompts, execution context created from YAML config
- **Agent Configuration**: YAML definition with identity, LLM settings, tools, workflow reference, error handling
- **System Prompt**: Markdown file with structured prompts for agent behavior and response formats
- **Agent Session**: Workflow execution tracking agent invocations, tool calls, reasoning steps, artifacts
- **MCP Tool Binding**: Connection between agent and MCP tools allowing LLM tool discovery and invocation

## Success Criteria

### Measurable Outcomes

- **SC-001**: Application startup fails within 5 seconds if LLM provider not accessible
- **SC-002**: Every workflow (Maven, test generation, deployment) results in at least 3 LLM API calls
- **SC-003**: LLM agents use reasoning from Markdown prompts (verifiable in responses)
- **SC-004**: Switching LLM provider requires zero code changes
- **SC-005**: 100% of agent tool calls traced in LangSmith when enabled
- **SC-006**: YAML config changes take effect on next workflow execution
- **SC-007**: All three workflows (Maven maintenance, test generation, Docker deployment) use LLM agents
- **SC-008**: Zero workflows execute without LLM invocation
- **SC-009**: LLM metrics logged for every workflow execution
- **SC-010**: Agent failure rate under 5% with retry logic

## Scope

### In Scope

- LLM connectivity check at startup
- Refactoring all three workflows to use DeepAgents:
  - Maven dependency maintenance (P1 workflow)
  - Test generation (P1 workflow)
  - Docker deployment (P2 workflow)
- Loading agent configs from YAML files
- Loading prompts from Markdown templates
- Binding MCP tools to LLM agents
- LangSmith tracing integration
- Session artifact storage
- Retry logic for LLM errors and edge cases
- End-to-end tests with real LLM calls for all workflows

### Out of Scope

- Creating new MCP servers
- Modifying existing YAML configs
- Adding new LLM providers
- Database schema changes
- CLI/API UX changes
- LLM call performance optimization
- Cost optimization strategies
- Multi-agent orchestration
- New workflow types

## Assumptions

- DeepAgents 0.2.7 is installed and functional
- MCP servers expose LangChain-compatible tools
- config/agents/*.yaml files are structurally correct
- LangSmith is optional
- Users have valid API keys for at least one provider
- Workflows can be migrated incrementally
- StateGraph can coexist with agent nodes
- PostgreSQL handles agent artifact data
- MCP tool responses compatible with LLM tool calling

## Dependencies

- DeepAgents 0.2.7 (pinned - tested and validated with this version. Future work: test compatibility with 0.2.8+)
- Python 3.11+ (required by DeepAgents 0.2.7)
- LangChain Core 1.1+
- LangGraph 1.0+
- MCP 1.22+
- LangSmith (optional)
- Existing MCP servers (maven, git, docker, test-gen, etc.)
- Google Gemini, Anthropic Claude, or OpenAI API
- PostgreSQL 15+

## Open Questions

None. Feature scope is clear based on comprehensive architecture analysis completed in 001-testboost-core investigation.
