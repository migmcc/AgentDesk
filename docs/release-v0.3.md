# Agent Desk — Release v0.3.0

## Version
`0.3.0` — Local Model Advisory Assistance (builds on v0.2.0 Git Integration and the v0.1.0 MVP).

## Release status
Stable. 93 tests pass; validated with the deterministic fake provider **and** with a real local
model (`qwen3:14b`) via Ollama's OpenAI-compatible `/v1` endpoint.

## What's new
A local model can now act as an advisory assistant for low-risk support work — without ever
executing or changing anything.

> The local model is advisory only. It does not execute code, modify implementation files, change
> task state, create official handovers, touch Git, or affect quality-gate PASS requirements.

## Included functionality
- Local model advisory assistance.
- `agentdesk local-status` (configuration check; never crashes when unconfigured).
- `agentdesk local-assist <project> <task> --mode <mode>`.
- Modes: `summary`, `prompt-review`, `doc-check`, `handover-draft`.
- Fake provider (deterministic, for tests) and OpenAI-compatible provider.
- Ollama support through its OpenAI-compatible `/v1` endpoint.
- Advisory reports written to `reports/` (excluded from Git scope analysis).
- Advisory-only safety boundaries and warnings for high-risk / implementation tasks.
- Local model documentation (`docs/local-model.md`).
- Default local-model timeout raised to 120s.

## New commands
```bash
agentdesk local-status
agentdesk local-assist <project> <task> --mode <summary|prompt-review|doc-check|handover-draft>
```

## Providers supported
- `fake` — deterministic, offline; used by the test suite.
- `openai-compatible` — any OpenAI-compatible `/chat/completions` endpoint.
- `ollama` — via its OpenAI-compatible `/v1` endpoint (set `base_url` to `.../v1`).

## Modes supported
| Mode | Output |
|------|--------|
| `summary` | `reports/TASK-XXX-summary.md` |
| `prompt-review` | `reports/TASK-XXX-prompt-review.md` |
| `doc-check` | `reports/TASK-XXX-doc-check.md` |
| `handover-draft` | `reports/TASK-XXX-handover-draft.md` |

## Configuration (env vars)
```bash
AGENTDESK_LOCAL_PROVIDER=openai-compatible
AGENTDESK_LOCAL_BASE_URL=http://localhost:11434/v1
AGENTDESK_LOCAL_MODEL=<your-model-name>
AGENTDESK_LOCAL_TIMEOUT=120
```

## Real-model validation (qwen3:14b)
- `local-status` reported the configured endpoint and model correctly.
- All four modes produced coherent advisory reports (first cold call ~61s → default timeout raised
  to 120s).
- Read-only confirmed: task state unchanged, no official handover created, no `.git` touched, and
  only `reports/` files written.

## Known limitations
- Advisory only (see boundary statement above).
- Local Git only (no remotes/push/PRs); model execution remains manual.
- Fixed-rule routing (no scoring); single-user; no UI/SaaS.

## Validation checklist
- [x] `feat/local-model-assist` merged into `main` with `--no-ff`.
- [x] Version bumped to `0.3.0` (pyproject + `agentdesk.__version__`).
- [x] `pytest` → 93 passed (Phase 5 tests use the fake provider only).
- [x] Real local model validated (`qwen3:14b` via Ollama `/v1`).
- [x] CHANGELOG updated; README, roadmap, and `docs/local-model.md` reflect v0.3.0.
- [x] `docs/release-v0.1.md` and `docs/release-v0.2.md` preserved as history.
- [x] Tag `v0.3.0` cut.

## Next steps
- **Phase 6 — Advanced quality gate**: test-check, diff-check, scope-check, risk-check.
- **Phase 7 — UI** (later).
- Optional: add a Git remote and `git push --follow-tags` if/when the project goes public.
