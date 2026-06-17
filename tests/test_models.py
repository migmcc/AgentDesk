"""Tests for the core data model."""

from agentdesk.models import (
    GateOutcome,
    Model,
    Project,
    ProjectStatus,
    RiskLevel,
    RoutingDecision,
    Task,
    TaskState,
    TaskType,
)


def test_enum_values():
    assert {s.value for s in TaskState} == {
        "todo", "ready", "blocked", "doing", "review", "done", "rejected",
    }
    assert {o.value for o in GateOutcome} == {
        "PASS", "PASS_WITH_WARNINGS", "FAIL", "NEEDS_HUMAN_REVIEW",
    }
    assert {m.value for m in Model} == {"codex", "claude-code", "local"}
    assert len(list(TaskType)) == 12


def test_project_defaults():
    p = Project(id="demo", name="Demo", idea="an idea")
    assert p.status is ProjectStatus.CREATED
    assert p.created_at is not None


def test_task_defaults_and_git_ready_fields():
    t = Task(id="TASK-001", project_id="demo", name="Do thing")
    assert t.state is TaskState.TODO
    assert t.task_type is TaskType.IMPLEMENTATION
    assert t.risk is RiskLevel.MEDIUM
    assert t.allowed_files == [] and t.forbidden_files == []
    # Git-ready fields exist and default to empty / None (not functional in the MVP).
    assert t.branch_name is None
    assert t.commit_hash is None
    assert t.base_branch is None
    assert t.pr_url is None
    assert t.diff_summary is None
    assert t.changed_files == []


def test_routing_decision_effective_model_honors_override():
    d = RoutingDecision(
        task_id="TASK-001",
        task_type=TaskType.IMPLEMENTATION,
        risk=RiskLevel.MEDIUM,
        recommended_model=Model.CODEX,
        reason="objective",
        manual_override=True,
        override_model=Model.CLAUDE_CODE,
    )
    assert d.effective_model is Model.CLAUDE_CODE

    d2 = RoutingDecision(
        task_id="TASK-002",
        task_type=TaskType.IMPLEMENTATION,
        risk=RiskLevel.MEDIUM,
        recommended_model=Model.CODEX,
        reason="objective",
    )
    assert d2.effective_model is Model.CODEX
