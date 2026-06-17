# Changelog

## Unreleased

### Added
- Local model advisory assistance (Phase 5): `local-status` and
  `local-assist <project> <task> --mode <summary|prompt-review|doc-check|handover-draft>`,
  writing advisory reports to `reports/`.
- Providers: `fake` (deterministic, for tests) and `openai-compatible` (Ollama via its `/v1`),
  configured by env vars (`AGENTDESK_LOCAL_PROVIDER/BASE_URL/MODEL/TIMEOUT`).
- `docs/local-model.md`.

### Notes
- The local model is advisory only: it never changes code, task state, the official handover, or
  Git, and is never required for a quality-gate PASS.

## v0.2.0 - Git Integration

### Added
- Local Git repository detection.
- Task branch creation.
- Branch association per task.
- Changed file detection.
- Diff summary support.
- Scope analysis against allowed files.
- Forbidden file violation detection.
- Git-enriched quality gate.
- Documentation for Git integration.

### Not included
- GitHub API.
- Pull requests.
- Push.
- Automatic commits.
- Automatic merge.
- CI integration.
- Model execution.

## v0.1.0 - Initial MVP

### Added
- Local-first CLI project management.
- Project creation.
- Deterministic planning.
- Task decomposition.
- Dependency management.
- Model routing for Codex, Claude Code and local models.
- Prompt generation.
- File locking and conflict guard.
- Task state coordination.
- Handover generation.
- Deterministic quality gate.
- MVP demo documentation.
- Packaged templates.
- Non-editable install support.

### Not included
- Automatic model execution.
- Git branch/diff integration.
- Runner/watcher.
- UI.
- SaaS.
- Multi-user collaboration.
