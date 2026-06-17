"""Conflict guard — prevent tasks/models from working in incompatible file zones.

Run D. Controls **file collisions** (the dependency manager controls **order**). Given a task that
wants to start, it compares the task's allowed files against currently held locks and returns
allow / warn / block. MVP uses SQLite locks only — no Git.
"""

from agentdesk.conflict_guard.guard import (
    ConflictDecision,
    ConflictResult,
    check_start,
)

__all__ = ["ConflictDecision", "ConflictResult", "check_start"]
