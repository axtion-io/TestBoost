# TestBoost Documentation

Welcome to the TestBoost documentation. This guide will help you get started with TestBoost and explore its features.

## Quick Links

- [User Guide](./user-guide.md) - Complete guide for using TestBoost
- [CLI Reference](./cli-reference.md) - Command-line interface documentation
- [API Authentication](./api-authentication.md) - API authentication and endpoints

---

## Table of Contents

### Getting Started

| Document | Description |
|----------|-------------|
| [User Guide](./user-guide.md) | Complete step-by-step guide for installation and usage |
| [CLI Reference](./cli-reference.md) | Full CLI commands reference with examples |
| [LLM Providers](./llm-providers.md) | Configure Google Gemini, Claude, or OpenAI |

### API & Architecture

| Document | Description |
|----------|-------------|
| [API Authentication](./api-authentication.md) | X-API-Key authentication, endpoints, rate limiting |
| [API Errors](./api-errors.md) | Error codes, responses, and retry strategies |
| [Database Schema](./database-schema.md) | PostgreSQL tables, relationships, migrations |
| [MCP Tools Reference](./mcp-tools-reference.md) | Model Context Protocol tools for agents |
| [Workflow Diagrams](./workflow-diagrams.md) | State machine diagrams for all workflows |

### Testing

| Document | Description |
|----------|-------------|
| [Testing Strategy](./testing-strategy.md) | Baseline tests, flaky test handling, coverage |
| [Test Generation](./test-generation.md) | Test quality scoring, mock generation, snapshots |
| [testing/manual-test-checklist.md](./testing/manual-test-checklist.md) | Manual testing checklist |
| [testing/smoke-test-protocol.md](./testing/smoke-test-protocol.md) | Smoke test procedures |
| [testing/test-scenarios.md](./testing/test-scenarios.md) | Test scenario catalog |

### Operations & Deployment

| Document | Description |
|----------|-------------|
| [Operations Guide](./operations.md) | Performance thresholds, load testing, incident response |
| [Docker Isolation](./docker-isolation.md) | Container resource limits, cleanup policies, security |
| [Monitoring Setup](./monitoring-setup.md) | Prometheus + Grafana configuration guide |
| [Dependencies](./dependencies.md) | External service dependencies and fallback strategies |

### Reference

| Document | Description |
|----------|-------------|
| [Traceability Matrix](./traceability.md) | FR-to-Constitution principles mapping |
| [Maven Maintenance](./maven-maintenance.md) | Maven dependency update workflow details |
| [Logging Gaps Analysis](./logging-gaps-analysis.md) | Logging coverage analysis |

---

## Documentation Structure

```
docs/
├── README.md                    # This file - Table of contents
├── user-guide.md                # Getting started guide
├── cli-reference.md             # CLI commands
├── api-authentication.md        # API auth & endpoints
├── api-errors.md                # Error reference
├── database-schema.md           # Database tables
├── llm-providers.md             # LLM configuration
├── mcp-tools-reference.md       # MCP tools
├── workflow-diagrams.md         # Workflow state machines
├── testing-strategy.md          # Testing approach
├── test-generation.md           # Test generation details
├── operations.md                # Production operations
├── docker-isolation.md          # Docker security
├── monitoring-setup.md          # Monitoring stack
├── dependencies.md              # External dependencies
├── traceability.md              # Requirements traceability
└── testing/                     # Testing subdocs
    ├── manual-test-checklist.md
    ├── smoke-test-protocol.md
    └── test-scenarios.md
```

---

## Related Resources

- **Specifications**: See `specs/` directory for feature specifications
- **Configuration**: See `config/` for agent YAML configurations
- **GitHub Actions**: See `.github/README.md` for CI/CD documentation

## Contributing to Documentation

1. Keep documentation in sync with code changes
2. Use consistent formatting (Markdown, tables)
3. Include code examples where helpful
4. Update this README when adding new docs
