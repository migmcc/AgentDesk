"""Local Git integration for Agent Desk (Phase 4).

Local-only: no remotes, no push, no PRs, no auto-commit. Wraps a few plain `git` commands via
subprocess and compares changed files against a task's allowed/forbidden lists.

Locks (SQLite) control *planned* work before execution; Git diff checks what *actually* changed
after execution. The two are complementary.
"""

from agentdesk.git_integration.git import (
    GitError,
    RepoAnalysis,
    analyze_scope,
    branch_exists,
    changed_files,
    create_branch,
    current_branch,
    diff_stat,
    filter_task_changes,
    is_clean,
    is_git_repo,
    matches_any,
    repo_analysis,
)

__all__ = [
    "GitError",
    "RepoAnalysis",
    "analyze_scope",
    "branch_exists",
    "changed_files",
    "create_branch",
    "current_branch",
    "diff_stat",
    "filter_task_changes",
    "is_clean",
    "is_git_repo",
    "matches_any",
    "repo_analysis",
]
