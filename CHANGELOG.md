# Changelog

All notable changes to TestBoost will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source documentation (CONTRIBUTING.md, LICENSE, CHANGELOG.md)
- GitHub issue and PR templates
- Enhanced code quality checks in CI

## [0.2.0] - 2025-01-15

### Added
- **DeepAgents Integration**: Full integration with DeepAgents 0.2.8 for AI-powered workflows
- **Configuration Management CLI**: New `config` command group with validate, show, backup, rollback, and reload commands
- **Hot-reload Configuration**: Agent configurations automatically reload on file changes via modification time tracking
- **7-Layer Validation**: Comprehensive config validation (YAML syntax, schema, MCP servers, prompts, LLM provider, parameters)
- **Backup/Rollback System**: Timestamped configuration backups with one-command rollback capability
- **Zero Complaisance Principle**: Workflows fail-fast with clear errors rather than degrading silently
- **LLM Startup Validation**: Application validates LLM connectivity on startup, fails within 5 seconds if not accessible
- **Rate Limit Handling**: Explicit rate limit error handling with retry guidance
- **Context Window Management**: Automatic input summarization for projects exceeding 170k tokens
- **Edge Case Handling**: Comprehensive handling for missing tool calls, malformed JSON, network errors

### Changed
- Upgraded to LangGraph 1.0 for workflow state machines
- Upgraded to LangChain Core 1.1.7+ for tool integration
- Improved error messages for LLM connection failures
- Enhanced CLI with ASCII-safe progress indicators for better Windows compatibility

### Fixed
- LangGraph recursion limit issues with automatic termination conditions
- Unicode encoding errors in CLI output
- Agent configuration changes not taking effect (hot-reload implementation)

## [0.1.0] - 2024-11-01

### Added
- **Core Platform**: Initial TestBoost platform for Java/Spring Boot test generation and maintenance
- **FastAPI Backend**: REST API with comprehensive endpoint coverage
  - Health check endpoints
  - Session management (create, read, update, delete, pause, resume)
  - Workflow step execution
  - Artifact management
- **CLI Tool**: Typer-based command-line interface with Rich terminal UI
  - `maintenance` commands for Maven dependency management
  - `tests` commands for test generation
  - `deploy` commands for Docker deployment
- **Database Schema**: PostgreSQL 15 with 8 core tables
  - `projects`: Maven project metadata
  - `sessions`: Workflow execution sessions
  - `steps`: Individual workflow steps
  - `events`: Session event log
  - `artifacts`: Build outputs and reports
  - `dependencies`: Maven dependency tracking
  - `modifications`: Code change tracking
  - `project_locks`: Concurrent execution prevention
- **Maven Maintenance Workflow**
  - Dependency analysis and update recommendations
  - Security vulnerability scanning
  - Automated test validation before updates
  - Git branch management for safe updates
- **Test Generation Workflow**
  - Unit tests with Mockito and JUnit 5
  - Integration tests for REST APIs, repositories, and services
  - Snapshot tests for data validation
  - Mutation testing with PIT for test quality assessment
  - Killer test generation for surviving mutants
- **Docker Deployment Workflow**
  - Automatic Dockerfile generation
  - Docker Compose orchestration
  - Multi-service deployment support
  - Health check integration
- **MCP Tool Servers**: Model Context Protocol servers for tool integration
  - `maven_maintenance` server
  - `container_runtime` server
- **Observability**
  - Structured JSON logging with structlog
  - LangSmith integration for workflow tracing
  - Session-based event tracking
- **LLM Provider Support**: Multiple provider options
  - Google Gemini (recommended)
  - Anthropic Claude
  - OpenAI GPT
- **Agent Configuration**: YAML-based agent behavior configuration
  - `maven_maintenance_agent.yaml`
  - `test_gen_agent.yaml`
  - `deployment_agent.yaml`
- **Prompt Templates**: Markdown-based prompt templates in `config/prompts/`

### Security
- API key authentication middleware
- Timing-safe comparison for API key validation
- No hardcoded secrets in codebase
- Environment variable configuration for all sensitive values

[Unreleased]: https://github.com/your-org/testboost/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/your-org/testboost/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/your-org/testboost/releases/tag/v0.1.0
