# Agent Desk

> A local-first CLI that turns a project idea into an executable, routed plan and coordinates the
> work across **Codex**, **Claude Code**, and **local models** — with model-specific prompts,
> file-conflict control, handovers, and a deterministic quality gate.

**Agent Desk does not execute the models for you.** It prepares, routes, coordinates, and validates
manual AI-assisted work. The goal is not to replace Codex / Claude Code / your local model — it is
to *coordinate* them so the work stays controlled, cheaper, and consistent.

- **Version:** 0.4.1 · **Python:** 3.12+ · **License:** MIT
- **Status:** stable local-first cycle + local Git integration + advisory local-model assist +
  advanced quality gate + a real-project validation layer (v0.4.1).

---

## What it is

A command-line tool that sits *above* your AI models. You give it an idea; it:

1. produces a structured plan (vision / scope / architecture / risks / success-criteria docs **plus**
   a deterministic, routed task list),
2. tells you **which model** should do each task and **why**,
3. generates a copy-paste **prompt per model**,
4. prevents two tasks from touching the **same files**,
5. records a **handover** for continuity between sessions, and
6. runs a **quality gate** before you accept the work.

Everything runs on your machine. No network calls, no SaaS, no telemetry. State lives in a local
SQLite database; human-readable artifacts are written into the project folder.

## Who it is for

- Developers using **multiple AI coding assistants** who want one coordination layer above them.
- Solo builders who want **structure** (plan → route → prompt → gate) without adopting a heavy
  platform.
- Anyone who wants AI-assisted work to be **reproducible and reviewable** rather than ad-hoc.

## The problem it solves

Working with several AI models by hand is messy: projects start without a clear vision, prompts are
vague, expensive models get used for trivial work, context is lost between sessions, two models edit
the same files, and there is no handover or quality gate before accepting output. Agent Desk turns
that into a controlled, repeatable workflow.

## Key features

- **Deterministic planning** — an idea becomes base docs + a fixed 12-task blueprint, fully
  reproducible (no LLM calls in the engine).
- **Fixed-rule routing** — each task type + risk maps to a recommended model, an alternative, and a
  human-readable reason. Manual override is always available.
- **Per-model prompts** — Codex / Claude Code / local-model prompt files generated to disk for
  copy-paste.
- **Conflict guard** — file locks (DB-enforced) stop two tasks reserving the same file.
- **Dependency manager** — tasks move `blocked` ⇄ `ready` automatically as their dependencies reach
  `done`.
- **Handovers** — deterministic continuity documents written to `handovers/`.
- **Advanced quality gate** — six deterministic check groups (scope, state/deps, risk, Git diff,
  prompt, test, handover) producing `PASS / PASS_WITH_WARNINGS / FAIL / NEEDS_HUMAN_REVIEW`.
- **Local Git integration** — branch-per-task, change detection, and allowed/forbidden scope checks
  (local only; no remotes/push/PRs).
- **Advisory local-model assist** — optional summary / prompt-review / doc-check / handover-draft
  reports; never changes code or state.

## Quickstart

Requires **Python 3.12+**. See [docs/quickstart.md](docs/quickstart.md) for the full walkthrough.

```bash
# from the repo root
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"

agentdesk version           # confirm install
pytest                      # run the test suite (114 tests)
```

State is stored under `~/.agentdesk/` by default (override with `AGENTDESK_HOME`). Project folders
(`docs/`, `tasks/`, `prompts/`, `handovers/`, `agentdesk.json`) are created where you run `new`, or
via `--path`.

## Basic CLI usage

All commands below are real and implemented. `<project>` accepts the project id (slug) **or** its
name; model `M` is one of `codex`, `claude-code`, `local-model`.

```bash
agentdesk new "<idea>" [--name N] [--path DIR]       # create a project (folder + state)
agentdesk projects                                   # list projects
agentdesk show <project>                              # project details
agentdesk plan <project> [--force]                    # base docs + routed task list (idempotent)
agentdesk status <project>                            # state counts, locks, ready/blocked tasks
agentdesk route <project> <task> [--override M]       # show / override a task's model routing
agentdesk prompt <project> <task> [--model M]         # write a model-specific prompt file
agentdesk start <project> <task>                      # check deps + conflicts, lock files -> doing
agentdesk review <project> <task>                     # doing -> review (keeps locks)
agentdesk handover <project> <task> [--summary S]     # generate + persist a handover
agentdesk gate <project> <task>                       # advanced gate: structured checks + outcome
agentdesk test-result <project> <task> --result R     # record a test result (passed|failed|not-run|unknown)
agentdesk done <project> <task>                       # complete: release locks, unblock dependents
agentdesk reject <project> <task>                     # reject: release locks (no unblock)

# Local Git integration (optional; see docs/git-integration.md)
agentdesk git-status <project>                        # repo / branch / clean / changed files
agentdesk branch <project> <task>                     # create+checkout agent/TASK-XXX-<slug>
agentdesk diff <project> <task>                        # changed files + allowed/forbidden scope check

# Local model advisory assistance (optional; see docs/local-model.md)
agentdesk local-status                               # show local-model configuration
agentdesk local-assist <project> <task> --mode M     # M: summary|prompt-review|doc-check|handover-draft
```

### End-to-end example

