# Agent Desk — Roadmap

The MVP compresses Phases 1–3 of the original intake roadmap into incremental runs. Git, local-model
execution, advanced quality gate, and UI are explicitly deferred.

## Run A — Foundation ✅ (this run)
- Repo scaffolding + packaging
- Pydantic data model + enums (states, types, risk, models, gate outcomes)
- SQLite storage layer (projects, tasks, locks, handovers, gate results, routing decisions)
- Task state machine
- Fixed routing rules + risk model
- Initial Jinja2 templates (docs, prompts, handover)
- Minimal CLI (`new`, `projects`, `show`, `version`)
- Initial tests
- **Proof:** a project initializes and state persists across a restart.

## Run B — Planning slice ✅
- `agentdesk plan <project>`: idea → vision/scope/architecture/risks/success-criteria docs →
  12 structured, routed tasks (deterministic blueprint; no LLM calls)
- Tasks persisted to SQLite; docs + `tasks/TASK-XXX.md` written to disk
- States set from dependencies: no deps → `ready`, has deps → `blocked`
- Idempotent (`--force` to regenerate)
- **Dependency manager** (`agentdesk/dependency_manager/`): task-to-task dependency logic across
  models — graph validation (unknown deps / self-deps / cycles), eligibility, topological order,
  and `recompute_states()` that moves tasks `blocked` ⇄ `ready` as dependencies reach `done`.
  Tasks may declare `depends_on:` (alias of `dependencies`).
- **Proof:** idea → 5 docs + 12 tasks generated; repeatable without corruption.
- Wired into the CLI in a later run: calling `recompute_states` on task-state changes (the engine
  is ready; the `done`/`start` commands that trigger it land in Run D).

## Run C — Routing & prompts ✅
- `agentdesk route <project> <task>`: show the routed model + reason; persisted per task
- `agentdesk route <project> <task> --override <model>`: manual override (keeps the original
  recommendation; reason "Manual override by user"); high-risk→local warns but is allowed
- `agentdesk prompt <project> <task>`: render the effective model's prompt to
  `prompts/<model-dir>/TASK-XXX.md`
- `agentdesk prompt <project> <task> --model <m>`: ad-hoc prompt for another model **without**
  changing saved routing
- Blocked tasks warn on the CLI and get a "Dependency warning" section in the prompt
- **Proof:** every task routed with a reason; per-model prompts generated; overrides persisted.

## Run D — Coordination ✅
- `agentdesk status <project>`: state counts, in-progress tasks, active locks, next ready tasks,
  blocked tasks with their pending dependencies
- `agentdesk start <project> <task>`: checks dependencies (must be `ready`) **and** file conflicts,
  locks the task's allowed files, moves to `doing`
- `agentdesk done <project> <task>`: from `doing`/`review` → `done`, releases locks, runs
  `recompute_states`, reports newly-ready tasks
- `agentdesk review <project> <task>`: `doing` → `review`, **keeps** locks, does not unblock dependents
- `agentdesk reject <project> <task>`: → `rejected`, releases locks, does not unblock dependents
- **state_machine** module: explicit allowed transitions; invalid ones are refused with a clear error
- **conflict_guard** module: allow / warn / block based on SQLite file locks (controls *collisions*;
  the dependency manager controls *order*)
- Windows-safe CLI output (ASCII only; no cp1252-incompatible glyphs)
- **Proof:** a second task targeting a locked file is blocked; a dependent only becomes `ready` when
  all its dependencies are `done`; invalid transitions are refused.

## Run E — Acceptance ✅ (MVP complete)
- `agentdesk handover <project> <task> [--summary "..."]` → `handovers/TASK-XXX.md` + persisted;
  deterministic ("Not recorded automatically in MVP." for diff/test data)
- `agentdesk gate <project> <task>` → PASS / PASS_WITH_WARNINGS / FAIL / NEEDS_HUMAN_REVIEW
  (deterministic rules over handover / dependencies / locks / criteria / risk)
- `agentdesk done` warns (does not block) when a handover or gate result is missing
- End-to-end demo documented in `docs/mvp-demo.md`; all 13 MVP acceptance criteria covered
- **Proof:** full `new → plan → route → prompt → start → handover → gate → done → unlock` flow.
- **Proof:** all 13 MVP acceptance criteria pass.

## Phase 4 — Git (local) ✅
- `git-status`, `branch` (agent/TASK-XXX-slug, persisted), `diff` (changed files + scope check)
- Quality gate enriched with Git findings: forbidden change → FAIL; out-of-scope / no-branch /
  no-repo → warning. Projects without Git remain fully supported.
- Functional Git-ready fields: `branch_name`, `changed_files`, `diff_summary`. Local only — no
  remotes, push, PRs, or auto-commits. See `docs/git-integration.md`.

## Phase 5 — Local model (advisory) ✅
- `local-status` (config check) and `local-assist <project> <task> --mode <mode>` with modes
  `summary`, `prompt-review`, `doc-check`, `handover-draft`; output to `reports/`.
- Providers: `fake` (deterministic, for tests) and `openai-compatible` (Ollama via its `/v1`).
- Advisory only: never changes code, task state, the official handover, or Git; output is never
  required for a gate PASS. See `docs/local-model.md`.

## Phase 6 — Advanced quality gate ✅
- `agentdesk gate` now runs six deterministic check groups — scope, state/dependencies, risk, diff
  (Git), prompt, test, handover — and emits structured `[PASS]/[WARN]/[FAIL]/[REVIEW]` lines plus
  failures / warnings / human-review reasons and a recommended action.
- `agentdesk test-result <project> <task> --result <passed|failed|not-run|unknown>` records a test
  result (Agent Desk never runs tests). `passed` → PASS, `failed` → FAIL, otherwise a warning.
- Forbidden file changed → FAIL; out-of-scope change → warning; high risk / architecture → review.
  Projects without Git stay supported. See `docs/advanced-quality-gate.md`.

## Deferred (post-MVP)
- **Phase 7 — UI**: dashboard, task board, model-assignment view, conflict warnings, prompt viewer.
