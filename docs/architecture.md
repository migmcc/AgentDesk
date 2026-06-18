# Architecture

Agent Desk is a set of small, **deterministic** engine modules behind a Typer CLI. There are no LLM
calls in the engine and no network access: the same inputs always produce the same plan, routing,
prompts, and gate results. This is what makes the whole system testable.

This document explains, in plain language, what each module does and how a task flows through them.

## The big picture

```text
        you type a command
                │
                ▼
        ┌───────────────┐
        │      cli       │  Typer commands; the only user-facing surface
        └───────┬───────┘
                │ calls engine modules, reads/writes state
                ▼
  ┌──────────────────────────────────────────────────────────────────────┐
  │                          storage (SQLite)                             │
  │   single source of truth: projects, tasks, locks, routing,           │
  │   handovers, gate results, test results                              │
  └──────────────────────────────────────────────────────────────────────┘
                ▲            ▲             ▲              ▲           ▲
                │            │             │              │           │
   ┌────────────┴──┐  ┌──────┴─────┐  ┌────┴──────┐  ┌────┴─────┐  ┌──┴──────────┐
   │   planner     │  │   router   │  │ conflict_ │  │ handover │  │ quality_gate │
   │ idea -> docs  │  │ task -> the│  │  guard    │  │ continui-│  │ PASS / WARN /│
   │ + 12 tasks    │  │ model + why│  │ file locks│  │ ty doc   │  │ FAIL / REVIEW│
   └───────────────┘  └─────┬──────┘  └───────────┘  └──────────┘  └──────┬──────┘
                            │                                              │
                     ┌──────┴────────┐                          ┌─────────┴─────────┐
                     │ prompt_       │                          │  git_integration  │
                     │ generator     │                          │ local branch/diff │
                     │ per-model .md │                          │ + scope checks    │
                     └───────────────┘                          └───────────────────┘

   supporting modules: models (shared types) · dependency_manager (task order) ·
   state_machine (allowed transitions) · local_model (advisory assist) ·
   scaffold/templating (folders + Jinja2)
```

## How a task flows through the system

1. **`new`** — `scaffold` creates the project folder and `storage` persists the `Project`.
2. **`plan`** — `planner` instantiates a fixed 12-task blueprint, asks `router` for each task's
   model, validates the dependency graph with `dependency_manager`, and writes docs + task files.
3. **`route` / `prompt`** — `router` explains (or overrides) the model choice; `prompt_generator`
   renders the chosen model's prompt to disk.
4. **`start`** — `dependency_manager` confirms the task may run, `conflict_guard` confirms its files
   are free, then `storage` records file locks and the `state_machine` moves it to `doing`.
5. **(you do the work)** — paste the generated prompt into Codex / Claude Code / your local model.
6. **`handover`** — `handover` writes a continuity document.
7. **`gate`** — `quality_gate` combines scope, dependencies, locks, risk, Git diff, prompt, test, and
   handover signals into one outcome.
8. **`done`** — locks are released and `dependency_manager` recomputes which tasks become `ready`.

## Module reference

### `models`
The shared contract. Pydantic schemas and enums (`Task`, `Project`, `RoutingDecision`, `FileLock`,
`Handover`, `GateResult`, `TestResult`, plus the `TaskState` / `TaskType` / `RiskLevel` / `Model` /
`GateOutcome` enums). Every other module speaks in these types.

### `storage`
The single source of truth, built on the standard-library `sqlite3`. Each table keeps a few indexed
key columns plus a JSON blob of the full model, which keeps the schema small and forward-compatible.
The conflict guard's locking primitive is a database-level `UNIQUE(project_id, file_path)`
constraint — the database itself prevents two tasks from reserving the same file.

### `planner`
Turns an idea into base Markdown docs (vision / scope / architecture / risks / success-criteria) and
a deterministic, ordered list of 12 tasks from a fixed blueprint. It calls `router` to set each
task's recommended model and `dependency_manager` to validate the graph and set initial
`ready` / `blocked` states. No LLM is involved, so the output is fully reproducible.

