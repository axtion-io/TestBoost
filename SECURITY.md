# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

**DO NOT report security vulnerabilities through public GitHub issues.**

### How to Report

**Email**: security@testboost.dev

**Subject**: [SECURITY] Brief description of the vulnerability

### What to Include

1. **Description**: A clear description of the vulnerability
2. **Steps to Reproduce**: Detailed steps to reproduce the issue
3. **Impact Assessment**: Potential impact (data exposure, privilege escalation, etc.)
4. **Affected Components**: Which parts of TestBoost are affected (CLI, test generation, session files, etc.)
5. **Suggested Fix** (optional): How to fix it
6. **Proof of Concept** (optional): Code or steps demonstrating the vulnerability

### What to Expect

- **48-hour acknowledgment**: We will acknowledge your report within 48 hours
- **5-day updates**: Status updates at least every 5 days
- **Coordinated disclosure**: We request reasonable time to fix before public disclosure
- **Credit**: We will acknowledge your contribution (unless you prefer anonymity)

## Security Best Practices for Users

### API Keys

TestBoost requires API keys for LLM providers (Google Gemini, Anthropic, OpenAI):

- **Never hardcode** API keys in source code or configuration files
- **Never commit** `.env` files with real credentials
- **Rotate keys regularly**, especially after team member changes
- **Use separate keys** for development and production
- **Restrict key permissions** to minimum required scope

### Environment Variables

- Use `.env` files for local development (already in `.gitignore`)
- Use `.env.example` as a template (placeholder values only)
- For production, use secrets management (AWS Secrets Manager, Azure Key Vault, etc.)

### Session Files

The `.testboost/` directory in your Java project contains session data including source code analysis. Consider:

- Adding `.testboost/` to `.gitignore` if sessions contain sensitive information
- Reviewing generated test files before committing (they may reference internal APIs or data structures)

## Security Features

### Secret Scanning

- **TruffleHog** -- Detects secrets in commits
- **Gitleaks** -- Comprehensive secret pattern detection
- **GitHub Actions CI** -- Runs scans on every PR and push

### Dependency Scanning

- License compliance checks (no GPL/AGPL dependencies, incompatible with Apache 2.0)
- GitHub Dependabot alerts for known vulnerabilities

### Code Quality

- **Ruff** -- Linting with security-focused rules
- **mypy** -- Static type checking
- **pytest** -- Comprehensive test suite

## Responsible Disclosure

We commit to:

1. **No legal action** against researchers who report in good faith
2. **Acknowledge contributions** in security advisories
3. **Work collaboratively** to understand and fix issues

## Contact

- **Security issues**: security@testboost.dev
- **General questions**: [GitHub Issues](https://github.com/axtion-io/TestBoost/issues) or [Discussions](https://github.com/axtion-io/TestBoost/discussions)
