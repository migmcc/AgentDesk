# Contributing to Agent Desk

Thanks for your interest in improving Agent Desk. It is a local-first, deterministic CLI, and these
guidelines keep it that way.

## Development setup

Requires **Python 3.12+**.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
```

See [docs/quickstart.md](docs/quickstart.md) for a full walkthrough.

## Before you open a change

- **Run the tests and keep them green.** The suite must pass before and after your change:

  ```bash
  pytest
  ```

- **Use focused branches.** Branch off `main` with a descriptive name, e.g.
  `feat/<short-name>`, `fix/<short-name>`, or `chore/<short-name>`. Keep each branch and PR scoped to
  one logical change.

- **Write small, focused commits** with clear messages (`feat:`, `fix:`, `docs:`, `chore:`,
  `test:`).

## Ground rules

- **Never commit secrets.** No API keys, tokens, passwords, `.env` files, or personal/local paths.
  The repository ships with zero secrets and we keep it that way. Configuration for a local model is
  read from environment variables, never committed.

- **Keep tests deterministic.** Tests must be reproducible and offline:
  - no network access and no real AI/API calls (use the bundled `fake` provider),
  - no dependence on wall-clock time, machine paths, or ordering,
  - use `tmp_path` / `AGENTDESK_HOME` isolation so runs don't touch real state.

- **Don't redesign the engine for a small feature.** Prefer composing the existing modules
  (`planner`, `router`, `quality_gate`, `conflict_guard`, `git_integration`, `handover`, `storage`).
  See [docs/architecture.md](docs/architecture.md).

- **No new runtime dependencies** unless clearly justified. The core engine has no external runtime
  dependency beyond the declared CLI/templating libraries.

- **Update docs and the changelog** when behavior changes: `README.md`, the relevant file under
  `docs/`, and a `CHANGELOG.md` entry.

## Submitting

1. Push your branch and open a pull request against `main`.
2. Make sure CI is green on Python 3.12 and 3.13.
3. Describe what changed and how you validated it.

Maintainers handle version bumps, tags, and releases — please do not bump the version or create tags
in a feature PR.
