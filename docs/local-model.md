# Local Model (Phase 5)

Agent Desk can use a **local model** as an advisory assistant for low-risk support tasks: summarize
context, review prompts before they go to Codex/Claude Code, review generated docs, and draft
handovers — all to save paid tokens and improve quality.

**The local model is an assistant, not an executor.** It never changes code, task state, the
official handover, project files, or Git. Its output is advisory and is written to the project's
`reports/` directory for you to act on.

## Configuration (env vars)

```bash
AGENTDESK_LOCAL_PROVIDER=openai-compatible   # fake | openai-compatible | ollama
AGENTDESK_LOCAL_BASE_URL=http://localhost:11434/v1
AGENTDESK_LOCAL_MODEL=<your-model-name>      # not hard-coded
AGENTDESK_LOCAL_TIMEOUT=120   # default 120s; raise it for large/cold local models
```

- `fake` — deterministic, offline; used by the test suite and for trying the flow without a model.
- `openai-compatible` — any OpenAI-compatible `/chat/completions` endpoint.
- `ollama` — works through the OpenAI-compatible surface (set `base_url` to `.../v1`).

Check it with `agentdesk local-status` (never crashes if unconfigured).

## Commands

```bash
agentdesk local-status
agentdesk local-assist <project> <task> --mode <mode>
```

Modes: `summary`, `prompt-review`, `doc-check`, `handover-draft`.

## Modes

| Mode | Purpose | Output |
|------|---------|--------|
| `summary` | Summarize the task and its context | `reports/TASK-XXX-summary.md` |
| `prompt-review` | Review the generated prompt before use | `reports/TASK-XXX-prompt-review.md` |
| `doc-check` | Review the project docs vs the task | `reports/TASK-XXX-doc-check.md` |
| `handover-draft` | Draft a handover **proposal** | `reports/TASK-XXX-handover-draft.md` |

`handover-draft` does not replace the official handover. To record one, the user still runs:

```bash
agentdesk handover "<project>" TASK-XXX --summary "..."
```

## Example

```bash
export AGENTDESK_LOCAL_PROVIDER=openai-compatible
export AGENTDESK_LOCAL_BASE_URL=http://localhost:11434/v1
export AGENTDESK_LOCAL_MODEL=llama3.1

agentdesk local-status
agentdesk local-assist "My Project" TASK-003 --mode summary
agentdesk local-assist "My Project" TASK-003 --mode prompt-review
```

## Safety and limits

- High-risk tasks: analysis is allowed but the CLI warns that output is advisory only.
- Implementation tasks: advisory output only; never modifies implementation files.
- The internal prompts instruct the model: *"You are an advisory local model. Do not claim to have
  executed code. Do not invent files, tests, commits, or changes. Use only the context provided.
  If information is missing, say so."*
- The quality gate stays independent: **local model output is advisory and is never required for
  PASS.**

## Out of scope

Code execution, automatic file changes, commits, Git operations, GitHub API, PRs, push, runners,
watchers, UI, and making the local model a required part of the gate.
