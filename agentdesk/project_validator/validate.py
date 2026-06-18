"""Deterministic validation of a real, local project folder.

This exposes existing Agent Desk capabilities as a single read-only report over an arbitrary
directory:

- local Git inspection (``git_integration``): repo? branch? clean or dirty?
- README presence (a public-readiness signal),
- an optional test command (the only thing that ever runs, and only when explicitly provided),
- and — when the folder is a *registered* Agent Desk project — active file locks (conflict /
  unsafe-edit indicators) and handover presence, read from ``storage``.

It reuses the quality gate's PASS / WARN / FAIL vocabulary (``GateOutcome``) for the overall result
so the output is consistent with ``agentdesk gate``. No LLM, no network. The engine modules are not
modified; this is a thin, additive composition layer.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agentdesk import git_integration as git
from agentdesk.models import GateOutcome, TaskState
from agentdesk.storage import Storage

# Per-line presentation levels. SKIP is neutral and never affects the overall outcome.
PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SKIP = "SKIP"

README_PREFIX = "readme"
DEFAULT_TEST_TIMEOUT = 600  # seconds; generous, only used when a test command is provided


@dataclass
class Check:
    """One line in the validation report."""

    name: str
    level: str
    message: str

    def to_dict(self) -> dict:
        return {"name": self.name, "level": self.level, "message": self.message}


@dataclass
class ValidationReport:
    """The full deterministic result of validating a project folder."""

    path: str
    checks: list[Check] = field(default_factory=list)
    outcome: GateOutcome = GateOutcome.PASS

    @property
    def failed(self) -> bool:
        return self.outcome is GateOutcome.FAIL

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "outcome": self.outcome.value,
            "checks": [c.to_dict() for c in self.checks],
        }


def _has_readme(root: Path) -> bool:
    """True if a top-level file named README(.*) exists (case-insensitive)."""
    try:
        for entry in root.iterdir():
            if entry.is_file() and entry.name.lower().startswith(README_PREFIX):
                return True
    except OSError:
        return False
    return False


def _git_check(root: Path) -> Check:
    if not git.is_git_repo(root):
        return Check("git", WARN, "Git repository not detected.")
    try:
        branch = git.current_branch(root) or "(detached)"
        if git.is_clean(root):
            return Check("git", PASS, f"Working tree clean on branch '{branch}'.")
        changed = git.changed_files(root)
        return Check(
            "git", WARN,
            f"Working tree is dirty on branch '{branch}' ({len(changed)} file(s) changed).",
        )
    except git.GitError as exc:
        # A git hiccup should not hard-fail a folder validation; surface it as a warning.
        return Check("git", WARN, f"Git inspection failed: {exc}")


def _readme_check(root: Path) -> Check:
    if _has_readme(root):
        return Check("readme", PASS, "README found at the project root.")
    return Check("readme", WARN, "No README found at the project root.")


def _test_check(root: Path, test_command: Optional[str], timeout: int) -> Check:
    if not test_command:
        return Check("tests", SKIP, "No test command provided (use --test-command to run tests).")
    try:
        proc = subprocess.run(
            test_command, shell=True, cwd=str(root),
            capture_output=True, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return Check("tests", FAIL, f"Test command timed out after {timeout}s: {test_command}")
    except OSError as exc:
        return Check("tests", FAIL, f"Could not run test command: {exc}")
    if proc.returncode == 0:
        return Check("tests", PASS, f"Test command passed: {test_command}")
    return Check("tests", FAIL, f"Test command failed (exit {proc.returncode}): {test_command}")


def _find_registered_project(store: Optional[Storage], root: Path):
    """Return the registered project whose root_path is this folder, or None."""
    if store is None:
        return None
    target = root.resolve()
    for proj in store.list_projects():
        if proj.root_path and Path(proj.root_path).resolve() == target:
            return proj
    return None


def _conflict_check(store: Optional[Storage], proj) -> Check:
    if proj is None:
        return Check("conflict", SKIP,
                     "Not a registered Agent Desk project; file-lock checks skipped.")
    locks = store.locks_for_project(proj.id)
    if locks:
        held = ", ".join(f"{lk.file_path} (held by {lk.task_id})" for lk in locks)
        return Check("conflict", WARN, f"{len(locks)} active file lock(s): {held}.")
    return Check("conflict", PASS, "No active file locks.")


def _handover_check(store: Optional[Storage], proj) -> Check:
    if proj is None:
        return Check("handover", SKIP,
                     "Not a registered Agent Desk project; handovers are tracked per task.")
    in_progress = [
        t for t in store.list_tasks(proj.id)
        if t.state in (TaskState.DOING, TaskState.REVIEW)
    ]
    missing = [t.id for t in in_progress if store.get_handover(proj.id, t.id) is None]
    if missing:
        return Check("handover", WARN,
                     f"In-progress task(s) without a handover: {', '.join(missing)}. "
                     "Run: agentdesk handover <project> <task>.")
    if in_progress:
        return Check("handover", PASS, "All in-progress tasks have a handover.")
    return Check("handover", SKIP, "No in-progress tasks requiring a handover.")


def validate_project(
    path: str | Path,
    *,
    test_command: Optional[str] = None,
    store: Optional[Storage] = None,
    timeout: int = DEFAULT_TEST_TIMEOUT,
) -> ValidationReport:
    """Validate a local project folder and return a deterministic report.

    Assumes ``path`` exists (the CLI validates this first). When ``store`` is provided and the folder
    is a registered Agent Desk project, conflict/handover checks use real lock and handover data;
    otherwise those checks are reported as SKIP.

    Overall outcome: any FAIL -> FAIL; else any WARN -> PASS_WITH_WARNINGS; else PASS. SKIP lines
    never change the outcome.
    """
    root = Path(path)
    proj = _find_registered_project(store, root)
    checks = [
        _git_check(root),
        _readme_check(root),
        _test_check(root, test_command, timeout),
        _conflict_check(store, proj),
        _handover_check(store, proj),
    ]

    if any(c.level == FAIL for c in checks):
        outcome = GateOutcome.FAIL
    elif any(c.level == WARN for c in checks):
        outcome = GateOutcome.PASS_WITH_WARNINGS
    else:
        outcome = GateOutcome.PASS

    return ValidationReport(path=str(root), checks=checks, outcome=outcome)
