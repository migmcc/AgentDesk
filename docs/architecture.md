# Agent Desk — Architecture

## Suggested Stack
- Python 3.12+
- Typer (CLI), Rich (terminal output)
- Pydantic v2 (schemas)
- SQLite via the stdlib `sqlite3` (local state)
- Jinja2 (templates)
- GitPython — **optional extra**, deferred to Phase 4 (no Git runtime dependency in the MVP)

## Folder Structure
```text
agent-desk/
  agentdesk/
    models.py            # Pydantic schemas + enums
    config.py            # AGENTDESK_HOME / db path resolution
    scaffold.py          # slugify + on-disk project folder creation
    storage/             # SQLite persistence
    router/              # fixed routing rules + risk model
    planner/             # idea -> docs -> tasks            (Run B)
    conflict_guard/      # per-file locking + rule table    (Run D)
    prompt_generator/    # per-model prompts                (Run C)
    handover/            # handover.md                      (Run E)
    quality_gate/        # gate outcomes                    (Run E)
    cli/                 # Typer app
  templates/             # Jinja2: docs, prompts, handover
  examples/sample-project/
  tests/
  docs/
```

## Main Modules
- **models** — the shared contract between every engine module.
- **storage** — single source of truth for state and locks; the conflict guard's locking primitive
  is a DB-level UNIQUE(project_id, file_path) constraint.
- **router** — pure functions mapping (task type, risk) → recommended model + reason + alternative.
- **cli** — the only user-facing surface in the MVP.

## Data Flow (MVP)
```text
idea --(cli new)--> Project --(storage)--> SQLite + on-disk folder/agentdesk.json
                                   |
                          (Run B) planner --> docs + tasks
                                   |
                          (Run C) router --> RoutingDecision; prompt_generator --> prompt files
                                   |
                          (Run D) conflict_guard --> FileLock (UNIQUE-enforced)
                                   |
                          (Run E) handover --> Handover; quality_gate --> GateResult
```

## Source of Truth
- **SQLite** owns mutable state: projects, tasks, task states, file locks, routing decisions,
  handovers, gate results.
- **Markdown / JSON on disk** is the human-readable projection: `agentdesk.json` manifest plus the
  generated `docs/`, `tasks/`, `prompts/`, `handovers/` (populated from Run B onward).

## Technical Decisions
See docs/decisions.md.

## Technical Risks
- Conflict-guard correctness (mitigated by DB-level uniqueness + tests).
- SQLite ↔ Markdown drift (mitigated by a clear per-data-type ownership rule above).
- Windows path handling (no Git in MVP removes the main offender).

## Alternatives Considered
- Per-column SQL schema vs JSON-blob-per-row → chose JSON blob + indexed key columns for
  forward-compatibility with evolving schemas (e.g. Git-ready fields).
- Scoring-based routing → deferred; fixed rules first for predictability and debuggability.
