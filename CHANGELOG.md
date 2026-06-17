# Changelog

## Unreleased

### Added
- Local Git integration (Phase 4): `git-status`, `branch` (branch-per-task, persisted), and `diff`
  (changed-file detection + allowed/forbidden scope analysis).
- Quality gate enriched with Git findings: forbidden file change → FAIL; out-of-scope change,
  no associated branch, or no Git repo → warning. Projects without Git remain fully supported.
- `docs/git-integration.md`.

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
