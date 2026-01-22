---
name: Bug Report
about: Report a bug to help us improve TestBoost
title: '[BUG] '
labels: bug
assignees: ''
---

## Bug Description

A clear and concise description of what the bug is.

## Environment

- **OS**: [e.g., Windows 11, Ubuntu 22.04, macOS 14]
- **Python Version**: [e.g., 3.11.5]
- **TestBoost Version**: [e.g., 1.0.0]
- **PostgreSQL Version**: [e.g., 15.x]
- **Installation Method**: [e.g., Poetry, pip]

## Steps to Reproduce

1. Go to '...'
2. Run command '...'
3. See error

## Expected Behavior

A clear and concise description of what you expected to happen.

## Actual Behavior

A clear and concise description of what actually happened.

## Error Output / Logs

```
Paste any relevant error messages or logs here
```

## Configuration

If applicable, share relevant configuration (remove any sensitive data like API keys):

```yaml
# Relevant agent config or .env settings (redact secrets!)
```

## Component Affected

Please check which component(s) are affected:

- [ ] API Server (`src/api/`)
- [ ] CLI (`src/cli/`)
- [ ] LangGraph Workflows (`src/core/langgraph/`)
- [ ] DeepAgents Integration (`src/core/agents/`)
- [ ] Database / Models (`src/db/`)
- [ ] MCP Server
- [ ] Documentation
- [ ] CI/CD / GitHub Actions
- [ ] Other: ___

## LLM Provider (if applicable)

- [ ] Google Gemini
- [ ] Anthropic Claude
- [ ] OpenAI
- [ ] Not LLM-related

## Additional Context

Add any other context about the problem here, such as:
- Screenshots
- Related issues
- Possible causes you've identified
- Attempted workarounds

## Checklist

Before submitting, please confirm:

- [ ] I have searched existing issues to ensure this bug hasn't been reported
- [ ] I have removed any sensitive data (API keys, passwords) from this report
- [ ] I have included relevant error logs and configuration
- [ ] I am using a supported Python version (3.11+)
