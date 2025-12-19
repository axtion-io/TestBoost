# Implementation Plan: Impact Analysis & Regression Testing

**Branch**: `003-impact-analysis-testing` | **Date**: 2025-12-19 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/003-impact-analysis-testing/spec.md`

## Summary

Enhance test generation by analyzing git diff of uncommitted changes to identify code impacts, classify risk levels, and generate targeted anti-regression tests following the test pyramid principle. The system will produce JSON impact reports for CI integration and support chunked processing for large diffs.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: LangGraph 1.0+, LangChain Core 1.1+, FastAPI 0.121, Typer (CLI)
**Storage**: PostgreSQL 15 (existing, port 5433)
**Testing**: pytest 8.2+ with pytest-asyncio, pytest-cov
**Target Platform**: Linux/Windows server, CLI-first
**Project Type**: Single project (CLI + API)
**Performance Goals**: Impact analysis + test generation < 2 minutes for < 500 lines (SC-006)
**Constraints**: Retry with exponential backoff (3 attempts), chunk diffs > 500 lines
**Scale/Scope**: Single developer workflow, integrates with existing test generation agent

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Implementation |
|-----------|--------|----------------|
| 1. Zéro Complaisance | ✅ Pass | Report actual impacts found, never fake results |
| 2. Outils via MCP | ✅ Pass | Git diff analysis via MCP server tools |
| 3. Pas de Mocks Production | ✅ Pass | Real git diff, real LLM analysis |
| 4. Automatisation + Contrôle | ✅ Pass | CLI triggers, user reviews generated tests |
| 5. Traçabilité Complète | ✅ Pass | Impact report JSON logs all decisions |
| 6. Validation Avant Modification | ✅ Pass | Analyze diff before generating tests |
| 7. Isolation et Sécurité | ✅ Pass | Works on current branch, no destructive ops |
| 8. Découplage et Modularité | ✅ Pass | Impact analyzer separate from test generator |
| 9. Transparence des Décisions | ✅ Pass | Impact report explains why each test is needed |
| 10. Robustesse | ✅ Pass | Exponential backoff retry (FR-012) |
| 11. Performance | ✅ Pass | < 2 min for < 500 lines, chunking for larger |
| 12. Respect Standards Projet | ✅ Pass | Detects existing test conventions |
| 13. Simplicité | ✅ Pass | Single CLI command: `boost tests impact` |

## Project Structure

### Documentation (this feature)

```text
specs/003-impact-analysis-testing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── impact-report.schema.json
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
src/
├── workflows/
│   ├── impact_analysis.py      # NEW: Git diff analyzer + impact classifier
│   └── test_generation_agent.py # EXISTING: Enhanced with impact input
├── mcp_servers/
│   └── git_maintenance/
│       └── tools/
│           └── diff.py          # NEW: Git diff extraction tool
├── models/
│   ├── impact.py               # NEW: Impact, ChangeCategory, RiskLevel
│   └── impact_report.py        # NEW: ImpactReport, TestRequirement
├── cli/
│   └── commands/
│       └── tests.py            # EXISTING: Add `impact` subcommand
└── lib/
    └── diff_chunker.py         # NEW: Chunk large diffs into batches

tests/
├── unit/
│   ├── test_impact_analysis.py
│   └── test_diff_chunker.py
└── integration/
    └── test_impact_workflow.py
```

**Structure Decision**: Single project structure. New modules integrate with existing `src/workflows/` and `src/mcp_servers/` patterns. Impact analyzer outputs feed into existing test generation agent.

## Complexity Tracking

> No violations detected. All gates pass.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| None | N/A | N/A |
