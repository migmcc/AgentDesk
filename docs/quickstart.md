# Quickstart

Get Agent Desk installed, run the tests, and walk through a minimal real workflow using only
commands that exist today. Everything is local — no network, no accounts.

## 1. Prerequisites

- **Python 3.12 or newer** (`python --version`)
- **Git** (optional — only needed for the `git-status` / `branch` / `diff` commands)

## 2. Install from a local clone

```bash
git clone https://github.com/migmcc/AgentDesk.git
cd AgentDesk
```

### Create a virtual environment

```bash
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

### Install with dev dependencies

```bash
# editable install + the dev extra (pytest)
pip install -e ".[dev]"
```

This exposes the `agentdesk` command and installs the test tooling.

## 3. Run the tests

```bash
pytest
```

You should see **114 passed**. The suite is deterministic and offline.

## 4. Confirm the CLI

```bash
agentdesk            # shows help (no args)
agentdesk --help     # full command list
agentdesk version    # version + home directory
```

State lives under `~/.agentdesk/` by default. To keep a throwaway workspace isolated, point
`AGENTDESK_HOME` somewhere temporary:

```bash
# Windows (PowerShell):  $env:AGENTDESK_HOME = "$PWD\.agentdesk-demo"
# macOS / Linux:
export AGENTDESK_HOME="$PWD/.agentdesk-demo"
```

## 5. A minimal real workflow

Every command here is implemented. Create a project, plan it, then take the first task through the
coordination cycle.

```bash
# 1. Create a project (scaffolds a folder + persists state)
agentdesk new "Demo Agent Desk"

# 2. Generate base docs + a deterministic, routed 12-task plan
agentdesk plan "Demo Agent Desk"

# 3. See what is ready, blocked, and locked
agentdesk status "Demo Agent Desk"

# 4. Inspect the routing for the first task (which model + why)
agentdesk route "Demo Agent Desk" TASK-001

# 5. Generate the model-specific prompt file (copy-paste material; nothing is executed)
agentdesk prompt "Demo Agent Desk" TASK-001

# 6. Start the task: checks dependencies + file conflicts, locks files, moves it to "doing"
agentdesk start "Demo Agent Desk" TASK-001

#    --> Now do the actual work in your chosen AI model by pasting the generated prompt. <--

# 7. Record a handover (continuity document)
agentdesk handover "Demo Agent Desk" TASK-001 --summary "Initial architecture task prepared."

# 8. (optional) Record a test result the gate can use
agentdesk test-result "Demo Agent Desk" TASK-001 --command "pytest" --result passed

# 9. Run the quality gate (structured checks + an overall outcome)
agentdesk gate "Demo Agent Desk" TASK-001

# 10. Accept the task: releases locks and unblocks dependents
agentdesk done "Demo Agent Desk" TASK-001

# 11. Confirm the next tasks became ready
agentdesk status "Demo Agent Desk"
```

`<project>` accepts the slug (e.g. `demo-agent-desk`) or the name (`"Demo Agent Desk"`).

## 6. Optional: local Git features

If your project folder is a Git repository (the folder must be the repo root), you can use the local
Git helpers. They are read/inspect-only with respect to the network — no remotes, push, or PRs.

```bash
agentdesk git-status "Demo Agent Desk"          # repo? branch? clean? changed files
agentdesk branch "Demo Agent Desk" TASK-001     # create+checkout agent/TASK-001-<slug>
agentdesk diff "Demo Agent Desk" TASK-001       # changed files vs allowed/forbidden scope
```

## 7. Optional: advisory local-model assist

Configure a local model (e.g. Ollama via its OpenAI-compatible `/v1` endpoint) to get advisory
reports. This never edits code or task state.

```bash
export AGENTDESK_LOCAL_PROVIDER=ollama
export AGENTDESK_LOCAL_BASE_URL=http://localhost:11434/v1
export AGENTDESK_LOCAL_MODEL=llama3.1

agentdesk local-status
agentdesk local-assist "Demo Agent Desk" TASK-001 --mode summary
```

See [local-model.md](local-model.md) for the supported providers and modes.

## Troubleshooting

- **`agentdesk: command not found`** — your virtual environment is not active, or the editable
  install did not run. Re-activate `.venv` and re-run `pip install -e ".[dev]"`.
- **`Project '<id>' has no root_path; run plan first.`** — run `agentdesk plan <project>` before
  `prompt` / `handover`.
- **Git commands say "No Git repository detected"** — the project folder must itself be the Git repo
  root; a folder merely nested inside a larger repo is intentionally not treated as the project repo.

## Next steps

- [architecture.md](architecture.md) — how the modules fit together
- [advanced-quality-gate.md](advanced-quality-gate.md) — what the gate checks and why
- [../examples/README.md](../examples/README.md) — example workflows and the validation fixtures
