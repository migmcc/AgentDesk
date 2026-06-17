"""Dependency manager — task-to-task dependency logic across models.

Agent Desk coordinates more than file conflicts: a task assigned to one model often cannot start
until another task (possibly assigned to a different model) is finished and accepted. This module
is the structural foundation for that:

- `validate()` — catch unknown dependencies, self-dependencies, and cycles in a task set.
- `dependencies_satisfied()` / `eligible_tasks()` — which tasks may start now.
- `recompute_states()` — move tasks between `blocked` and `ready` as dependencies reach `done`.

A task may only start once **all** its dependencies are accepted (state `done`). In-progress or
finished tasks (`doing` / `review` / `done` / `rejected`) are never auto-overridden.
"""

from agentdesk.dependency_manager.manager import (
    DependencyIssues,
    SETTLED_STATES,
    compute_state,
    dependencies_satisfied,
    eligible_tasks,
    recompute_states,
    topological_order,
    validate,
)

__all__ = [
    "DependencyIssues",
    "SETTLED_STATES",
    "compute_state",
    "dependencies_satisfied",
    "eligible_tasks",
    "recompute_states",
    "topological_order",
    "validate",
]
