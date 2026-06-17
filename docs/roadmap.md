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

## Run D — Coordination
- `agentdesk lock` / `start`: per-file reservation + conflict rule table (allow / warn / block)
- State transitions wired into the CLI
- **Proof:** a second task targeting the same file is blocked; states move correctly.

## Run E — Acceptance
- `agentdesk handover TASK-xxx` → handover.md
- `agentdesk gate TASK-xxx` → PASS / PASS_WITH_WARNINGS / FAIL / NEEDS_HUMAN_REVIEW
- End-to-end demo + full test suite
- **Proof:** all 13 MVP acceptance criteria pass.

## Deferred (post-MVP)
- **Phase 4 — Git**: branch-per-task, file-change detection, forbidden-file diff check, diff summary.
  (The schema is already Git-ready: `branch_name`, `commit_hash`, `base_branch`, `changed_files`,
  `pr_url`, `diff_summary`.)
- **Phase 5 — Local model**: real summarizer / handover generator / prompt reviewer / doc checker.
- **Phase 6 — Advanced quality gate**: test-check, diff-check, scope-check, risk-check.
- **Phase 7 — UI**: dashboard, task board, model-assignment view, conflict warnings, prompt viewer.
