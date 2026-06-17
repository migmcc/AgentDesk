"""Core data model for Agent Desk.

Pydantic schemas and enums shared across every engine module. These types are the contract
between storage, routing, planning, conflict guard, prompt generation, handover, and quality gate.

Design notes (Run A / MVP):
- Task carries Git-ready optional fields (branch_name, commit_hash, ...) that need NOT function in
  the MVP. Git is deferred to Phase 4 (see docs/decisions.md); the schema is prepared so adding it
  later is non-breaking.
- Risk levels and the model enum follow the locked decisions in docs/decisions.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------------------
class TaskState(str, Enum):
    """Lifecycle of a task."""

    TODO = "todo"          # created but not yet prepared
    READY = "ready"        # ready to be sent to a model
    BLOCKED = "blocked"    # dependency or conflict
    DOING = "doing"        # in execution
    REVIEW = "review"      # work done, not yet approved
    DONE = "done"          # accepted
    REJECTED = "rejected"  # rejected / needs rework


class TaskType(str, Enum):
    """Type of a task — drives routing."""

    PLANNING = "planning"
    ARCHITECTURE = "architecture"
    SETUP = "setup"
    IMPLEMENTATION = "implementation"
    BUGFIX = "bugfix"
    REFACTOR = "refactor"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    REVIEW = "review"
    HANDOVER = "handover"
    QUALITY_GATE = "quality-gate"
    RESEARCH = "research"


class RiskLevel(str, Enum):
    """Task risk — see docs/decisions.md for concrete definitions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Model(str, Enum):
    """Executor models Agent Desk can route to."""

    CODEX = "codex"
    CLAUDE_CODE = "claude-code"
    LOCAL = "local"


class GateOutcome(str, Enum):
    """Possible quality-gate results."""

    PASS = "PASS"
    PASS_WITH_WARNINGS = "PASS_WITH_WARNINGS"
    FAIL = "FAIL"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class ProjectStatus(str, Enum):
    """High-level project lifecycle."""

    CREATED = "created"
    PLANNING = "planning"
    ACTIVE = "active"
    DONE = "done"


# --------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------
class Project(BaseModel):
    """A project managed by Agent Desk."""

    id: str  # slug
    name: str
    idea: str
    objective: Optional[str] = None
    status: ProjectStatus = ProjectStatus.CREATED
    root_path: Optional[str] = None  # on-disk folder for docs/tasks/prompts/handovers
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class Task(BaseModel):
    """A single unit of work, sized for one model in one session."""

    id: str  # e.g. TASK-001
    project_id: str
    name: str
    objective: str = ""
    context: str = ""
    task_type: TaskType = TaskType.IMPLEMENTATION
    recommended_model: Optional[Model] = None
    risk: RiskLevel = RiskLevel.MEDIUM
    allowed_files: list[str] = Field(default_factory=list)
    forbidden_files: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    test_command: Optional[str] = None
    definition_of_done: Optional[str] = None
    prompt: Optional[str] = None
    state: TaskState = TaskState.TODO
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # --- Git-ready fields (Phase 4; not functional in the MVP) ---
    branch_name: Optional[str] = None
    base_branch: Optional[str] = None
    commit_hash: Optional[str] = None
    changed_files: list[str] = Field(default_factory=list)
    pr_url: Optional[str] = None
    diff_summary: Optional[str] = None


class RoutingDecision(BaseModel):
    """Output of the model router for one task."""

    task_id: str
    task_type: TaskType
    risk: RiskLevel
    recommended_model: Optional[Model]  # None => handled by internal system (e.g. quality-gate low)
    reason: str
    alternative_model: Optional[Model] = None
    local_model_allowed: bool = False
    manual_override: bool = False
    override_model: Optional[Model] = None

    @property
    def effective_model(self) -> Optional[Model]:
        """The model that will actually be used, honoring a manual override."""
        if self.manual_override and self.override_model is not None:
            return self.override_model
        return self.recommended_model


class FileLock(BaseModel):
    """A reservation of a file path by a task (conflict guard)."""

    id: Optional[int] = None
    project_id: str
    task_id: str
    file_path: str
    created_at: datetime = Field(default_factory=_utcnow)


class Handover(BaseModel):
    """Continuity document produced at the end of a task."""

    task_id: str
    summary: str = ""
    what_changed: str = ""
    files_changed: list[str] = Field(default_factory=list)
    tests_run: str = ""
    problems_found: str = ""
    decisions_made: str = ""
    next_recommended_task: Optional[str] = None
    risks_remaining: str = ""
    created_at: datetime = Field(default_factory=_utcnow)


class GateResult(BaseModel):
    """Result of running the quality gate on a task."""

    task_id: str
    outcome: GateOutcome
    checks: dict[str, bool] = Field(default_factory=dict)
    notes: str = ""
    created_at: datetime = Field(default_factory=_utcnow)
