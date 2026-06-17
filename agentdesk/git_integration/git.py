"""Thin, local-only Git helpers built on subprocess. No network, no commits, no pushes."""

from __future__ import annotations

import fnmatch
import subprocess
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
    """True if `root` is inside a Git work tree. Never raises (returns False on any problem)."""
    if not root or not Path(root).exists():
        return False
    try:
        proc = _run(root, "rev-parse", "--is-inside-work-tree", check=False)
    except GitError:
        return False
    return proc.returncode == 0 and proc.stdout.strip() == "true"


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


def gate_findings(root: str | Path | None, task) -> tuple[dict[str, str], list[str], list[str]]:
    """Git-derived checks for the quality gate: (checks, failures, warnings).

    Defensive: a non-repo project yields a warning (not a failure); a critical git error yields a
    failure rather than a crash.
    """
    checks: dict[str, str] = {}
    failures: list[str] = []
    warnings: list[str] = []

    if not is_git_repo(root):
        checks["Git repository"] = "not detected"
        warnings.append("Git repository not detected.")
        return checks, failures, warnings

    checks["Git repository"] = "detected"
    try:
        branch_name = getattr(task, "branch_name", None)
        if branch_name:
            if not branch_exists(root, branch_name):
                checks["Task branch"] = "missing"
                failures.append(
                    f"Branch '{branch_name}' associated with {task.id} does not exist."
                )
                return checks, failures, warnings
            checks["Task branch"] = branch_name
        else:
            checks["Task branch"] = "none"
            warnings.append("No branch associated with the task.")

        changed = filter_task_changes(changed_files(root))
        checks["Changed files"] = str(len(changed))
        out_of_scope, forbidden_v = analyze_scope(
            changed, task.allowed_files, task.forbidden_files
        )
        if forbidden_v:
            checks["Forbidden files"] = "violated"
            failures += [f"Forbidden file changed: {f}." for f in forbidden_v]
        else:
            checks["Forbidden files"] = "not changed"
        if out_of_scope:
            checks["Changed files in scope"] = "no"
            warnings += [f"{f} changed but not listed in allowed_files." for f in out_of_scope]
        else:
            checks["Changed files in scope"] = "yes"
    except GitError as exc:
        failures.append(f"Git command failed: {exc}")

    return checks, failures, warnings
