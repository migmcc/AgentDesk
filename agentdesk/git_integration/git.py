"""Thin, local-only Git helpers built on subprocess. No network, no commits, no pushes."""

from __future__ import annotations

import fnmatch
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


class GitError(Exception):
    """Raised when a git command fails critically."""


def _run(root: str | Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(root), capture_output=True, text=True
        )
    except FileNotFoundError as exc:  # git not installed
        raise GitError("git executable not found on PATH.") from exc
    if check and proc.returncode != 0:
        raise GitError((proc.stderr or proc.stdout).strip() or f"git {' '.join(args)} failed")
    return proc


def is_git_repo(root: str | Path | None) -> bool:
    """True if `root` is itself the root of a Git work tree.

    Agent Desk treats a project folder as its own repository, so a folder merely *nested* inside a
    larger repo is intentionally NOT treated as the project's repo (avoids analyzing a parent repo).
    Never raises (returns False on any problem).
    """
    if not root or not Path(root).exists():
        return False
    try:
        inside = _run(root, "rev-parse", "--is-inside-work-tree", check=False)
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return False
        top = _run(root, "rev-parse", "--show-toplevel", check=False)
        if top.returncode != 0:
            return False
        return Path(top.stdout.strip()).resolve() == Path(root).resolve()
    except GitError:
        return False


def current_branch(root: str | Path) -> Optional[str]:
    return _run(root, "branch", "--show-current").stdout.strip() or None


def is_clean(root: str | Path) -> bool:
    return _run(root, "status", "--porcelain").stdout.strip() == ""


def changed_files(root: str | Path) -> list[str]:
    """Paths changed in the working tree (staged, unstaged, and individual untracked files)."""
    # -uall lists untracked files individually instead of collapsing whole untracked directories.
    out = _run(root, "status", "--porcelain", "-uall").stdout
    files: list[str] = []
    for line in out.splitlines():
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else line.strip()
        if "->" in path:  # rename: "old -> new"
            path = path.split("->")[-1]
        files.append(path.strip().strip('"'))
    return sorted(set(files))


def branch_exists(root: str | Path, name: str) -> bool:
    proc = _run(root, "rev-parse", "--verify", f"refs/heads/{name}", check=False)
    return proc.returncode == 0


def create_branch(root: str | Path, name: str) -> bool:
    """Create and check out `name`. If it already exists, just check it out.

    Returns True if a new branch was created, False if an existing one was reused.
    """
    if branch_exists(root, name):
        _run(root, "checkout", name)
        return False
    _run(root, "checkout", "-b", name)
    return True


def diff_stat(root: str | Path) -> str:
    return _run(root, "diff", "--stat").stdout.strip()


# Agent Desk's own coordination artifacts — not task deliverables, so excluded from scope checks.
IGNORED_CHANGE_PREFIXES = ("prompts/", "handovers/", "tasks/", "reports/")
IGNORED_CHANGE_FILES = ("agentdesk.json",)


def filter_task_changes(changed: list[str]) -> list[str]:
    """Drop Agent Desk's generated artifacts so they are not treated as task work."""
    result = []
    for c in changed:
        n = _norm(c)
        if any(n.startswith(p) for p in IGNORED_CHANGE_PREFIXES) or n in IGNORED_CHANGE_FILES:
            continue
        result.append(c)
    return result


# --------------------------------------------------------------------- scope analysis
def _norm(p: str) -> str:
    return p.replace("\\", "/").strip()


def matches_any(path: str, patterns: list[str]) -> bool:
    """True if `path` matches any glob pattern (e.g. 'src/**', 'docs/architecture.md')."""
    p = _norm(path)
    for raw in patterns:
        pat = _norm(raw)
        if p == pat or fnmatch.fnmatch(p, pat):
            return True
    return False


def analyze_scope(
    changed: list[str], allowed: list[str], forbidden: list[str]
) -> tuple[list[str], list[str]]:
    """Return (out_of_scope, forbidden_violations) for changed files.

    - forbidden_violations: changed files matching a forbidden pattern.
    - out_of_scope: changed files matching no allowed pattern (and not forbidden).
    """
    forbidden_violations = [c for c in changed if matches_any(c, forbidden)]
    out_of_scope = [
        c for c in changed
        if c not in forbidden_violations and not matches_any(c, allowed)
    ]
    return out_of_scope, forbidden_violations


@dataclass
class RepoAnalysis:
    """Structured Git facts for a task, consumed by the quality gate's diff-check."""

    is_repo: bool
    branch_name: Optional[str] = None
    branch_associated: bool = False
    branch_missing: bool = False           # branch_name set but the branch does not exist
    changed: list[str] = field(default_factory=list)
    out_of_scope: list[str] = field(default_factory=list)
    forbidden: list[str] = field(default_factory=list)
    error: Optional[str] = None            # a critical git error message, if any


def repo_analysis(root: str | Path | None, task) -> RepoAnalysis:
    """Inspect the repo for a task. Never raises: a non-repo or git error is reported via fields."""
    if not is_git_repo(root):
        return RepoAnalysis(is_repo=False)
    branch_name = getattr(task, "branch_name", None)
    try:
        branch_missing = bool(branch_name) and not branch_exists(root, branch_name)
        changed: list[str] = []
        if not branch_missing:
            changed = filter_task_changes(changed_files(root))
        out_of_scope, forbidden_v = analyze_scope(
            changed, task.allowed_files, task.forbidden_files
        )
        return RepoAnalysis(
            is_repo=True,
            branch_name=branch_name,
            branch_associated=bool(branch_name),
            branch_missing=branch_missing,
            changed=changed,
            out_of_scope=out_of_scope,
            forbidden=forbidden_v,
        )
    except GitError as exc:
        return RepoAnalysis(is_repo=True, branch_name=branch_name, error=str(exc))
