# Agent Desk — Release v0.4.0

## Version
`0.4.0` — Advanced Quality Gate (builds on v0.3.0 local-model assist, v0.2.0 Git, and the v0.1.0 MVP).

## Release status
Stable. 106 tests pass. The gate is deterministic and validated with temporary Git repos and the
fake/real local-model paths from earlier phases.

## What's new
`agentdesk gate` becomes a structured, multi-check validator, and tasks can carry a manually
recorded test result.

> The advanced quality gate is deterministic. It does not execute tests, call models, use CI, call
> GitHub APIs, create PRs, push, merge, or modify code automatically.

## Included functionality
- Advanced deterministic quality gate with grouped checks.
- `agentdesk test-result` to record a manual test result.
- Structured gate output with `[PASS]` / `[WARN]` / `[FAIL]` / `[REVIEW]` per-check levels.
- Persistent test results (one current result per task).
- Advanced quality gate documentation (`docs/advanced-quality-gate.md`).

## New commands
```bash
agentdesk gate <project> <task>
agentdesk test-result <project> <task> --result <passed|failed|not-run|unknown> [--command ...] [--notes ...]
```

## Checks added
1. **Scope** — acceptance criteria (missing → FAIL), allowed files, high-risk forbidden files, short
   description.
2. **State & dependencies** — blocked / unmet dependency / lock conflict / non-gateable state → FAIL.
3. **Risk** — high / architecture / non-low refactor / quality-gate / dangerous override / sensitive
   files → REVIEW.
4. **Diff (Git)** — forbidden change → FAIL, missing branch → FAIL, out-of-scope change → WARN,
   no branch on code task → WARN, no repo → WARN.
5. **Prompt** — present for the effective model → PASS, missing → WARN.
6. **Test** — recorded `passed` → PASS, `failed` → FAIL, otherwise WARN (docs/handover/research/review
   do not require tests).
7. **Handover** — missing → FAIL, placeholder summary → WARN.

## Precedence rules
`FAIL > NEEDS_HUMAN_REVIEW > PASS_WITH_WARNINGS > PASS`.

## Example output
```text
Quality Gate: PASS_WITH_WARNINGS

Checks:
[PASS] Acceptance criteria found
[PASS] Dependencies satisfied
[PASS] Git repository detected
[WARN] Changed file outside allowed scope: src/config.py.
[PASS] No forbidden files changed
[PASS] Risk level: medium
[WARN] Tests not recorded.
[PASS] Handover found

Failures:
- none

Warnings:
- Changed file outside allowed scope: src/config.py.
- Tests not recorded.

Human review reasons:
- none

Recommended action:
Review warnings before marking task as done.
```

## Known limitations
- Deterministic only (see boundary statement above); test results are recorded manually.
- Git diff requires the project folder to be its own repository root.
- A local-model report is advisory and never required for a PASS.
- Fixed-rule routing (no scoring); single-user; no UI/SaaS.

## Validation checklist
- [x] `feat/advanced-quality-gate` merged into `main` with `--no-ff`.
- [x] Version bumped to `0.4.0` (pyproject + `agentdesk.__version__`).
- [x] `pytest` → 106 passed.
- [x] CHANGELOG updated; README, roadmap, and `docs/advanced-quality-gate.md` reflect v0.4.0.
- [x] `docs/release-v0.1.md` … `docs/release-v0.3.md` preserved as history.
- [x] Tag `v0.4.0` cut.

## Next steps
- **Phase 7 — UI** (optional): dashboard, task board, model-assignment view, conflict warnings,
  prompt viewer.
- Optional: add a Git remote and `git push --follow-tags` if/when the project goes public.
