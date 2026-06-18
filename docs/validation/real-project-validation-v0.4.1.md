# Real-Project Validation (v0.4.1)

## Purpose

v0.4.1 adds **no new features**. Its single goal is to *validate* that the existing Agent Desk
engine behaves correctly when pointed at small but realistic local projects, rather than only at
synthetic, hand-built `Task` objects.

The validation layer wires the existing modules together over checked-in sample projects and
asserts the outcomes are correct **and deterministic**. If a scenario had revealed a genuine
integration gap, the fix would be a minimal change to the relevant module — not a redesign.

## What is reused (and what is not)

The validation exercises the real engine end to end. Nothing here re-implements engine logic:

| Module             | Role in validation                                                        |
| ------------------ | ------------------------------------------------------------------------- |
| `planner`          | Generates the deterministic blueprint task list / docs for a project.     |
| `router`           | Picks the recommended model per task (fixed rules).                       |
| `conflict_guard`   | Detects file-lock collisions between tasks (simulated conflict scenario). |
| `git_integration`  | Inspects a real Git work tree: branch, clean/dirty, changed files, scope. |
| `handover`         | Builds and writes the continuity document for a finished task.            |
| `quality_gate`     | Combines all of the above into a single PASS / WARN / FAIL / REVIEW result. |

Out of scope, exactly as in the core engine: no test execution by Agent Desk itself (test results
are recorded manually), no network, no GitHub API, no LLM calls, no auto-commit/push.

## Fixtures

Realistic sample projects live under [`tests/fixtures/real_projects/`](../../tests/fixtures/real_projects/).
Each is a genuine, runnable Python project (not a stub):

| Fixture          | Shape                                              | Used to validate                          |
| ---------------- | ------------------------------------------------- | ----------------------------------------- |
| `clean_cli`      | Working to-do CLI: README, `src/`, passing tests. | Clean Python CLI project (happy path).    |
| `broken_tests`   | `calc` lib with an **intentional** bug.           | Project with broken tests.                |
| `missing_readme` | `wordcount` lib, **no** `README.md`.              | Project missing a README.                 |

Because these fixtures contain their own `test_*.py` files, `tests/fixtures/` is excluded from
Agent Desk's own collection (`norecursedirs = ["fixtures"]` in `pyproject.toml`). The validation
suite runs a fixture's tests in an **isolated subprocess** so an intentionally broken fixture never
fails the parent suite.

## Scenarios

All scenarios are in [`tests/test_real_project_validation.py`](../../tests/test_real_project_validation.py).
Each copies a fixture into a temp directory, registers it as an Agent Desk project, and drives the
real modules.

1. **Clean Python CLI project** — `clean_cli` in a clean Git repo with an in-scope change, an
   associated branch, a recorded passing test, a generated prompt and a handover. The quality gate
   returns `PASS` with no failures and no human-review reasons.

2. **Project with broken tests** — the `broken_tests` fixture is *actually run* in a subprocess to
   confirm it fails (proving the fixture is real), then that failing result is recorded through
   Agent Desk's manual `TestResult` mechanism. The gate returns `FAIL` and cites the failing test.

3. **Project with missing README** — a documentation task targets `README.md` for `missing_readme`.
   `git_integration` confirms the file is absent at the start and is picked up as an in-scope change
   once written, and the routed model for the doc task is the local model (token-saving rule).

4. **Dirty Git state / simulated conflict** — two complementary checks on `clean_cli`:
   - *Dirty Git*: an out-of-scope and a forbidden file are modified in the work tree;
     `git_integration` reports the repo as not clean and the gate `FAIL`s on the forbidden change.
   - *Simulated conflict*: two tasks reserve the same file; `conflict_guard` `BLOCK`s the second and
     the gate reports the lock conflict as a failure.

5. **Project requiring handover output** — `handover.generate_handover` writes
   `handovers/TASK-XXX.md` to disk for a finished task; the gate then finds the handover and the
   document contains the task's real data.

## Running

```bash
# Just the validation layer
pytest tests/test_real_project_validation.py -q

# The whole suite (validation included)
pytest -q
```

The validation is fully deterministic: fixed fixtures, fixed routing rules, fixed blueprint, and a
pinned interpreter (`sys.executable`) for the one subprocess test run.
