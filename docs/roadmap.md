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

## Run B — Planning slice
- `agentdesk plan` / `agentdesk tasks`: idea → vision/scope/architecture docs → ≥10 structured tasks
- `agentdesk show TASK-xxx`
- **Proof:** idea → docs + ≥10 tasks generated.

## Run C — Routing & prompts
- `agentdesk route TASK-xxx` (wire the router into the CLI; record decisions)
- `agentdesk prompt TASK-xxx --model <m>` → per-model prompt files
- **Proof:** every task routed with a reason; per-model prompts generated.

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
