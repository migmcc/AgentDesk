# Agent Desk — Release v0.1

## Version
`0.1.0` — MVP.

## MVP status
**Complete.** The full local-first cycle works end to end and is covered by an automated test suite
(71 tests) and a documented demo ([mvp-demo.md](mvp-demo.md)).

```text
new → plan → route → prompt → start → handover → gate → done → unlock next task
```

## Included functionality
- Project creation with on-disk scaffold + local SQLite state.
- Deterministic planning: idea → 5 base docs + 12 routed, dependency-aware tasks.
- Fixed-rule model routing with manual override (Codex / Claude Code / local model).
- Per-model prompt generation (copy-paste; no execution).
- File-locking conflict guard (allow / warn / block) — controls collisions.
- Dependency manager — controls order (validation, eligibility, recompute, topological order).
- Task state machine with validated transitions.
- Deterministic handover generation (Markdown + persisted).
- Deterministic basic quality gate (PASS / PASS_WITH_WARNINGS / FAIL / NEEDS_HUMAN_REVIEW).
- Everything stored locally (SQLite + Markdown). Windows-safe CLI output.
- Templates packaged inside the wheel (works in non-editable installs).

## Available commands
`version`, `new`, `projects`, `show`, `plan`, `status`, `route`, `prompt`, `start`, `review`,
`handover`, `gate`, `done`, `reject`. See the README for full usage.

## MVP acceptance criteria covered
All 13 criteria from `MVP_SCOPE.md` — coverage table in [mvp-demo.md](mvp-demo.md):
create project, enter idea, base docs, ≥10 tasks, model assignment + reason, per-model prompt,
file reservation, conflict blocking, state transitions (doing/review/done/rejected), handover,
basic quality gate, local storage.

## Known limitations
- No model execution; prompts are manual copy-paste.
- No active Git integration (schema is Git-ready; Phase 4).
- Handover/gate deterministic; diff/test data shown as "Not recorded automatically in MVP.".
- `NEEDS_HUMAN_REVIEW` reported but not technically blocking; `done` only warns on missing
  handover/gate.
- Fixed-rule routing (no scoring), single-user, no UI/SaaS.

## Recommended next steps
Proceed to **Phase 4 — Git** (branch-per-task, file-change detection, forbidden-file diff check,
diff summary), then Phases 5–7 per `docs/roadmap.md`.

## Pre–Phase 4 checklist
- [x] All tests pass (`pytest` → 71 passed).
- [x] `.gitattributes` added; line endings normalized to LF.
- [x] Templates packaged inside `agentdesk/templates/` (verified in a non-editable install).
- [x] Non-editable install validated (`pip install .` → `plan`/`prompt`/`handover`/`gate` work).
- [x] README updated (what / problem / install / commands / flow / example / limitations / roadmap).
- [x] Release notes (this file) and MVP demo documented.
- [x] No out-of-scope features added in v0.1.
- [x] License: MIT (definitive).
- [x] Tag `v0.1.0` cut for the release.
