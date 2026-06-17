# Advanced Quality Gate (Phase 6)

`agentdesk gate <project> <task>` evaluates whether a task is safe enough to accept. It is
**deterministic** and **never runs tests or models** — it only reads data Agent Desk already has
(task, dependencies, locks, routing, handover, Git diff, and a manually recorded test result).

## Levels

Each check line is tagged with a level:

- `[PASS]` — fine.
- `[WARN]` — a non-blocking warning (advisory).
- `[FAIL]` — a hard blocker.
- `[REVIEW]` — a reason to have a human review the task.

Overall outcome precedence: **FAIL > NEEDS_HUMAN_REVIEW > PASS_WITH_WARNINGS > PASS**.

| Outcome | Meaning |
|---------|---------|
| `PASS` | No failures, warnings, or review reasons. |
| `PASS_WITH_WARNINGS` | Only warnings — review them, but you may proceed. |
| `FAIL` | One or more hard blockers; resolve before accepting. |
| `NEEDS_HUMAN_REVIEW` | A human should review (risk/architecture/etc.) before `done`. |

## Check groups

1. **Scope** — acceptance criteria (missing → FAIL); allowed files (missing on code tasks → WARN);
   high-risk without forbidden files → WARN; empty/short description → WARN.
2. **State & dependencies** — blocked or unmet dependency → FAIL; file-lock conflict → FAIL; a state
   that can't be gated (not `doing`/`review`) → FAIL.
3. **Risk** — high risk / architecture / non-low refactor / quality-gate / dangerous override
   (high-risk → local-model) / changed files touching sensitive areas → REVIEW.
4. **Diff (Git)** — forbidden file changed → FAIL; missing associated branch → FAIL; change outside
   `allowed_files` → WARN; no branch on a code task → WARN; no repo / not a repo root → WARN
   (never a crash). The project folder must be its own repo root.
5. **Prompt** — prompt present for the effective model → PASS; missing → WARN.
6. **Test** — uses the manually recorded test result (see below). `passed` → PASS; `failed` → FAIL;
   `not-run` / `unknown` / not recorded → WARN (documentation/handover/research/review tasks do not
   require tests).
7. **Handover** — missing → FAIL; placeholder summary → WARN.

## Recording tests

Agent Desk does **not** run tests. Record the result yourself:

```bash
agentdesk test-result <project> <task> --command "pytest" --result passed
agentdesk test-result <project> <task> --command "pytest" --result failed --notes "1 failing test"
```

Results: `passed`, `failed`, `not-run`, `unknown`. One current result per task; the gate reads it.

## Example

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

## Limitations

- The gate never executes tests, code, or models; no CI, no GitHub API.
- Test results are recorded manually.
- Git diff requires the project folder to be its own repository root.
- A local-model report is advisory and is never required for a PASS.
