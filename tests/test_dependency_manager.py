"""Tests for the dependency manager (task-to-task dependency logic)."""

from agentdesk import dependency_manager as dm
from agentdesk.models import Task, TaskState
from agentdesk.planner import build_tasks
from agentdesk.models import Project


def _t(tid, deps=None, state=TaskState.TODO):
    return Task(id=tid, project_id="demo", name=tid, dependencies=deps or [], state=state)


def test_depends_on_alias_loads():
    t = Task.model_validate(
        {"id": "TASK-002", "project_id": "demo", "name": "x", "depends_on": ["TASK-001"]}
    )
    assert t.dependencies == ["TASK-001"]
    # canonical field name still serializes as "dependencies"
    assert '"dependencies"' in t.model_dump_json()


def test_validate_detects_unknown_and_self_and_cycles():
    tasks = [
        _t("A", ["GHOST"]),     # unknown dependency
        _t("B", ["B"]),         # self dependency
        _t("C", ["D"]),
        _t("D", ["C"]),         # cycle C <-> D
    ]
    issues = dm.validate(tasks)
    assert not issues.ok
    assert issues.unknown == {"A": ["GHOST"]}
    assert "B" in issues.self_dependent
    assert any(set(cycle) >= {"C", "D"} for cycle in issues.cycles)


def test_blueprint_graph_is_valid_and_acyclic():
    tasks = build_tasks(Project(id="demo", name="Demo", idea="idea"))
    issues = dm.validate(tasks)
    assert issues.ok
    order = dm.topological_order(tasks)
    # every dependency appears before the task that needs it
    pos = {tid: i for i, tid in enumerate(order)}
    for t in tasks:
        for dep in t.dependencies:
            assert pos[dep] < pos[t.id]


def test_dependencies_satisfied_and_eligible():
    a = _t("A")
    b = _t("B", ["A"])
    assert dm.dependencies_satisfied(a, set()) is True
    assert dm.dependencies_satisfied(b, set()) is False
    # only A is eligible while nothing is done
    assert [t.id for t in dm.eligible_tasks([a, b])] == ["A"]


def test_recompute_states_unblocks_when_dependency_done():
    a = _t("A", state=TaskState.DONE)
    b = _t("B", ["A"], state=TaskState.BLOCKED)
    c = _t("C", ["A", "B"], state=TaskState.BLOCKED)

    changed = dm.recompute_states([a, b, c])
    assert b.state is TaskState.READY        # its only dep (A) is done
    assert c.state is TaskState.BLOCKED       # B not done yet
    assert b in changed and c not in changed


def test_recompute_states_preserves_in_progress_tasks():
    a = _t("A", state=TaskState.DONE)
    b = _t("B", ["A"], state=TaskState.DOING)  # already being worked on
    dm.recompute_states([a, b])
    assert b.state is TaskState.DOING          # not auto-overridden
