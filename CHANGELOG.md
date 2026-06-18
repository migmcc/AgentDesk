# Changelog

## v0.4.2 - Real Project Validate Command

### Added
- New `agentdesk validate-project <path>` command: deterministic, read-only validation of a local
  project folder (it does not need to be a registered Agent Desk project).
- Git state inspection: repository detection, current branch, and clean / dirty working tree.
- README detection at the project root.
- Optional `--test-command` execution inside the project (the only thing that ever runs).
- `PASS / PASS_WITH_WARNINGS / FAIL` summary; exits non-zero only on `FAIL`.
- `--json` output mode for machine consumption.
- Registered-project conflict and handover indicators (active file locks and missing handovers for
  in-progress tasks), read from `storage`.
- New `agentdesk/project_validator/` module — a thin composition layer that reuses `git_integration`,
  the quality gate's `GateOutcome` vocabulary, and `storage`. No engine module was redesigned.
- 11 new tests covering the command (clean project, missing path, file-not-directory, missing README,
  non-git folder, passing and failing test commands, JSON output and JSON failure exit code,
  registered-project locks/handover, and CLI help).
- Documentation updates: README, `docs/quickstart.md`, `examples/README.md`, and this changelog.

### Notes
- The command never calls an AI model and adds no external dependencies. The only thing it executes
  is the test command you explicitly pass via `--test-command`.

## v0.4.1 - Real Project Validation

### Added
- Real project validation layer.
- `docs/validation/real-project-validation-v0.4.1.md`.
- Realistic, runnable sample project fixtures under `tests/fixtures/real_projects/`.
- Integration tests exercising the existing engine against realistic projects:
  - Clean Python CLI project.
  - Broken tests project.
  - Missing README project.
  - Dirty Git state / out-of-scope edits.
  - Conflict guard blocking.
  - Handover output.
- Pytest fixture exclusion via `norecursedirs = ["fixtures"]` so the sample projects
  (some intentionally broken) are not collected by Agent Desk's own suite.

### Notes
- Validation only: it reuses planner, router, quality_gate, conflict_guard, handover, and
  git_integration. No production `agentdesk/` modules were changed.

### Not included
- Release tag.
- Automatic test execution by Agent Desk.

## v0.4.0 - Advanced Quality Gate

### Added
- Advanced deterministic quality gate.
- `agentdesk test-result` command.
- Manual test result registration.
- Structured gate checks with PASS/WARN/FAIL/REVIEW levels.
- Scope check.
- State and dependency check.
- Risk check.
- Diff check using local Git information.
- Prompt check.
- Improved handover check.
- Persistent test results.
- Detailed recommended actions in gate output.
- Advanced quality gate documentation.

### Changed
- `agentdesk gate` now provides grouped checks, failures, warnings, human review reasons and recommended actions.
- Git analysis now requires the managed project folder to be the repository root.

### Not included
- Automatic test execution.
- CI integration.
- GitHub API.
- Pull requests.
- Push.
- Runner.
- Watcher.
- UI.
- Automatic model execution.

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
