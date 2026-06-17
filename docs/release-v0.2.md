# Agent Desk — Release v0.2.0

## Version
`0.2.0` — Git Integration (builds on the v0.1.0 MVP).

## What's new
Local Git integration (Phase 4), layered on top of the complete v0.1.0 MVP without changing the
manual, local-first workflow.

## New commands
```bash
agentdesk git-status <project>     # repo detected? current branch? clean? changed files
agentdesk branch <project> <task>  # create/checkout agent/TASK-XXX-<slug>, persist branch_name
agentdesk diff <project> <task>    # changed files + allowed/forbidden scope analysis
```
`agentdesk start` now also shows a task's associated branch.

## Git features included
- Local Git repository detection (never crashes on non-Git projects).
- Branch per task (`agent/TASK-XXX-<slug>`), persisted to `branch_name`.
- Changed-file detection (individual untracked files included).
- Diff summary (`diff_summary`) and recorded `changed_files`.
- Scope analysis against `allowed_files`; out-of-scope changes flagged.
- Forbidden-file violation detection.
- Quality gate enriched with Git findings.

## Locks (SQLite) vs Git diff
- **Locks** control *planned* work before execution — reserve a task's files so two tasks don't
  collide.
- **Git diff** checks what *actually* changed after execution — and whether it stayed in scope.

See [git-integration.md](git-integration.md) for details.

## Quality gate with Git
- **FAIL** — forbidden file changed, task branch missing, or a git command fails.
- **PASS_WITH_WARNINGS** — out-of-scope change, no branch associated, dirty tree, or no Git repo.
- **PASS** — clean scope inside a Git repo (plus the existing non-Git checks).
- **NEEDS_HUMAN_REVIEW** — unchanged precedence (high risk / architecture / refactor / quality-gate /
  dangerous override).

## Known limitations
- Local Git only: no remotes, push, pull requests, automatic commits/merges, GitHub API, or CI.
- Model execution remains manual.
- `commit_hash`, `base_branch`, `pr_url` remain optional / non-functional.
- Projects without Git are fully supported (Git commands warn; gate degrades to a warning).

## Validation checklist
- [x] `feat/git-integration` merged into the default branch with `--no-ff`.
- [x] Version bumped to `0.2.0` (pyproject + `agentdesk.__version__`).
- [x] `pytest` → 80 passed (Git tests use temporary repos only).
- [x] Manual validation of `git-status` / `branch` / `diff` against a temporary Git repo.
- [x] CHANGELOG updated; README, roadmap, and `docs/git-integration.md` reflect v0.2.0.
- [x] `docs/release-v0.1.md` preserved as v0.1 history.
- [x] Tag `v0.2.0` cut.

## Next steps
- **Phase 5 — Local model**: real summarizer / handover / prompt-review / doc-check support tasks.
- Optional: rename the default branch `master` → `main`; add a Git remote and push tags if/when the
  project goes public.
