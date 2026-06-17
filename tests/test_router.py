"""Tests for the fixed routing rules and risk-based model permissions."""

import pytest

from agentdesk.models import Model, RiskLevel, Task, TaskType
from agentdesk.router import local_model_allowed, route


def _task(task_type: TaskType, risk: RiskLevel = RiskLevel.MEDIUM) -> Task:
    return Task(id="TASK-001", project_id="demo", name="t", task_type=task_type, risk=risk)


@pytest.mark.parametrize(
    "task_type,expected",
    [
        (TaskType.PLANNING, Model.CLAUDE_CODE),
        (TaskType.ARCHITECTURE, Model.CLAUDE_CODE),
        (TaskType.SETUP, Model.CODEX),
        (TaskType.IMPLEMENTATION, Model.CODEX),
        (TaskType.BUGFIX, Model.CODEX),
        (TaskType.TESTING, Model.CODEX),
        (TaskType.REFACTOR, Model.CLAUDE_CODE),
        (TaskType.DOCUMENTATION, Model.LOCAL),
        (TaskType.HANDOVER, Model.LOCAL),
    ],
)
def test_static_recommendations(task_type, expected):
    assert route(_task(task_type)).recommended_model is expected


def test_review_is_risk_dependent():
    assert route(_task(TaskType.REVIEW, RiskLevel.LOW)).recommended_model is Model.LOCAL
    assert route(_task(TaskType.REVIEW, RiskLevel.HIGH)).recommended_model is Model.CLAUDE_CODE


def test_quality_gate_is_internal_on_low_and_claude_on_higher():
    low = route(_task(TaskType.QUALITY_GATE, RiskLevel.LOW))
    assert low.recommended_model is None  # internal system only
    high = route(_task(TaskType.QUALITY_GATE, RiskLevel.HIGH))
    assert high.recommended_model is Model.CLAUDE_CODE


def test_research_depends_on_criticality():
    assert route(_task(TaskType.RESEARCH, RiskLevel.LOW)).recommended_model is Model.LOCAL
    assert route(_task(TaskType.RESEARCH, RiskLevel.HIGH)).recommended_model is Model.CLAUDE_CODE


def test_local_model_allowed_matrix():
    # high risk -> never
    assert local_model_allowed(TaskType.DOCUMENTATION, RiskLevel.HIGH) is False
    assert local_model_allowed(TaskType.IMPLEMENTATION, RiskLevel.HIGH) is False
    # low risk -> always
    assert local_model_allowed(TaskType.IMPLEMENTATION, RiskLevel.LOW) is True
    # medium -> only support-style types
    assert local_model_allowed(TaskType.HANDOVER, RiskLevel.MEDIUM) is True
    assert local_model_allowed(TaskType.IMPLEMENTATION, RiskLevel.MEDIUM) is False


def test_manual_override_is_recorded():
    d = route(_task(TaskType.IMPLEMENTATION), override_model=Model.CLAUDE_CODE)
    assert d.recommended_model is Model.CODEX  # recommendation still computed
    assert d.manual_override is True
    assert d.effective_model is Model.CLAUDE_CODE


def test_every_task_type_has_a_rule():
    for tt in TaskType:
        decision = route(_task(tt))
        assert decision.task_id == "TASK-001"
        assert decision.reason
