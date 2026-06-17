# Git Integration (Phase 4)

Agent Desk can use a project's **local** Git repository to create a branch per task, detect what
actually changed, and feed that information into the quality gate.

**Local only.** No remotes, no `push`, no pull requests, no GitHub API, no automatic commits or
merges. Agent Desk prepares and analyzes; it never publishes. Model execution stays manual.

## Locks vs Git diff

> Locks control planned work before execution. Git diff checks what actually changed after
> execution.

- **Conflict guard (SQLite locks)** — *before* you work: reserves a task's files so two tasks don't
  collide. Order-independent, intent-based.
- **Git diff** — *after* you work: reports the files that were actually modified and checks them
  against the task's `allowed_files` / `forbidden_files`.

## Commands

```bash
agentdesk git-status <project>          # repo detected? current branch? clean? changed files
agentdesk branch <project> <task>       # create/checkout agent/TASK-XXX-<slug>, store branch_name
agentdesk diff <project> <task>         # changed files + allowed/forbidden scope analysis
```

`branch` and `diff` require the project folder to be inside a Git repo; otherwise they print a clear
message and exit. `git-status` never crashes on a non-Git project.

## Example flow

```bash
# project folder is a git repo; commit the generated plan first so task diffs stay clean
git add -A && git commit -m "agentdesk: initial plan"

agentdesk branch "My Project" TASK-003     # -> agent/TASK-003-create-review-parser
agentdesk start  "My Project" TASK-003     # locks files, -> doing (shows the branch)
# ... do the work in your chosen model, editing only the allowed files ...
agentdesk diff   "My Project" TASK-003     # confirm changes are in scope
agentdesk handover "My Project" TASK-003 --summary "Implemented the parser."
agentdesk gate   "My Project" TASK-003     # now also checks Git scope
agentdesk done   "My Project" TASK-003
```

## Quality gate with Git

When a project is a Git repo, the gate adds these checks:

- Git repository detected
- Branch associated with the task
- Changed files detected (Agent Desk's own `prompts/`, `handovers/`, `tasks/`, and `agentdesk.json`
  are excluded — they are tool artifacts, not task deliverables)
- Changed files within `allowed_files`
- Forbidden files not changed

Effect on the result:

- **FAIL** — a forbidden file was changed, the task's branch is missing, or a git command fails.
- **PASS_WITH_WARNINGS** — files changed outside `allowed_files` (but not forbidden), no branch
  associated, working tree dirty, or no Git repo detected.
- **PASS** — clean scope inside a Git repo (subject to the existing non-Git checks).
- **NEEDS_HUMAN_REVIEW** — unchanged (high risk / architecture / refactor / quality-gate / dangerous
  override) and still takes precedence over warnings.

## Schema fields

The Git-ready Task fields become functional in this phase: `branch_name` (set by `branch`),
`changed_files` and `diff_summary` (set by `diff`). `base_branch`, `commit_hash`, and `pr_url`
remain optional/non-functional (PRs and remotes are out of scope).

## Tips

- Commit the generated plan (`docs/`, `tasks/`, `agentdesk.json`) right after `plan`, or add them to
  `.gitignore`, so per-task diffs show only your task work.
- Documentation tasks legitimately edit `docs/`; set their `allowed_files` to include `docs/**`.

## Out of scope

GitHub API, pull requests, push, automatic commits/merges, CI, runners, watchers, model execution.
