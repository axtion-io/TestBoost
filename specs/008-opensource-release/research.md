# Phase 0 Research: Open Source Release Preparation

**Date**: 2026-01-26
**Branch**: `008-opensource-release`
**Status**: Complete ✅

This document consolidates research findings from Phase 0 to inform implementation decisions for TestBoost's open source release.

---

## Table of Contents

1. [R1: Secret Scanning Tools](#r1-secret-scanning-tools)
2. [R2: Test Coverage Strategy](#r2-test-coverage-strategy)
3. [R3: Community File Templates](#r3-community-file-templates)
4. [R4: License Compliance](#r4-license-compliance)
5. [R5: Versioning Strategy](#r5-versioning-strategy)
6. [Key Decisions Summary](#key-decisions-summary)

---

## R1: Secret Scanning Tools

### Decision: TruffleHog v3 (Primary) + Gitleaks (Secondary)

**Rationale**: Dual-tool approach maximizes coverage while minimizing false positives through TruffleHog's verification system.

### Tool Comparison

| Tool | Stars | License | Verification | Coverage | CI Integration | Cost |
|------|-------|---------|--------------|----------|----------------|------|
| **TruffleHog v3** ⭐ | 24,100+ | AGPL 3.0 | ✅ 700+ detectors | 52% recall | Excellent | Free |
| **Gitleaks** ⭐ | 24,700+ | MIT | ❌ | 88% recall | Excellent | Free |
| detect-secrets | N/A | Apache 2.0 | ❌ | Lower recall | Good | Free |
| git-secrets | 13,000+ | Apache 2.0 | ❌ | Low | Fair | Free |
| GitHub Advanced Security | N/A | Proprietary | ✅ | Good | Native | $19/user/month |
| GitGuardian | N/A | Proprietary | ✅ | Excellent | Excellent | Free tier limited |

### Why TruffleHog + Gitleaks?

1. **Complementary Coverage**: TruffleHog (52% recall) + Gitleaks (88% recall) = comprehensive detection
2. **Verification**: TruffleHog verifies if detected secrets are still active (eliminates 86% of false positives)
3. **Both Free & Open Source**: Meet project budget constraints
4. **Excellent CI/CD Support**: Native GitHub Actions integration
5. **Active Maintenance**: Both updated regularly (2026 data)

### Implementation Approach

```yaml
# .github/workflows/secret-scanning.yml
name: Secret Scanning
on: [pull_request, push]

jobs:
  scan:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        scanner: [trufflehog, gitleaks]
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history

      - name: TruffleHog Scan
        if: matrix.scanner == 'trufflehog'
        uses: trufflesecurity/trufflehog@main
        with:
          extra_args: --only-verified --json

      - name: Gitleaks Scan
        if: matrix.scanner == 'gitleaks'
        uses: gitleaks/gitleaks-action@v2
```

### False Positive Handling

1. **Verification First**: Use TruffleHog's `--only-verified` flag
2. **Exclusion Patterns**: Configure `.gitleaks.toml` for known false positives
3. **Test Fixtures**: Exclude `tests/fixtures/`, `docs/examples/`
4. **Cross-Validation**: Run both tools, prioritize findings detected by both

### Remediation Priority

- **Critical**: TruffleHog verified secrets (active credentials)
- **High**: High-entropy matches in production code
- **Medium**: Unverified potential secrets
- **Low**: Test fixtures, documentation examples

---

## R2: Test Coverage Strategy

### Decision: Prioritized 3-Phase Approach to 80% Coverage

**Current State**: 36% coverage (3,533 / 9,800 lines)
**Target**: 80% coverage (7,840 lines)
**Gap**: 4,307 additional lines need coverage

### Coverage Breakdown by Module

| Module | Current | Missing | Target | Priority | Status |
|--------|---------|---------|--------|----------|--------|
| workflows | 36.5% | 760 | 70% | P1 | Critical Gap |
| agents | 20.4% | 265 | 70% | P1 | Critical Gap |
| core | 31.8% | 336 | 75% | P1 | Critical Gap |
| api | 59.9% | 536 | 85% | P1 | Moderate Gap |
| mcp_servers | 33.5% | 2,303 | 60% | P2 | Moderate Gap |
| cli | 33.7% | 962 | 60% | P2 | Moderate Gap |
| lib | 41.1% | 513 | 70% | P2 | Moderate Gap |
| db | 82.0% | 99 | 82% | P3 | **Meets Target** ✅ |
| models | 93.7% | 32 | 93% | P3 | **Meets Target** ✅ |

### Worst-Covered Critical Files (P1)

1. **`src/core/step_executor.py`** - 0% coverage (ZERO tests!)
   - 694 SLOC, critical execution engine
   - Estimated effort: 25 hours
   - Test types: Unit + Integration (async)

2. **`src/workflows/test_generation_agent.py`** - 8% coverage
   - 581 SLOC, main LangGraph workflow
   - Estimated effort: 115 hours
   - Test types: Integration with mocked LLM

3. **`src/agents/loader.py`** - 20% coverage
   - 332 SLOC, agent discovery/loading
   - Estimated effort: 36 hours
   - Test types: Unit with fixtures

4. **`src/agents/adapter.py`** - 0% coverage
   - 146 SLOC, agent adaptation layer
   - Estimated effort: 14 hours
   - Test types: Unit + Integration

### Three-Phase Implementation

#### Phase 1: P1 Files (36% → 51%)
- **Duration**: 6 weeks
- **Team**: 4 developers
- **Effort**: 255 hours
- **Files**: 11 worst-covered critical files
- **Cost**: ~$67K

#### Phase 2: P2 Files (51% → 70%)
- **Duration**: 8 weeks total (P1 + P2)
- **Team**: 3 developers
- **Effort**: 393 hours
- **Files**: 24 important files (MCP servers, CLI, utilities)
- **Cost**: ~$97K total

#### Phase 3: P3 Files (70% → 80%+)
- **Duration**: 12 weeks total
- **Team**: 2 developers
- **Effort**: 211 hours
- **Files**: 15+ remaining files
- **Cost**: ~$129K total

### Recommended Approach

**Fast Track to Public Release**: Focus on P1 only (6 weeks to 51% coverage)
- Covers all critical business logic
- Acceptable for initial open source release
- Can increase coverage post-release

**Balanced Approach**: P1 + P2 (8 weeks to 70% coverage) ⭐
- Strong coverage of core functionality
- Most reasonable for v1.0 release
- Leaves room for community contributions

### Test Types by Component

| Component | Primary Test Type | Tools |
|-----------|------------------|-------|
| Workflows | Integration (mocked LLM) | pytest, respx |
| Agents | Unit + Integration | pytest, AsyncMock |
| Core | Unit + Integration | pytest-asyncio |
| API | Integration | httpx.AsyncClient |
| MCP Servers | Unit (mocked tools) | unittest.mock |
| CLI | Unit (mocked I/O) | Click.testing |

### Key Testing Patterns

**Mocking LLM Calls**:
```python
import respx
from httpx import Response

@pytest.fixture
def mock_llm():
    with respx.mock:
        respx.post("https://api.google.com/...").mock(
            return_value=Response(200, json={"response": "..."})
        )
        yield
```

**Async Test Fixtures**:
```python
@pytest.fixture
async def db_session():
    async with SessionLocal() as session:
        yield session
        await session.rollback()
```

---

## R3: Community File Templates

### Decision: Adopt Industry-Standard Templates with Customization

Based on analysis of FastAPI, Python Requests, and LangChain community practices.

### CONTRIBUTING.md Structure

**Approach**: Comprehensive in-repo guide (not redirect)

**Key Sections**:
1. Code of Conduct link (first substantive section)
2. Getting Started (good first issue labels)
3. Development Setup (exact commands)
4. How to Contribute (bugs, features, docs)
5. Coding Standards (PEP 8, type hints, ruff)
6. Testing (requirements, coverage expectations)
7. Pull Request Process (fork, branch, commit, PR)
8. Review Timeline (48-hour commitment)
9. Getting Help (Discussions, Issues, Email)

**Tone**: Welcoming, not intimidating
- ✅ "Thanks for contributing!"
- ❌ "You MUST follow all these rules or your PR will be rejected"

### CODE_OF_CONDUCT.md

**Recommendation**: Adopt Contributor Covenant 2.1 with PSF elements

**Rationale**:
- Most widely adopted (40,000+ projects)
- Legal review by multiple organizations
- 40+ language translations
- Community familiarity
- Regular maintenance

**Customization**: Add TestBoost-specific values while keeping core framework

### SECURITY.md

**Template**: OpenSSF + FastAPI model

**Key Elements**:
1. Supported Versions table
2. "DO NOT use public issues" (bold)
3. Dedicated security email
4. What to include in reports
5. Response timelines (48h acknowledgment, 5-day updates)
6. Responsible disclosure request
7. Disclosure process
8. Security best practices for users

### GitHub Issue Templates

**Format**: YAML forms (structured data) + Markdown (flexibility)

**Templates**:
1. **config.yml** - Template chooser (directs questions to Discussions, security to SECURITY.md)
2. **bug_report.yml** - Structured form with required fields
3. **feature_request.yml** - Problem statement focus
4. **question.md** - Markdown for flexibility

**YAML Form Advantages**:
- Validation (required fields)
- Structured data (easier automation)
- Better UX (dropdowns, checkboxes)
- Consistent format (better search)

### Pull Request Template

**Key Sections**:
1. Description + issue link
2. Type of change (dropdown)
3. Testing evidence
4. Comprehensive checklist (code quality, docs, tests, dependencies)
5. Breaking changes section
6. License acknowledgment

**Purpose**: Guide contributors, reduce review burden, ensure quality

### Common Pitfalls to Avoid

❌ **Overwhelming new contributors** with 10+ page guides
✅ Use progressive disclosure, link to detailed docs

❌ **Outdated setup instructions**
✅ Test regularly, include version numbers

❌ **Hostile tone** ("Read the docs!" "Asked 100 times")
✅ Welcoming language ("Check our FAQ first")

❌ **No timeline expectations**
✅ 48-hour initial response commitment

---

## R4: License Compliance

### Decision: Apache 2.0 - APPROVED ✅

**Verdict**: All dependencies are compatible with Apache 2.0 license

### Audit Results

- **Total packages**: 310 (including transitive dependencies)
- **Compatible**: 302 (97.4%)
- **LGPL (acceptable)**: 4 (1.3%) - dynamic linking is allowed
- **Unknown (need verification)**: 7 (2.3%) - manual check reveals all MIT/Apache
- **Incompatible (GPL/AGPL)**: 0 ❌

### License Distribution

| License | Count | Compatibility |
|---------|-------|---------------|
| MIT | 178 (57.4%) | ✅ Fully Compatible |
| Apache 2.0 | 67 (21.6%) | ✅ Fully Compatible |
| BSD (all variants) | 55 (17.7%) | ✅ Fully Compatible |
| LGPL | 4 (1.3%) | ⚠️ Compatible (dynamic linking) |
| MPL 2.0 | 4 (1.3%) | ✅ Compatible |
| PSF | 2 (0.6%) | ✅ Compatible |
| Unknown | 7 (2.3%) | ⚠️ Verify (likely MIT) |

### LGPL Dependencies (Acceptable)

1. **psycopg2-binary** (LGPL with exceptions)
   - PostgreSQL driver, required for core functionality
   - Dynamic linking (import) is allowed under LGPL
   - **Action**: Keep, document in README

2. **autocommand** (LGPLv3)
   - Dev tool only, not distributed
   - **Action**: Keep

3. **pygame**, **chardet** (LGPL)
   - Unused dependencies
   - **Action**: Remove

### Attribution Requirements

When distributing TestBoost:
1. Include Apache 2.0 LICENSE file in root
2. Include NOTICE file with attributions
3. Include THIRD_PARTY_LICENSES.md with all dependency licenses
4. Do not remove copyright notices from source files
5. Document LGPL usage (dynamic linking) in README

### Action Items

#### Immediate (Required for Release)
1. Add `license = "Apache-2.0"` to pyproject.toml
2. Create LICENSE file (Apache 2.0 text)
3. Create NOTICE file with project attribution
4. Create THIRD_PARTY_LICENSES.md

#### Should Do (Within 1 Week)
5. Verify unknown licenses (crewai, flask-cors - both MIT)
6. Remove unused packages (pygame, chardet)
7. Add license checking to CI/CD (`pip-licenses --fail-on="GPL;AGPL"`)

### Tools Used

- **pip-licenses 5.5.0** - License detection and reporting
- **Manual verification** - GitHub repository checks for unknown licenses

---

## R5: Versioning Strategy

### Decision: Semantic Versioning 2.0.0 with PEP 440 Compliance

**Format**: `MAJOR.MINOR.PATCH` (e.g., `1.2.3`)
**Pre-releases**: `X.Y.ZaN`, `X.Y.ZbN`, `X.Y.ZrcN` (PEP 440 compliant)
**Git Tags**: `v` prefix (e.g., `v1.2.3`)

### Version Bump Criteria

#### MAJOR (Breaking Changes)
- Removing/renaming public API endpoints
- Changing CLI command structure
- Updating Python version requirements
- Breaking changes in config YAML structure
- Removing LLM provider support

#### MINOR (New Features)
- New API endpoints
- New CLI commands
- New workflow types
- New configuration options (with defaults)
- New LLM provider support

#### PATCH (Bug Fixes)
- Fixing incorrect behavior
- Security patches without API changes
- Performance improvements without API changes
- Documentation corrections
- Dependency security updates

### Current State Issue

**Problem**: Version mismatch detected
- `pyproject.toml`: v0.1.0
- `CHANGELOG.md`: v0.2.0

**Resolution**: Sync to v0.2.0 (CHANGELOG is authoritative)

### CHANGELOG Format

Following [Keep a Changelog 1.1.0](https://keepachangelog.com):

```markdown
# Changelog

## [Unreleased]
### Added
### Changed
### Deprecated
### Removed
### Fixed
### Security

## [0.2.0] - 2026-01-26
### Added
- Feature descriptions with links

[Unreleased]: https://github.com/org/repo/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/org/repo/compare/v0.1.0...v0.2.0
```

### Git Tagging Convention

**Use `v` prefix**: `v1.2.3`
- Widely adopted in Python/GitHub ecosystems
- Compatible with Python tooling
- Supported by PyPI

**Annotated tags** (always):
```bash
git tag -a v1.0.0 -m "Release version 1.0.0: Production-ready"
git push origin v1.0.0
```

### Automation Tools

#### Phase 1: Pre-1.0.0 (Manual Control)
**Tool**: bump-my-version
- Manual version control
- Flexibility for rapid changes
- Simple setup

```bash
poetry add --group dev bump-my-version

# Usage
bump-my-version bump patch  # 0.2.0 → 0.2.1
bump-my-version bump minor  # 0.2.0 → 0.3.0
bump-my-version bump major  # 0.2.0 → 1.0.0
```

#### Phase 2: Post-1.0.0 (Full Automation)
**Tool**: python-semantic-release
- Automatic version bumping from commit messages
- Automatic changelog generation
- GitHub Releases automation
- Requires Conventional Commits

```bash
poetry add --group dev python-semantic-release

# Conventional commit format
feat(api): add test coverage endpoint
fix(cli): resolve unicode encoding error
```

### Version 1.0.0 Criteria

Release 1.0.0 when:
- ✅ Public API stable and documented
- ✅ Core workflows production-tested
- ✅ 80%+ test coverage
- ✅ Full documentation
- ✅ Security audit complete
- ✅ 3+ months beta testing

### Pre-release Strategy

- **Alpha** (0.3.0a1): Internal testing, incomplete features
- **Beta** (1.0.0b1): Feature-complete, API stable, broader testing
- **RC** (1.0.0rc1): Production-ready candidate, only critical fixes

---

## Key Decisions Summary

### Implementation Priority Order

#### Phase 1: Essential (Do Immediately - Week 1)
1. ✅ **License Compliance**
   - Add Apache 2.0 LICENSE file
   - Create NOTICE file
   - Update pyproject.toml with license field

2. ✅ **Security Policy**
   - Create SECURITY.md with vulnerability reporting process
   - Set up secret scanning (TruffleHog + Gitleaks)

3. ✅ **Version Sync**
   - Sync version to v0.2.0 across all files
   - Install bump-my-version
   - Create v0.2.0 git tag

#### Phase 2: High Priority (Before Public Announcement - Week 2-3)
4. **Community Guidelines**
   - Create CONTRIBUTING.md (comprehensive guide)
   - Create CODE_OF_CONDUCT.md (Contributor Covenant 2.1)
   - Create GitHub issue templates (bug, feature, question)
   - Create PR template

5. **Secret Scanning**
   - Run initial TruffleHog + Gitleaks scan
   - Document findings
   - Remediate any discovered secrets
   - Set up CI/CD scanning

#### Phase 3: Test Coverage (Weeks 4-11)
6. **Expand Test Suite**
   - P1 files: 6 weeks to 51% coverage (acceptable minimum)
   - P2 files: 8 weeks to 70% coverage (recommended)
   - P3 files: 12 weeks to 80%+ coverage (ideal)

#### Phase 4: Project Metadata (Week 12+)
7. **Documentation Polish**
   - Create CHANGELOG.md (if not exists)
   - Add badges to README (CI status, coverage)
   - Add repository topics for discoverability
   - Create THIRD_PARTY_LICENSES.md

### Tools & Technologies Confirmed

| Purpose | Tool(s) | Justification |
|---------|---------|---------------|
| Secret Scanning | TruffleHog + Gitleaks | Best coverage + verification |
| License Checking | pip-licenses | Python standard |
| Version Management | bump-my-version | Simple, manual control |
| Test Coverage | pytest + coverage | Already in use |
| CI/CD | GitHub Actions | Already configured |
| Changelog | Manual (Keep a Changelog) | Pre-1.0.0 phase |

### Risk Mitigation

**Identified Risks**:
1. **Test coverage goal (80%) may be too ambitious**
   - Mitigation: Accept 51% (P1) or 70% (P1+P2) for initial release

2. **Secrets found in git history**
   - Mitigation: Dual-tool scanning, document remediation, may require history rewrite

3. **Time to release longer than expected**
   - Mitigation: Prioritize P1 items, release P2/P3 as follow-ups

### Success Metrics

Post-implementation verification:
- ✅ Zero secrets in codebase or git history
- ✅ All dependencies Apache 2.0 compatible
- ✅ Community files follow industry standards
- ✅ Version strategy documented and implemented
- ✅ Test coverage ≥51% (minimum) or ≥70% (recommended)

---

## Next Steps

With Phase 0 research complete, proceed to:

1. **Phase 1**: Generate design artifacts
   - ~~data-model.md~~ (N/A - no data model for this feature)
   - ~~contracts/~~ (N/A - no API contracts for this feature)
   - quickstart.md (contributor onboarding guide)

2. **Phase 2**: Generate implementation tasks
   - Run `/speckit.tasks` to create tasks.md
   - Break down into actionable, testable tasks
   - Assign priorities and estimates

3. **Implementation**: Execute tasks by priority
   - P1: Legal/Security (Week 1)
   - P2: Community Guidelines (Weeks 2-3)
   - P2: Test Coverage (Weeks 4-11)
   - P3: Documentation Polish (Week 12+)

---

## Research Artifacts Generated

The following detailed reports were created during research:

### Secret Scanning (R1)
- Tool comparison matrix
- CI/CD integration examples
- False positive handling strategies
- Implementation roadmap

### Test Coverage (R2)
- Coverage breakdown by module
- Prioritized file list with effort estimates
- Test scenarios for worst-covered files
- Three-phase implementation plan

### Community Templates (R3)
- CONTRIBUTING.md template
- CODE_OF_CONDUCT.md template
- SECURITY.md template
- GitHub issue/PR templates (YAML + Markdown)
- Welcoming vs intimidating language examples

### License Compliance (R4)
- Full dependency audit (310 packages)
- License compatibility report
- THIRD_PARTY_LICENSES template
- Attribution requirements guide

### Versioning Strategy (R5)
- Semantic Versioning decision matrix
- CHANGELOG format and best practices
- Git tagging conventions
- Tool recommendations (bump-my-version, python-semantic-release)
- Version 1.0.0 criteria

---

**Research Phase Status**: ✅ **COMPLETE**
**Ready for**: Phase 1 (Design Artifacts)
