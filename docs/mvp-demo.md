# Agent Desk — MVP Demo

End-to-end walkthrough proving the v0.1 MVP. Everything is local-first and deterministic; no model
is executed and no Git is touched.

## Commands used

```bash
agentdesk new "Demo Agent Desk"
agentdesk plan "Demo Agent Desk" --force
agentdesk status "Demo Agent Desk"
agentdesk route "Demo Agent Desk" TASK-001
agentdesk prompt "Demo Agent Desk" TASK-001
agentdesk start "Demo Agent Desk" TASK-001
agentdesk handover "Demo Agent Desk" TASK-001 --summary "Initial architecture task prepared."
agentdesk gate "Demo Agent Desk" TASK-001
agentdesk done "Demo Agent Desk" TASK-001
agentdesk status "Demo Agent Desk"
```

State lives under `~/.agentdesk/` (override with `AGENTDESK_HOME`). The project folder (docs/,
tasks/, prompts/, handovers/, agentdesk.json) is created where you run `new` (or via `--path`).

## Expected results

- **new** → project created; folder scaffold + `agentdesk.json` + persisted state.
- **plan --force** → 5 base docs (`vision`, `scope`, `architecture`, `risks`, `success-criteria`)
  + 12 routed tasks written to `tasks/` and SQLite; only `TASK-001` is `ready`, the rest `blocked`.
- **status** → counts by state, active locks, next ready tasks, blocked tasks with pending deps.
- **route TASK-001** → `Recommended model: claude-code` (architecture needs reasoning) + reason.
- **prompt TASK-001** → `prompts/claude-code/TASK-001.md` written.
- **start TASK-001** → state `doing`; `docs/architecture.md` locked; prompt path shown.
- **handover --summary** → `handovers/TASK-001.md` written and persisted; manual summary recorded.
- **gate TASK-001** → `NEEDS_HUMAN_REVIEW` (high risk + architecture) — reported, not blocked.
- **done TASK-001** → state `done`; lock released; dependencies recomputed; `TASK-002` becomes `ready`.
- **status** → `TASK-001` done, `TASK-002` ready, no active locks.

Example gate outputs:

```text
Quality Gate: NEEDS_HUMAN_REVIEW
Reasons:
- Task is high risk.
- Task type is architecture.
Recommended action:
Review manually before marking as done.
```

```text
Quality Gate: FAIL          # e.g. on the still-blocked TASK-002
Failures:
- Handover not found.
- TASK-002 is blocked by TASK-001.
```

## MVP acceptance criteria coverage (MVP_SCOPE.md)

| # | Criterion | Command(s) | Covered |
|---|-----------|-----------|---------|
| 1 | Create a project via CLI | `new` | ✅ |
| 2 | Enter an idea / project name | `new "<idea>"` | ✅ |
| 3 | Generate base Markdown docs | `plan` → docs/*.md | ✅ |
| 4 | Generate ≥10 structured tasks | `plan` → 12 tasks | ✅ |
| 5 | Assign each task to a model | `plan` / `route` | ✅ |
| 6 | Explain the assignment reason | `route` (reason) | ✅ |
| 7 | Generate a per-model prompt | `prompt` (+ `--model`) | ✅ |
| 8 | Reserve files for a task | `start` (locks) | ✅ |
| 9 | Block a file conflict | `start` (conflict guard) | ✅ |
| 10 | Mark doing / review / done / rejected | `start` / `review` / `done` / `reject` | ✅ |
| 11 | Generate a handover | `handover` (+ `--summary`) | ✅ |
| 12 | Run a basic quality gate | `gate` | ✅ |
| 13 | Store everything locally | SQLite + Markdown | ✅ |

## Known limitations (MVP)

- Model execution is **manual** — Agent Desk generates copy-paste prompts; it does not call Codex,
  Claude Code, or a local model.
- No active Git integration (the Task schema is Git-ready; branch/diff handling is Phase 4).
- Handover/gate are deterministic: anything requiring diffs/test runs is written as
  "Not recorded automatically in MVP."
- `NEEDS_HUMAN_REVIEW` is reported but does not technically block `done`; `done` only *warns* when
  a handover or gate result is missing.
- Routing is fixed rules + manual override (no scoring); single-user; no UI/SaaS.
