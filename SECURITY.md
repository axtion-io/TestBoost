# Security Policy

## Supported Versions

We release patches for security vulnerabilities in the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2   | :x:                |

## Reporting a Vulnerability

**DO NOT report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities privately to our security team.

### How to Report

**Email**: security@testboost.dev

**Subject**: [SECURITY] Brief description of the vulnerability

### What to Include in Your Report

To help us assess and address the vulnerability quickly, please include:

1. **Description**: A clear description of the vulnerability
2. **Steps to Reproduce**: Detailed steps to reproduce the issue
3. **Impact Assessment**: Your assessment of the potential impact (data exposure, privilege escalation, etc.)
4. **Affected Components**: Which parts of TestBoost are affected (API, CLI, workflows, etc.)
5. **Suggested Fix** (optional): If you have suggestions for how to fix it
6. **Proof of Concept** (optional): Code or steps demonstrating the vulnerability

### What to Expect

- **48-hour acknowledgment**: We will acknowledge receipt of your report within 48 hours
- **5-day updates**: We will provide status updates at least every 5 days
- **Coordinated disclosure**: We request that you give us reasonable time to fix the vulnerability before public disclosure
- **Credit**: With your permission, we will acknowledge your contribution in our security advisories

### Our Commitment

- We will keep you informed about the progress of fixing the vulnerability
- We will notify you when the vulnerability is fixed
- We will credit you in our security advisory (unless you prefer to remain anonymous)

## Security Best Practices for Users

### Environment Variables

Never commit sensitive data to the repository:
- Use `.env` files for local development (already in `.gitignore`)
- Use `.env.example` as a template (safe placeholder values only)
- For production, use environment-specific secrets management (AWS Secrets Manager, Azure Key Vault, etc.)

### API Keys and Credentials

TestBoost requires API keys for LLM providers (Google Gemini, Anthropic, OpenAI):
- **Never hardcode** API keys in source code or configuration files
- **Never commit** `.env` files with real credentials
- **Rotate keys regularly** especially after team member changes
- **Use separate keys** for development, staging, and production environments
- **Restrict key permissions** to minimum required scope

### Database Security

For PostgreSQL:
- Use **strong passwords** (minimum 16 characters, mixed case, numbers, symbols)
- **Never use default credentials** (testboost/testboost from examples)
- **Restrict network access** to trusted IPs only
- **Enable SSL/TLS** for database connections in production
- **Regular backups** with encrypted storage

### Docker and Container Security

- **Keep base images updated** to latest patch versions
- **Scan images** for vulnerabilities before deployment
- **Run containers as non-root** user when possible
- **Limit container resources** (CPU, memory) to prevent DoS
- **Use secrets management** for container environment variables

### Network Security

- **Use HTTPS** for all production API endpoints
- **Enable CORS** carefully - restrict to trusted origins only
- **Rate limiting** on API endpoints to prevent abuse
- **Authentication/Authorization** for all non-public endpoints

## Security Features in TestBoost

### Secret Scanning

This repository uses automated secret scanning to prevent accidental credential commits:
- **TruffleHog** - Detects and verifies secrets in commits
- **Gitleaks** - Comprehensive secret pattern detection
- **GitHub Actions CI** - Runs scans on every PR and push

If the CI detects secrets, your PR will be blocked until the issue is resolved.

### Dependency Scanning

We monitor dependencies for known vulnerabilities:
- **License compliance** - Automated checks for GPL/AGPL dependencies (incompatible with Apache 2.0)
- **Security advisories** - GitHub Dependabot alerts for vulnerable dependencies

### Code Quality Checks

- **Ruff** - Python linter with security-focused rules
- **mypy** - Static type checking to catch potential bugs
- **pytest** - Comprehensive test suite with security-focused tests

## Responsible Disclosure Policy

We believe in responsible disclosure and appreciate security researchers who report vulnerabilities responsibly. We commit to:

1. **No legal action** against security researchers who:
   - Report vulnerabilities privately and in good faith
   - Give us reasonable time to fix before public disclosure
   - Do not exploit vulnerabilities for personal gain or harm users

2. **Acknowledge contributions** in our security advisories

3. **Work collaboratively** to understand and fix reported vulnerabilities

## Security Updates

Security updates will be released as PATCH versions (e.g., 0.2.1, 0.2.2) and documented in:
- **GitHub Security Advisories**: https://github.com/axtion-io/TestBoost/security/advisories
- **CHANGELOG.md**: With `### Security` section
- **Release notes**: With clear upgrade instructions

Subscribe to **GitHub repository notifications** to receive security update alerts.

## Contact

For non-security-related questions, please use:
- **GitHub Issues**: https://github.com/axtion-io/TestBoost/issues
- **GitHub Discussions**: https://github.com/axtion-io/TestBoost/discussions

For security-related concerns **only**, contact: security@testboost.dev

---

**Document Version**: 1.0
**Last Updated**: 2026-01-26
