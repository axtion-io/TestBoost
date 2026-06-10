# MVP Plan — Async CI/CD Integration

> Living document. Phases 1-6 are **done**; this file now keeps the
> status, the decisions taken, what remains open, and the lessons
> learned. The detailed per-phase task breakdowns, acceptance criteria
> and test plans were executed and removed from this document — they
> live in the git history of this file if you need them.

## Status overview

| Phase | Goal | Status | Completed |
|-------|------|--------|-----------|
| Spike | Prove pause/resume primitives | ✅ done | 2026-06-01 |
| 1 | Security & state foundations (HMAC, per-file cursor, resume) | ✅ done | 2026-06-02 |
| 2 | UX extension (hints, validate/killer pause triggers) | ✅ done | 2026-06-02 |
| 3 | Operability (cleanup, doctor, metrics) | ✅ done | 2026-06-02 |
| 4 | GitLab integration layer | ✅ done (reworked in P5-P6) | 2026-06-02 |
| 5 | Hardening — review fixes (state hand-off, secret leak, dead features) | ✅ done | 2026-06-09 |
| 6 | Grouped questions & resume UX | ✅ done | 2026-06-09 |

## What remains open

- **P4-USR / P6-USR — the real-world demo.** Everything is implemented
  and unit-tested end-to-end, but the loop has never been driven on a
  real GitLab project. Protocol: a demo Java repo with an "unclear"
  service, the webhook deployed (see `docs/gitlab-integration.md`), two
  humans (dev + reviewer); push an MR, watch generate pause orange, ONE
  question comment appear, answer it, watch the resume pipeline finish.
  Acceptance: round-trip < 5 min, recorded 5-minute screencast usable
  for onboarding. **Next step: find a volunteer dev with a real GitLab
  project.**
- **E2E suite** (cross-cutting): `tests/e2e/` is an empty placeholder —
  the old e2e file tested deleted agent modules and was removed. Add
  fixtures that cross the seams unit tests mock (cross-pipeline state,
  GitLab variables, script distribution).
- GitLab.com vs Self-Managed validation (both must run the template).

## Key decisions (user-validated)

- **2026-06-01**: do not mock the P4 user test; real-world UX validation
  with an external volunteer dev.
- **2026-06-09** (post-review):
  - Session state crosses pipelines by **committing `.testboost/` to the
    MR branch** on pause (`[skip ci]`, secret excluded) — no artifact
    plumbing.
  - **One batched question per run** instead of one pause per file.
  - Paused jobs show GitLab's **orange warning** status
    (`allow_failure: exit_codes: [78]`), never a misleading green.
  - The cursor memorizes the run scope (`--files`) and generated output;
    a `fixed_code` answer is applied **without regenerating**.
  - Answers are **consumed only after the answered work succeeds**
    (crash-safe resume).
  - `validate_fixes` accepts `fixed_code` only; hints stay a
    generate/killer feature.

## Lessons learned

### Phase 1 — 2026-06-02

- **Refactor**: the original `generate` used a 3-pass structure (collect in
  memory → bulk write → bulk compile-fix). Merged into one per-file
  pipeline (edge cases → generate → write → compile-fix) so the cursor
  has a single semantic anchor.
- **Signing**: signing on `emit_question` is opt-in via the
  `project_path` parameter to preserve backwards compat with the spike
  tests. In production, `cli.py` always passes it.
- **`markdown_preview` field** in `question.json` is computed *before*
  signing so it's included in the HMAC and authoritative — pasting it
  back into a comment is safe.

### Phase 2 — 2026-06-02

- **Hints mode**: when `compile_fixes.<class>.hints` is provided, the
  compile-fix loop caps to a single LLM retry with the hint prepended to
  the error context. `fixed_code` wins when both are present.
- **Validate/killer pause**: wired with the same emit_question pattern;
  the killer wiring stayed minimal (full hint injection landed in P5).

### Phase 3 — 2026-06-02

- **Cleanup** is non-destructive (status flip only, audit preserved).
- **Metrics**: one `[TESTBOOST_METRICS:{...}]` line per command.
- **Doctor**: 4 checks (`.tb_secret`, write perms, Maven, LLM ping).

### Phase 4 — 2026-06-02

- Template, MR scripts and webhook shipped individually tested — see the
  2026-06-09 review below for what that hid.

### Deep review — 2026-06-09

A full branch review invalidated Phase 4's "done" status: the components
worked in isolation but **the loop did not close end-to-end**. Root
causes: session state never crossed pipelines (fresh checkout, no
artifacts); `CI_MERGE_REQUEST_IID` unset in webhook-triggered branch
pipelines; `include:` does not ship shell scripts to consumer repos;
`.tb_secret` leaked in CI artifacts; `killer_hints`/`validate hints`
documented but not wired; `cleanup` could never find a real paused
session.

- **Lesson**: "tests green" ≠ "feature works" — every P4 test mocked the
  seam where the integration actually broke (cross-pipeline state, GitLab
  variable availability, script distribution). Phase 5/6 acceptance
  criteria therefore required E2E coverage that crosses those seams.

### Phase 5 — 2026-06-09

- State hand-off via session commit to the MR branch; resume job is part
  of the template; `.tb_secret` excluded from artifacts.
- MR scripts became `testboost gitlab post-question|fetch-answer`
  subcommands (pip-installable; the bash `set -e` dead-error-path bug
  disappeared with the scripts).
- `emit_question` flips the session-level status so cleanup works;
  `killer_hints` actually injected; metrics moved to stderr; webhook
  hardened (constant-time compare, loop guards).

### Phase 6 — 2026-06-09

- Batched questions (one MR comment per run, `items[]` + combined
  answer schema); answers scoped per class; cursor remembers
  `--files` + deferred test paths (zero-LLM `fixed_code` application);
  verify-then-finalize answers (crash-safe); orange pause status.

### Dead-code purge — 2026-06-09

- `scripts/find_dead_code.py` (AST reachability + reference counting,
  cross-checked with vulture) found ~1 900 dead lines, mostly survivors
  of the 001-simplify purge — including config fields whose removal the
  spec had explicitly mandated (T015) and an e2e file importing deleted
  modules, invisible because permanently skipped in CI.
- **Lesson**: a spec's deletion tasks need a verification step
  (`find_dead_code.py` now fills that role; consider wiring it into CI).
