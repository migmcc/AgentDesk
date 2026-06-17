"""Core dependency logic. Pure functions over Task lists — no I/O, fully testable."""

from __future__ import annotations

from dataclasses import dataclass, field

from agentdesk.models import Task, TaskState

# States that the dependency manager must NOT auto-change. A task that is being worked on or is
# already finished keeps its state regardless of dependency movement.
SETTLED_STATES: frozenset[TaskState] = frozenset(
    {TaskState.DOING, TaskState.REVIEW, TaskState.DONE, TaskState.REJECTED}
)


@dataclass
class DependencyIssues:
    """Structural problems found in a task set's dependency graph."""

    unknown: dict[str, list[str]] = field(default_factory=dict)   # task_id -> missing dep ids
    self_dependent: list[str] = field(default_factory=list)        # task ids depending on themselves
    cycles: list[list[str]] = field(default_factory=list)          # each cycle as an ordered id list

    @property
    def ok(self) -> bool:
        return not self.unknown and not self.self_dependent and not self.cycles


def _by_id(tasks: list[Task]) -> dict[str, Task]:
    return {t.id: t for t in tasks}


def done_ids(tasks: list[Task]) -> set[str]:
    """Ids of tasks that are accepted (`done`)."""
    return {t.id for t in tasks if t.state is TaskState.DONE}


def dependencies_satisfied(task: Task, accepted: set[str]) -> bool:
    """True when every dependency of `task` is in the accepted (`done`) set."""
    return all(dep in accepted for dep in task.dependencies)


def compute_state(task: Task, accepted: set[str]) -> TaskState:
    """The state `task` should have given which dependencies are accepted.

    Settled states (doing/review/done/rejected) are preserved. Otherwise the task is READY when its
    dependencies are all satisfied, else BLOCKED.
    """
    if task.state in SETTLED_STATES:
        return task.state
    return TaskState.READY if dependencies_satisfied(task, accepted) else TaskState.BLOCKED


def recompute_states(tasks: list[Task]) -> list[Task]:
    """Update blocked/ready states in place; return the tasks whose state changed."""
    accepted = done_ids(tasks)
    changed: list[Task] = []
    for task in tasks:
        new_state = compute_state(task, accepted)
        if new_state is not task.state:
            task.state = new_state
            changed.append(task)
    return changed


def eligible_tasks(tasks: list[Task]) -> list[Task]:
    """Tasks that may start now: not settled, and all dependencies accepted."""
    accepted = done_ids(tasks)
    return [
        t for t in tasks
        if t.state not in SETTLED_STATES and dependencies_satisfied(t, accepted)
    ]


def validate(tasks: list[Task]) -> DependencyIssues:
    """Find unknown dependencies, self-dependencies, and cycles."""
    by_id = _by_id(tasks)
    issues = DependencyIssues()

    for task in tasks:
        missing = [dep for dep in task.dependencies if dep not in by_id]
        if missing:
            issues.unknown[task.id] = missing
        if task.id in task.dependencies:
            issues.self_dependent.append(task.id)

    issues.cycles = _find_cycles(by_id)
    return issues


def _find_cycles(by_id: dict[str, Task]) -> list[list[str]]:
    """DFS cycle detection over known dependency edges (unknown deps are ignored here)."""
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in by_id}
    cycles: list[list[str]] = []
    stack: list[str] = []

    def visit(node: str) -> None:
        color[node] = GRAY
        stack.append(node)
        for dep in by_id[node].dependencies:
            if dep not in by_id:
                continue  # unknown dep — reported separately by validate()
            if color[dep] == GRAY:
                # found a back edge -> extract the cycle from the stack
                idx = stack.index(dep)
                cycles.append(stack[idx:] + [dep])
            elif color[dep] == WHITE:
                visit(dep)
        stack.pop()
        color[node] = BLACK

    for tid in by_id:
        if color[tid] == WHITE:
            visit(tid)
    return cycles


def topological_order(tasks: list[Task]) -> list[str]:
    """A dependency-respecting order of task ids. Raises ValueError if the graph has a cycle."""
    by_id = _by_id(tasks)
    if _find_cycles(by_id):
        raise ValueError("Cannot order tasks: dependency cycle detected.")
    order: list[str] = []
    seen: set[str] = set()

    def visit(node: str) -> None:
        if node in seen:
            return
        for dep in by_id[node].dependencies:
            if dep in by_id:
                visit(dep)
        seen.add(node)
        order.append(node)

    for t in tasks:  # preserve input order for determinism
        visit(t.id)
    return order