```bash
agentdesk new "Demo Agent Desk"
agentdesk plan "Demo Agent Desk"
agentdesk status "Demo Agent Desk"
agentdesk route "Demo Agent Desk" TASK-001
agentdesk prompt "Demo Agent Desk" TASK-001
agentdesk start "Demo Agent Desk" TASK-001
# ... do the work in your chosen model by pasting the generated prompt ...
agentdesk handover "Demo Agent Desk" TASK-001 --summary "Initial architecture task prepared."
agentdesk gate "Demo Agent Desk" TASK-001
agentdesk done "Demo Agent Desk" TASK-001
agentdesk status "Demo Agent Desk"
```

## Architecture overview

Agent Desk is a set of small, deterministic engine modules behind a Typer CLI. SQLite owns mutable
state; Markdown/JSON on disk is the human-readable projection.

```text
idea ──> planner ──> docs + routed tasks ──> router ──> prompt_generator ──> (you run the model)
                          │                                                        │
                  dependency_manager                                          handover
                  conflict_guard (file locks)                                      │
                  git_integration (local diff/scope) ───────────────────────> quality_gate ──> PASS/FAIL/REVIEW
                          │
                       storage (SQLite)  ◄── single source of truth for every module
```

Full module-by-module explanation and a larger diagram: [docs/architecture.md](docs/architecture.md).

## The quality gate

The gate answers one question deterministically: *can this task's work be accepted?* It never runs
tests or models — it inspects observable data and combines six check groups:

| Check group        | What it looks at                                                       |
| ------------------ | ---------------------------------------------------------------------- |
| Scope              | acceptance criteria, allowed/forbidden files, objective length        |
| State & deps       | task state, unmet dependencies, file-lock conflicts                   |
| Risk               | high risk / architecture / dangerous overrides / sensitive files      |
| Diff (Git)         | branch association, forbidden changes, out-of-scope changes           |
| Prompt             | whether the effective model's prompt exists on disk                   |
| Test               | the **manually recorded** test result (`test-result`)                 |
| Handover           | presence and quality of the handover document                        |

Outcome precedence: **FAIL > NEEDS_HUMAN_REVIEW > PASS_WITH_WARNINGS > PASS**. Details in
[docs/advanced-quality-gate.md](docs/advanced-quality-gate.md).

## Real project validation (v0.4.1)

v0.4.1 adds **no new features**. It validates that the existing engine behaves correctly against
small but realistic local projects, instead of only synthetic task objects. It ships:

- runnable sample-project fixtures under
  [tests/fixtures/real_projects/](tests/fixtures/real_projects/) (a clean CLI app, a project with an
  intentionally broken test, and a project missing a README),
- integration tests in [tests/test_real_project_validation.py](tests/test_real_project_validation.py)
  covering a clean Python CLI project, broken tests, a missing README, dirty Git / out-of-scope
  edits, conflict-guard blocking, and handover output,
- documentation at
  [docs/validation/real-project-validation-v0.4.1.md](docs/validation/real-project-validation-v0.4.1.md).

No production `agentdesk/` modules were changed for the validation layer. See the doc for details.

## Current limitations

- **No model execution** — prompts are copy-paste; Agent Desk never calls Codex, Claude Code, or a
  local model to do task work. The local-model assist is *advisory* output only.
- **Git is local-only** — branch-per-task, change detection, and scope checks work locally. No
  remotes, push, PRs, or auto-commits. Projects without Git remain fully supported.
- **Deterministic by design** — handover/gate never run diffs or tests; test results are recorded
  manually via `test-result`.
- **`NEEDS_HUMAN_REVIEW` does not hard-block `done`** — `done` only *warns* when a handover or gate
  result is missing.
- Routing is **fixed rules + manual override** (no scoring). Single-user. No UI, no SaaS.

## Roadmap

| Phase | Status |
| ----- | ------ |
| Core local-first cycle (`new → plan → route → prompt → start → handover → gate → done`) | ✅ |
| Phase 4 — Local Git (branch/diff/scope, gate enrichment) | ✅ |
| Phase 5 — Advisory local-model assist | ✅ |
| Phase 6 — Advanced quality gate | ✅ |
| v0.4.1 — Real-project validation layer | ✅ |
| Phase 7 — UI (dashboard, task board, conflict warnings, prompt viewer) | Planned |

Full history and detail: [docs/roadmap.md](docs/roadmap.md).

## Project status

Actively developed, single-maintainer, local-first. The full coordination cycle is implemented and
covered by **114 passing tests**. The repository is in public-readiness hardening (documentation +
CI) ahead of a wider release.

## Documentation

- [docs/quickstart.md](docs/quickstart.md) — install, test, and a minimal real workflow
- [docs/architecture.md](docs/architecture.md) — module-by-module design
- [docs/advanced-quality-gate.md](docs/advanced-quality-gate.md) — the gate in depth
- [docs/git-integration.md](docs/git-integration.md) — local Git features
- [docs/local-model.md](docs/local-model.md) — advisory local-model assist
- [docs/validation/real-project-validation-v0.4.1.md](docs/validation/real-project-validation-v0.4.1.md) — v0.4.1 validation
- [docs/roadmap.md](docs/roadmap.md) · [docs/decisions.md](docs/decisions.md) · [docs/vision.md](docs/vision.md)
- [examples/README.md](examples/README.md) — example workflows
- [CHANGELOG.md](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
