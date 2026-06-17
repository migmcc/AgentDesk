# Agent Desk

> Local-first tool that turns a project idea into an executable plan and distributes the work to
> the best available model — **Codex**, **Claude Code**, or a **local model** — with separated
> tasks, model-specific prompts, conflict control, and quality gates.

**Agent Desk does not execute Codex, Claude Code, or local models in v0.1. It prepares, routes,
coordinates, and validates manual AI-assisted work.** The goal is not to replace the models — it is
to coordinate them.

## What it is

A CLI that sits *above* your AI models. You give it an idea; it produces a structured plan
(vision/scope/architecture docs + a routed task list), tells you which model should do each task and
why, generates a copy-paste prompt per model, prevents two tasks from touching the same files, and
runs a basic quality gate before you accept work.

## The problem it solves

Working with several AI models by hand is messy: projects start without a clear vision, prompts are
vague, expensive models get used for trivial work, context is lost between sessions, multiple models
edit the same files, and there is no handover or quality gate before accepting AI output. Agent Desk
makes that workflow controlled, cheaper, and consistent.

## Status — v0.1 (MVP complete)

The full local-first cycle works:

```text
new → plan → route → prompt → start → handover → gate → done → unlock next task
```

All 13 MVP acceptance criteria are covered — see [docs/mvp-demo.md](docs/mvp-demo.md) and
[docs/release-v0.1.md](docs/release-v0.1.md).

## Install

Requires Python 3.12+.

```bash
# from the repo root
python -m venv .venv
# Windows
.venv\Scripts\activate
# normal install
pip install .
# or, for development
pip install -e ".[dev]"
```

State is stored under `~/.agentdesk/` by default (override with the `AGENTDESK_HOME` env var).
Project folders (docs/, tasks/, prompts/, handovers/, agentdesk.json) are created where you run
`new`, or via `--path`.

## Commands

```bash
agentdesk version                                   # version + home dir
agentdesk new "<idea>" [--name N] [--path DIR]      # create a project
agentdesk projects                                  # list projects
agentdesk show <project>                            # project details
agentdesk plan <project> [--force]                  # docs + routed task list (idempotent)
agentdesk status <project>                          # states, locks, next ready, blocked tasks
agentdesk route <project> <task> [--override M]     # show / override a task's model routing
agentdesk prompt <project> <task> [--model M]       # write a model-specific prompt file
agentdesk start <project> <task>                    # check deps + conflicts, lock files, -> doing
agentdesk review <project> <task>                   # doing -> review (keeps locks)
agentdesk handover <project> <task> [--summary S]   # generate + persist a handover
agentdesk gate <project> <task>                     # PASS / PASS_WITH_WARNINGS / FAIL / NEEDS_HUMAN_REVIEW
agentdesk done <project> <task>                      # complete: release locks, unblock dependents
agentdesk reject <project> <task>                   # reject: release locks (no unblock)
```

`<project>` accepts the project id (slug) **or** its name. `M` (model) is one of `codex`,
`claude-code`, `local-model`.

## Recommended flow

1. `new` an idea, then `plan` it into docs + tasks.
2. `status` to see what is `ready`.
3. For a ready task: `route` (check/adjust model) → `prompt` (generate the mission) → `start`
   (lock files, go `doing`).
4. Do the work in your chosen model by pasting the generated prompt (manual in v0.1).
5. `handover` (record a summary) → `gate` (validate) → `done` (accept, unlock dependents).

## End-to-end example

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

## Run tests

```bash
pytest
```

## Limitations (v0.1)

- **No model execution** — prompts are copy-paste; Agent Desk never calls Codex, Claude Code, or a
  local model.
- **No active Git integration** — the Task schema is Git-ready, but branch/diff handling is Phase 4.
- Handover and gate are **deterministic**: anything needing diffs/test runs is written as
  "Not recorded automatically in MVP.".
- `NEEDS_HUMAN_REVIEW` is reported but does not technically block `done`; `done` only *warns* when a
  handover or gate result is missing.
- Routing is fixed rules + manual override (no scoring). Single-user. No UI, no SaaS.

## Roadmap (post-MVP)

- **Phase 4 — Git**: branch-per-task, file-change detection, forbidden-file diff check, diff summary.
- **Phase 5 — Local model**: real summarizer / handover / prompt-review / doc-check support tasks.
- **Phase 6 — Advanced quality gate**: test-check, diff-check, scope-check, risk-check.
- **Phase 7 — UI**: dashboard, task board, model-assignment view, conflict warnings, prompt viewer.

See [docs/roadmap.md](docs/roadmap.md) for the full plan.

## Project layout

```text
agentdesk/
  models.py            # Pydantic schemas + enums (states, types, risk, models, gate outcomes)
  config.py            # AGENTDESK_HOME / db path
  scaffold.py          # slug + project folder creation
  templating.py        # shared Jinja2 environment
  storage/             # SQLite persistence (projects, tasks, locks, routing, handovers, gates)
  router/              # fixed routing rules + risk model
  planner/             # idea -> docs -> tasks (deterministic blueprint)
  dependency_manager/  # task-to-task dependency logic (validate, eligibility, recompute states)
  conflict_guard/      # file-collision checks (allow / warn / block)
  state_machine/       # allowed task state transitions
  prompt_generator/    # per-model prompts
  handover/            # handover.md generation
  quality_gate/        # PASS / PASS_WITH_WARNINGS / FAIL / NEEDS_HUMAN_REVIEW
  templates/           # Jinja2 templates (docs + prompts + handover), packaged
  cli/                 # Typer CLI
examples/              # sample project
tests/                 # pytest suite
docs/                  # vision, roadmap, architecture, decisions, mvp-demo, release-v0.1
```

## License

MIT (provisional — see [docs/decisions.md](docs/decisions.md)).
