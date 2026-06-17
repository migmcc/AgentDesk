# Changelog

## Unreleased

### Added
- Advanced quality gate (Phase 6): `agentdesk gate` now runs six deterministic check groups
  (scope, state/dependencies, risk, diff/Git, prompt, test, handover) and emits structured
  `[PASS]/[WARN]/[FAIL]/[REVIEW]` lines plus failures, warnings, human-review reasons, and a
  recommended action.
- `agentdesk test-result <project> <task> --result <passed|failed|not-run|unknown>` to record a
  test result (Agent Desk never runs tests).
- `docs/advanced-quality-gate.md`.

### Changed
- `GateResult` now stores structured checks and a recommended action.
- Git detection now requires the project folder to be its own repository root (avoids analyzing a
  parent repo when a project is nested inside one).

## v0.3.0 - Local Model Advisory Assistance

### Added
- Local model advisory assistance.
- `agentdesk local-status`.
- `agentdesk local-assist`.
- Support for summary, prompt-review, doc-check and handover-draft modes.
- Fake local model provider for deterministic tests.
- OpenAI-compatible local provider.
- Ollama support through its OpenAI-compatible `/v1` endpoint.
- Reports written to `reports/`.
- Advisory-only safety boundaries.
- Local model documentation.

### Changed
- Local model default timeout increased to 120 seconds.

### Not included
- Automatic model execution.
- Code modification by local models.
- Task state changes by local models.
- Git changes by local models.
- Local model as a required quality gate dependency.
- Runner.
- Watcher.
- UI.

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
