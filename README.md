# Agent Desk

> Local-first tool that turns a project idea into an executable plan and distributes the work to
> the best available model — **Codex**, **Claude Code**, or a **local model** — with separated
> tasks, model-specific prompts, conflict control, and quality gates.
>
> The goal is **not** to replace Codex / Claude Code / local models. The goal is to **coordinate**
> them.

## Status

**v0.1 — Run D (Coordination).** Foundation + planning + routing/prompts, plus the coordination
layer: start tasks (with dependency + file-conflict checks), track state, lock files, and complete
tasks (releasing locks and unblocking dependents). Handover and quality gate land next
(see `docs/roadmap.md`).

What works today:

- `agentdesk new "<idea>"` - create a project (folder scaffold + `agentdesk.json` + persisted state)
- `agentdesk plan <project-id>` - generate base docs + >=10 routed tasks with dependencies/states
- `agentdesk route <project> <task> [--override <model>]` - show or override a task's model routing
- `agentdesk prompt <project> <task> [--model <model>]` - write a model-specific prompt file
- `agentdesk status <project>` - state counts, in-progress, active locks, next ready, blocked tasks
- `agentdesk start <project> <task>` - check deps + conflicts, lock files, move to `doing`
- `agentdesk done|review|reject <project> <task>` - complete / send to review / reject a task
- `agentdesk projects` - list projects (proves state persists across restarts)
- `agentdesk show <project-id>` - show project details
- `agentdesk version`

## Key decisions (MVP)

- **Local-first**, CLI, single-user. No SaaS, no desktop UI, no multi-user.
- **State** in SQLite; **documents** in Markdown.
- **Model execution is manual** — Agent Desk generates copy-paste prompts; it does not call models.
- **Routing** is a fixed rule table + manual override (no scoring yet).
- **Git is not actively integrated** in the MVP (deferred to Phase 4). The schema is Git-ready.

See `docs/decisions.md` for the full rationale.

## Install (dev)

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -e ".[dev]"
```

## Usage

```bash
agentdesk new "Review Assistant para restaurantes"
agentdesk projects
agentdesk show review-assistant-para-restaurantes
```

State is stored under `~/.agentdesk/` by default (override with the `AGENTDESK_HOME` env var).

## Run tests

```bash
pytest
```

## Project layout

```text
agentdesk/
  models.py            # Pydantic schemas + enums (states, types, risk, models, gate outcomes)
  storage/             # SQLite persistence layer
  router/              # fixed routing rules + risk model
  planner/             # idea -> docs -> tasks
  dependency_manager/  # task-to-task dependency logic (validate, eligibility, recompute states)
  conflict_guard/      # file-collision checks (allow / warn / block)
  state_machine/       # allowed task state transitions + validation
  prompt_generator/    # per-model prompts
  handover/            # handover.md generation           (later run)
  quality_gate/        # PASS/WARN/FAIL/NEEDS_HUMAN_REVIEW (later run)
  cli/                 # Typer CLI
  templating.py        # shared Jinja2 environment
templates/             # Jinja2 templates (docs + prompts + handover)
examples/              # sample project
tests/                 # pytest suite
docs/                  # vision, roadmap, architecture, decisions
```
