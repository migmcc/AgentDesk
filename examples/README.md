# Examples

Honest, runnable example workflows for Agent Desk. Every command shown here is implemented today —
nothing in this folder describes planned or imaginary behavior. If you have not installed Agent Desk
yet, start with [../docs/quickstart.md](../docs/quickstart.md).

> Tip: keep these experiments out of your real state by pointing `AGENTDESK_HOME` at a temporary
> folder first (e.g. `export AGENTDESK_HOME="$PWD/.agentdesk-demo"`).

## Contents

- [`sample-project/`](sample-project/) — a placeholder folder describing what `new` + `plan`
  generate on disk.
- The **real-project validation fixtures** under
  [`../tests/fixtures/real_projects/`](../tests/fixtures/real_projects/) — small, genuinely runnable
  sample projects used by the v0.4.1 validation suite (see below).

## Example 1 — Plan an idea and read the routing

Turn an idea into docs + a routed task list, then see which model each task is assigned to and why.

```bash
agentdesk new "Review Assistant for restaurants"
agentdesk plan "Review Assistant for restaurants"
agentdesk status "Review Assistant for restaurants"
agentdesk route "Review Assistant for restaurants" TASK-001   # architecture task -> claude-code
agentdesk route "Review Assistant for restaurants" TASK-002   # setup task        -> codex
```

What you learn: planning is deterministic (always 12 tasks from the fixed blueprint), and routing is
a fixed rule table — architecture/refactor lean to Claude Code, objective implementation/setup lean
to Codex, docs/handover lean to the local model.

## Example 2 — Take one task through the full cycle

```bash
agentdesk prompt "Review Assistant for restaurants" TASK-001   # write the model prompt to disk
agentdesk start  "Review Assistant for restaurants" TASK-001   # lock files, move to "doing"
# ... do the work in your chosen model using the generated prompt ...
agentdesk handover "Review Assistant for restaurants" TASK-001 --summary "Architecture drafted."
agentdesk gate   "Review Assistant for restaurants" TASK-001   # structured checks + outcome
agentdesk done   "Review Assistant for restaurants" TASK-001   # release locks, unblock dependents
```

What you learn: Agent Desk coordinates the work but never executes the model — step 3 is yours.

## Example 3 — Override the routed model

```bash
# Force TASK-001 onto Codex instead of the recommended model (the recommendation is preserved).
agentdesk route "Review Assistant for restaurants" TASK-001 --override codex
agentdesk prompt "Review Assistant for restaurants" TASK-001    # now renders the Codex prompt
```

What you learn: overrides are persisted and honored by later commands; assigning a high-risk task to
the local model warns but is allowed.

## Example 4 — See the conflict guard block a collision

```bash
agentdesk start "Review Assistant for restaurants" TASK-003   # locks src/**
# A second task that also wants src/** cannot start while those files are locked:
agentdesk start "Review Assistant for restaurants" TASK-004   # -> "File conflict detected"
```

What you learn: file locks (enforced by the database) stop two tasks from touching the same files.

## Example 5 — How the validation fixtures map to real projects

The v0.4.1 validation layer exercises the engine against real, runnable projects. You can browse and
even run those fixtures directly:

| Fixture | Location | Demonstrates |
| --- | --- | --- |
| Clean Python CLI | [`../tests/fixtures/real_projects/clean_cli/`](../tests/fixtures/real_projects/clean_cli/) | a well-formed project that passes the gate |
| Broken tests | [`../tests/fixtures/real_projects/broken_tests/`](../tests/fixtures/real_projects/broken_tests/) | a failing test that drives a gate `FAIL` |
| Missing README | [`../tests/fixtures/real_projects/missing_readme/`](../tests/fixtures/real_projects/missing_readme/) | a project whose missing README is detected and tracked |

```bash
# Each fixture is a genuine project; run its own tests directly:
python -m pytest tests/fixtures/real_projects/clean_cli/tests -q     # passes
python -m pytest tests/fixtures/real_projects/broken_tests/tests -q  # fails on purpose
```

The integration tests that drive Agent Desk against these fixtures live in
[`../tests/test_real_project_validation.py`](../tests/test_real_project_validation.py), and the
scenario-by-scenario write-up is in
[`../docs/validation/real-project-validation-v0.4.1.md`](../docs/validation/real-project-validation-v0.4.1.md).

> Note: `tests/fixtures/` is excluded from Agent Desk's own test collection
> (`norecursedirs = ["fixtures"]`), so the intentionally broken fixture never fails the main suite.

## A note on honesty

Agent Desk **prepares, routes, coordinates, and validates** AI-assisted work. It does not call Codex,
Claude Code, or a local model to perform task work — the model step is always manual. The
`local-assist` command produces *advisory* reports only and never changes code or task state.
