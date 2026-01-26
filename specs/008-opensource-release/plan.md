# Implementation Plan: Open Source Release Preparation

**Branch**: `008-opensource-release` | **Date**: 2026-01-26 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/008-opensource-release/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/commands/plan.md` for the execution workflow.

## Summary

Prepare TestBoost (v0.2.0) for public open source release on GitHub under Apache 2.0 license. Current state: 60% ready (18/30 requirements complete) with comprehensive README, CI/CD infrastructure, and 65 test files. Critical gaps: LICENSE file, community guidelines (CONTRIBUTING, CODE_OF_CONDUCT, SECURITY), GitHub templates, test coverage (36% → 80% target), and secret scanning. Priority focus on P1 legal/security requirements, then P2 community enablement, finally P3 project metadata.

## Technical Context

**Language/Version**: Python 3.11+ (existing project)
**Primary Dependencies**: Existing stack (FastAPI, LangGraph, SQLAlchemy) + new tools for secret scanning (git-secrets, TruffleHog, or GitHub Advanced Security)
**Storage**: N/A (documentation and configuration files only)
**Testing**: pytest (existing) - need to expand coverage from 36% to 80% (44% gap)
**Target Platform**: GitHub public repository with GitHub Actions for CI/CD
**Project Type**: Single Python project (existing structure in src/)
**Performance Goals**: N/A for this feature (documentation and tooling setup)
**Constraints**:
- Zero secrets in codebase or git history
- 80% minimum test coverage before public release
- All CI checks must pass (linting, tests, security scans)
- Apache 2.0 license compliance for all dependencies
**Scale/Scope**:
- Current: 9800 SLOC across src/, 65 test files
- Target: Public open source project with community contribution capability
- Expected initial reach: 10+ GitHub stars in first month

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### ✅ Aligned with Constitution

1. **Zéro Complaisance** (Principle 1): ✅
   - Spec explicitly calls for real external developer testing (5 testers)
   - Success criteria are measurable (80% coverage, 0 secrets, 10+ stars)
   - No fake metrics or placeholder values

2. **Outils via MCP** (Principle 2): ✅ N/A
   - This feature doesn't add agent tools, only documentation and community files
   - Existing MCP servers remain unchanged

3. **Pas de Mocks** (Principle 3): ✅
   - User testing will be done by real external developers
   - No simulated community engagement or fake contributors

4. **Automatisation avec Contrôle** (Principle 4): ✅
   - Secret scanning is automated but results reviewed by maintainer
   - Community contribution process requires manual PR review
   - No automatic merges or bypassing of review gates

5. **Traçabilité Complète** (Principle 5): ✅
   - All community interactions tracked via GitHub (issues, PRs, discussions)
   - CI/CD logs all checks and their results
   - Secret scanning produces audit reports

6. **Validation Avant Modification** (Principle 6): ✅
   - Spec requires secret scanning before public release
   - Test coverage gate (80%) before release
   - All CI checks must pass

7. **Isolation et Sécurité** (Principle 7): ✅
   - Feature developed on dedicated branch (008-opensource-release)
   - PR review required before merging to main
   - .env.example protects real credentials

8. **Découplage et Modularité** (Principle 8): ✅
   - Community files (LICENSE, CONTRIBUTING) are independent additions
   - No modifications to core application logic
   - Documentation can be updated without code changes

9. **Transparence des Décisions** (Principle 9): ✅
   - CONTRIBUTING.md documents decision-making process
   - SECURITY.md explains vulnerability handling
   - README documents assumptions and limitations

10. **Robustesse** (Principle 10): ✅ N/A
    - No runtime behavior changes in this feature
    - Documentation and templates don't affect error handling

11. **Performance** (Principle 11): ✅ N/A
    - No performance impact (documentation only)

12. **Respect des Standards** (Principle 12): ✅
    - Following Python ecosystem standards (LICENSE, CONTRIBUTING, CODE_OF_CONDUCT)
    - GitHub community standards (issue/PR templates)
    - Apache 2.0 is widely recognized standard

13. **Simplicité** (Principle 13): ✅
    - Contributing guidelines simplify onboarding
    - README already comprehensive (456 lines)
    - Quick start guide enables 30-minute setup

### ⚠️ Areas Requiring Attention

**Test Coverage Gap (36% → 80%)**:
- Current: 9800 SLOC, 36% coverage
- Requires: Adding ~4400 SLOC of test code (estimated based on 44% gap)
- Files needing most work: `test_generation_agent.py` (8% coverage), other workflow files
- **Mitigation**: Phase 2 tasks will break this down by module with specific test scenarios

**Secret Scanning**:
- Must scan entire git history, not just current HEAD
- Potential for false positives requiring manual review
- **Mitigation**: Use multiple tools (git-secrets + TruffleHog + GitHub scanning) and document all findings

### No Constitution Violations

This feature adds documentation, legal files, and community guidelines without modifying core application behavior or architecture. All principles remain respected.

## Project Structure

### Documentation (this feature)

```text
specs/008-opensource-release/
├── spec.md                # Feature specification (COMPLETE)
├── checklists/
│   └── requirements.md    # Spec validation (COMPLETE)
├── plan.md                # This file (IN PROGRESS)
├── research.md            # Phase 0 output (NEXT)
├── data-model.md          # Phase 1 output (N/A - no data model for this feature)
├── quickstart.md          # Phase 1 output (NEXT)
├── contracts/             # Phase 1 output (N/A - no API contracts for this feature)
└── tasks.md               # Phase 2 output (via /speckit.tasks command)
```

### Source Code (repository root)

**No changes to src/ directory structure** - this feature only adds files at repository root and in .github/

```text
TestBoost/                      # Repository root
├── LICENSE                     # NEW: Apache 2.0 license file
├── CONTRIBUTING.md             # NEW: Contribution guidelines
├── CODE_OF_CONDUCT.md          # NEW: Community behavior standards
├── SECURITY.md                 # NEW: Security policy and vulnerability reporting
├── CHANGELOG.md                # NEW: Version history
├── README.md                   # UPDATE: Replace "[Your License Here]" placeholder, add badges
├── pyproject.toml              # UPDATE: Add license field
│
├── .github/
│   ├── ISSUE_TEMPLATE/         # NEW: Issue templates directory
│   │   ├── bug_report.md       # NEW: Bug report template
│   │   └── feature_request.md  # NEW: Feature request template
│   ├── pull_request_template.md # NEW: PR template with checklist
│   ├── workflows/              # EXISTING: No changes to CI/CD workflows
│   │   ├── ci.yml
│   │   ├── ci-tests.yml
│   │   └── impact-check.yml
│   └── README.md               # EXISTING: CI/CD documentation
│
├── src/                        # EXISTING: No structural changes
│   ├── api/                    # UPDATE: May need copyright headers
│   ├── cli/
│   ├── core/
│   ├── db/
│   ├── lib/
│   ├── workflows/
│   ├── agents/
│   └── mcp_servers/
│
├── tests/                      # EXPAND: Add tests to reach 80% coverage
│   ├── unit/                   # EXPAND: Add missing unit tests
│   ├── integration/            # EXISTING
│   ├── e2e/                    # EXISTING
│   ├── regression/             # EXISTING
│   └── security/               # EXISTING
│
├── config/                     # EXISTING: No changes
├── docs/                       # EXISTING: May add MAINTAINERS.md
└── .env.example                # EXISTING: Already has placeholders
```

**Structure Decision**:

This is a **non-invasive feature** that adds community and legal files without modifying the existing single-project Python structure. All new files are added at repository root or in `.github/` directory following GitHub community standards. The only code modifications will be:
1. Adding copyright headers to source files (src/**/*.py)
2. Expanding test suite (tests/) to reach 80% coverage
3. Minor README updates to fix placeholders and add badges

## Complexity Tracking

> **No violations requiring justification** - this feature adds documentation and community files without architectural changes.

## Phase 0: Research & Technology Decisions

### Research Questions

The following areas require investigation to resolve unknowns and make informed decisions:

#### R1: Secret Scanning Tools Evaluation

**Question**: Which secret scanning tool(s) should we use for detecting accidentally committed credentials?

**Options to Evaluate**:
- git-secrets (AWS Labs) - Git hooks for preventing secrets
- TruffleHog - Entropy-based secret detection in git history
- detect-secrets (Yelp) - Preventing new secrets from entering codebase
- GitHub Advanced Security - Built-in secret scanning (requires GitHub Enterprise/paid)
- GitGuardian - Commercial with free tier

**Evaluation Criteria**:
- Free and open source (project has no budget)
- Scans entire git history, not just current HEAD
- Low false positive rate
- Easy CI/CD integration
- Active maintenance and community support

**Deliverable**: Recommendation for primary tool + optional secondary tool for validation

#### R2: Test Coverage Strategy

**Question**: How should we prioritize test expansion to reach 80% coverage from current 36%?

**Current State Analysis**:
- Total: 9800 SLOC, 36% coverage
- Worst covered: `test_generation_agent.py` (8%), `maven_maintenance_agent.py` (estimated low)
- Best covered: API endpoints, database models (estimated from integration tests)

**Research Areas**:
- Coverage breakdown by module (use `coverage report --show-missing`)
- Identify critical vs non-critical paths
- Determine test types needed (unit vs integration vs contract)
- Estimate effort per module (SLOC to be tested vs test SLOC needed)

**Deliverable**: Prioritized module list with test scenarios and effort estimates

#### R3: Community File Templates and Best Practices

**Question**: What should our community files contain to follow Python open source standards?

**Files to Research**:
- CONTRIBUTING.md - development workflow, coding standards, PR process
- CODE_OF_CONDUCT.md - behavior expectations (Contributor Covenant?)
- SECURITY.md - vulnerability disclosure policy
- GitHub issue/PR templates - what fields to include?
- MAINTAINERS.md (optional) - governance structure

**Reference Projects**:
- FastAPI (similar tech stack, very successful open source)
- Requests (Python, Apache 2.0, large community)
- LangChain (similar domain, new but rapidly growing)

**Evaluation Criteria**:
- Clarity for new contributors
- Reduction of low-quality issues/PRs
- Encouraging community engagement
- Legal protection for maintainers

**Deliverable**: Template recommendations with rationale for each choice

#### R4: Apache 2.0 License Compliance Verification

**Question**: Do all our dependencies have licenses compatible with Apache 2.0?

**Required Analysis**:
- Audit pyproject.toml dependencies
- Check license of each package (use `pip-licenses` or similar)
- Identify any GPL/AGPL dependencies (incompatible with Apache 2.0)
- Document attribution requirements for dependencies

**Known Dependencies** (from pyproject.toml):
- fastapi, uvicorn (MIT/Apache 2.0)
- sqlalchemy (MIT)
- langchain, langgraph (MIT)
- pydantic (MIT)
- ...need full audit

**Deliverable**: Dependency license compatibility report + list of any packages requiring replacement

#### R5: Semantic Versioning and Release Strategy

**Question**: How should we version releases and communicate breaking changes?

**Current State**: v0.2.0 (documented in README, no formal versioning strategy)

**Research Areas**:
- Semantic Versioning 2.0.0 (semver.org)
- Python-specific practices (PEP 440)
- Changelog format (Keep a Changelog)
- Release automation (GitHub Releases, git tags)

**Deliverable**: Versioning strategy document with examples of what constitutes major/minor/patch changes

### Research Assignments

| Research ID | Assignee | Priority | Estimated Effort |
|-------------|----------|----------|------------------|
| R1 - Secret Scanning | AI Agent | P1 | 1-2 hours |
| R2 - Test Coverage Strategy | AI Agent | P1 | 2-3 hours |
| R3 - Community Templates | AI Agent | P2 | 2-3 hours |
| R4 - License Compliance | AI Agent | P1 | 1-2 hours |
| R5 - Versioning Strategy | AI Agent | P3 | 1 hour |

**Total Research Effort**: 7-11 hours

**Next Step**: Generate `research.md` with findings from all research questions

## Phase 1: Design Artifacts

### Data Model

**N/A** - This feature does not involve data storage or new entities. All existing database tables remain unchanged.

### API Contracts

**N/A** - This feature does not add or modify API endpoints. It only adds documentation and community files.

### Quickstart Guide

**Output**: `quickstart.md` with step-by-step guide for:
1. Setting up development environment for contributing
2. Running tests locally
3. Submitting first contribution
4. Understanding project structure and key patterns

This guide will be referenced from CONTRIBUTING.md.

## Phase 2: Implementation Tasks

**Note**: Detailed implementation tasks will be generated via `/speckit.tasks` command after research is complete.

### High-Level Task Groups

#### TG1: Legal and Licensing (P1)
- Add Apache 2.0 LICENSE file
- Add copyright headers to source files
- Document third-party licenses
- Update pyproject.toml with license field

#### TG2: Security (P1)
- Create SECURITY.md with vulnerability reporting process
- Run secret scanning on entire git history
- Document security best practices
- Set up automated secret scanning in CI

#### TG3: Community Guidelines (P2)
- Create CONTRIBUTING.md with development workflow
- Create CODE_OF_CONDUCT.md
- Create GitHub issue templates (bug report, feature request)
- Create GitHub PR template
- Update README with contribution section

#### TG4: Test Coverage (P2)
- Expand test suite module by module
- Target: 80% coverage minimum
- Focus on workflow files and core logic

#### TG5: Project Metadata (P3)
- Create CHANGELOG.md
- Document semantic versioning strategy
- Add missing badges to README (CI status, coverage)
- Add repository topics/tags for discoverability

#### TG6: Documentation Polish (P3)
- Fix README placeholders ("[Your License Here]")
- Review and improve existing documentation
- Add links between documentation files

## Success Criteria Validation

Post-implementation, the following must be verified:

- [ ] **SC-001**: 5 external developers can install and run TestBoost in <30 minutes using only documentation
- [ ] **SC-002**: 90% of survey respondents understand project purpose within 2 minutes of reading README
- [ ] **SC-003**: All CI checks pass (tests, linting, security scans) with 100% success rate
- [ ] **SC-004**: Test coverage reaches minimum 80%
- [ ] **SC-005**: Zero secrets found in codebase or git history
- [ ] **SC-006**: Documentation receives 4/5 or higher average rating from external reviewers
- [ ] **SC-007**: First external contribution merged within 30 days of public release
- [ ] **SC-008**: Project receives 10+ GitHub stars within first month

## Risk Mitigation

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Test coverage goal too ambitious (80%) | High | Medium | Phase 2 tasks will prioritize critical paths; can adjust target to 70% if needed |
| Secrets found in git history | Critical | Medium | Use multiple scanning tools; document remediation process; may require git history rewrite |
| Community engagement lower than expected | Medium | Medium | Focus on quality documentation; leverage existing networks; patient organic growth |
| License compliance issues with dependencies | High | Low | Early audit in Phase 0; replace incompatible dependencies before release |
| Time to public release longer than expected | Low | High | Prioritize P1 items; can release with P2/P3 as follow-up improvements |

## Timeline Estimates

- **Phase 0 (Research)**: 1-2 days
- **Phase 1 (Design artifacts)**: 1 day (quickstart guide only)
- **Phase 2 (Implementation)**: 5-10 days (depending on test coverage effort)
- **Testing & Validation**: 2-3 days (external developer testing)
- **Total**: 9-16 days

**Critical Path**: Test coverage expansion (TG4) is the longest task and blocks final release.

## Next Steps

1. ✅ Plan complete - review and approve
2. ✅ Execute Phase 0 research (generate `research.md`) - **COMPLETE**
3. ✅ Execute Phase 1 design (generate `quickstart.md`) - **COMPLETE**
4. ⏳ Generate implementation tasks with `/speckit.tasks`
5. ⏳ Begin implementation following prioritized task list

---

## Phase Completion Status

### Phase 0: Research ✅ COMPLETE
- [research.md](research.md) created with consolidated findings from 5 research areas
- All unknowns resolved with actionable recommendations
- Key decisions documented for implementation

### Phase 1: Design Artifacts ✅ COMPLETE
- [quickstart.md](quickstart.md) created for contributor onboarding
- data-model.md: N/A (no data model for this feature)
- contracts/: N/A (no API contracts for this feature)

### Phase 2: Implementation Tasks ⏳ NEXT
- Run `/speckit.tasks` to generate tasks.md
- Break down into actionable, priority-ordered tasks
