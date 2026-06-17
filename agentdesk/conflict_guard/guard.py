"""File-collision checks for starting a task. Pure read over the lock store."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from agentdesk.models import Task
from agentdesk.storage import Storage


class ConflictDecision(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class ConflictResult:
    decision: ConflictDecision
    reasons: list[str] = field(default_factory=list)
    conflicts: list[tuple[str, str]] = field(default_factory=list)  # (file_path, holder_task_id)

    @property
    def allowed(self) -> bool:
        """True unless blocked (warn still allows the action, with a notice)."""
        return self.decision is not ConflictDecision.BLOCK


def check_start(store: Storage, project_id: str, task: Task) -> ConflictResult:
    """Decide whether `task` may start, based purely on file locks.

    - any allowed file already locked by another task -> BLOCK (lists the conflicts)
    - a file that is both allowed and forbidden (self-contradiction) -> BLOCK
    - no allowed files defined -> WARN
    - otherwise -> ALLOW
    """
    conflicts: list[tuple[str, str]] = []
    for path in task.allowed_files:
        held = store.lock_for_file(project_id, path)
        if held is not None and held.task_id != task.id:
            conflicts.append((path, held.task_id))
    if conflicts:
        reasons = [f"{path} locked by {holder}" for path, holder in conflicts]
        return ConflictResult(ConflictDecision.BLOCK, reasons, conflicts)

    contradictory = sorted(set(task.allowed_files) & set(task.forbidden_files))
    if contradictory:
        return ConflictResult(
            ConflictDecision.BLOCK,
            [f"{p} is both allowed and forbidden" for p in contradictory],
        )

    if not task.allowed_files:
        return ConflictResult(
            ConflictDecision.WARN,
            ["Task has no allowed files defined; no locks will be created."],
        )

    return ConflictResult(ConflictDecision.ALLOW)
