"""Allowed task state transitions and validation."""

from __future__ import annotations

from agentdesk.models import Task, TaskState

# User-initiated transitions only. `blocked` ⇄ `ready` from dependency recomputation is handled
# by the dependency manager and is intentionally not modeled here.
ALLOWED_TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.TODO: {TaskState.READY},
    TaskState.READY: {TaskState.DOING},
    TaskState.BLOCKED: {TaskState.READY},
    TaskState.DOING: {TaskState.REVIEW, TaskState.DONE, TaskState.REJECTED},
    TaskState.REVIEW: {TaskState.DONE, TaskState.REJECTED},
    TaskState.DONE: set(),
    TaskState.REJECTED: set(),
}


class InvalidTransition(Exception):
    """Raised when a state transition is not allowed."""

    def __init__(self, task_id: str, src: TaskState, dst: TaskState):
        self.task_id = task_id
        self.src = src
        self.dst = dst
        super().__init__(
            f"Cannot move {task_id} from '{src.value}' to '{dst.value}'."
        )


def can_transition(src: TaskState, dst: TaskState) -> bool:
    return dst in ALLOWED_TRANSITIONS.get(src, set())


def validate_transition(task_id: str, src: TaskState, dst: TaskState) -> None:
    if not can_transition(src, dst):
        raise InvalidTransition(task_id, src, dst)


def apply_transition(task: Task, dst: TaskState) -> Task:
    """Validate and apply a transition in place. Raises InvalidTransition if not allowed."""
    validate_transition(task.id, task.state, dst)
    task.state = dst
    return task