### `router`
A fixed rule table mapping each `TaskType` (and, for a few types, the `RiskLevel`) to a recommended
model, an alternative, and a human-readable reason. It also encodes which model may *execute* a task
at a given risk level, and supports a persisted manual override. No scoring — predictability first.

### `prompt_generator`
Renders a per-model prompt file (`prompts/codex/…`, `prompts/claude-code/…`,
`prompts/local-model/…`) from the task and project context, adding a dependency-warning section when
the task is blocked. It only writes text files; it never executes a model.

### `dependency_manager`
Owns task **order** (as opposed to file collisions). It validates the dependency graph (catching
unknown dependencies, self-dependencies, and cycles), determines which tasks are eligible to start,
and recomputes `blocked` ⇄ `ready` states as dependencies reach `done`.

### `conflict_guard`
Owns file **collisions**. Before a task starts, it compares the task's allowed files against
currently held locks and returns allow / warn / block. It is a pure read over the lock store; the
locks themselves are created by `start`.

### `state_machine`
Defines the allowed task state transitions (e.g. `ready → doing → review → done`) and refuses invalid
ones with a clear error, so task lifecycles cannot get into impossible states.

### `git_integration`
Local-only Git helpers built on `subprocess` — no remotes, push, PRs, or auto-commits. It detects
whether the project folder is a repo root, reads the current branch and changed files, creates a
branch-per-task (`agent/TASK-XXX-<slug>`), and compares changed files against the task's
allowed/forbidden lists. Its findings feed the quality gate's diff check. Projects without Git remain
fully supported.

### `handover`
Builds and writes a deterministic continuity document (`handovers/TASK-XXX.md`) from observable task
data: what the task was, its risk, and the next recommended task. Anything that would require diffs
or test runs is recorded as a placeholder rather than guessed.

### `quality_gate`
The acceptance decision. It runs six deterministic check groups — scope, state/dependencies, risk,
diff (Git), prompt, test, and handover — and emits structured `[PASS]/[WARN]/[FAIL]/[REVIEW]` lines
plus failures, warnings, human-review reasons, and a recommended action. Test results are **recorded
manually** (`test-result`); the gate never runs tests or models. Outcome precedence is
**FAIL > NEEDS_HUMAN_REVIEW > PASS_WITH_WARNINGS > PASS**.

### `local_model`
Optional, advisory assistance from a local model (configured via environment variables). Modes:
`summary`, `prompt-review`, `doc-check`, `handover-draft`. Providers: `fake` (deterministic, used in
tests) and `openai-compatible` / `ollama`. It writes reports to `reports/` and **never** changes
code, task state, the official handover, or Git, and is never required for a gate to pass.

### `cli`
The Typer application — the only user-facing surface. Each command resolves the project, calls the
relevant engine modules, persists results through `storage`, and prints Windows-safe output via Rich.

## Source of truth

- **SQLite** owns mutable state: projects, tasks, task states, file locks, routing decisions,
  handovers, gate results, and test results.
- **Markdown / JSON on disk** is the human-readable projection: the `agentdesk.json` manifest plus
  generated `docs/`, `tasks/`, `prompts/`, `handovers/`, and `reports/`.

When the two could drift, SQLite is authoritative for state and the on-disk files are regenerated
artifacts.

## Design principles

- **Deterministic engine** — no LLM calls or network access inside the modules; reproducible output.
- **Local-first** — all state stays on your machine under `AGENTDESK_HOME`.
- **Clear ownership** — order is `dependency_manager`; collisions are `conflict_guard`; acceptance is
  `quality_gate`; truth is `storage`.
- **Fixed rules over scoring** — routing and planning are predictable and debuggable.

See [decisions.md](decisions.md) for the recorded technical decisions and
[roadmap.md](roadmap.md) for how the phases were built.
