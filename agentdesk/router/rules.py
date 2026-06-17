"""Fixed routing rules + risk-based model permissions.

Locked decisions (docs/decisions.md):
- Routing is a FIXED rule table + manual override. No scoring in the MVP.
- Three risk levels (low / medium / high) gate which models may execute a task.

Each task type maps to a recommended model and an alternative. A few types are risk-dependent
(review, quality-gate, research) and resolve at routing time. The router always records: the
recommended model, a human reason, an alternative, and whether the local model is allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from agentdesk.models import Model, RiskLevel, RoutingDecision, Task, TaskType

# Task types whose final execution the local model may handle (when risk permits).
LOCAL_FRIENDLY_TYPES: set[TaskType] = {
    TaskType.DOCUMENTATION,
    TaskType.HANDOVER,
    TaskType.REVIEW,
    TaskType.RESEARCH,
}


def local_model_allowed(task_type: TaskType, risk: RiskLevel) -> bool:
    """Whether the local model may EXECUTE this task (not merely assist).

    - high risk  -> never (local forbidden for execution)
    - low risk   -> always allowed
    - medium     -> only for inherently support-style task types (docs, handover, review, research)
    """
    if risk is RiskLevel.HIGH:
        return False
    if risk is RiskLevel.LOW:
        return True
    return task_type in LOCAL_FRIENDLY_TYPES


@dataclass(frozen=True)
class Rule:
    """A routing rule. `resolver` (if set) overrides the static recommendation using risk."""

    recommended: Optional[Model]
    alternative: Optional[Model]
    reason: str
    resolver: Optional[Callable[[RiskLevel], tuple[Optional[Model], Optional[Model], str]]] = None


def _review_resolver(risk: RiskLevel) -> tuple[Optional[Model], Optional[Model], str]:
    if risk is RiskLevel.LOW:
        return Model.LOCAL, Model.CLAUDE_CODE, "Simple review — local model is sufficient."
    return Model.CLAUDE_CODE, Model.LOCAL, "Structural review — Claude Code for deeper reasoning."


def _quality_gate_resolver(risk: RiskLevel) -> tuple[Optional[Model], Optional[Model], str]:
    if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH):
        return (
            Model.CLAUDE_CODE,
            None,
            "Internal system runs the gate; Claude Code reviews because risk is medium/high.",
        )
    return None, None, "Handled by the internal quality-gate system (low risk)."


def _research_resolver(risk: RiskLevel) -> tuple[Optional[Model], Optional[Model], str]:
    if risk is RiskLevel.HIGH:
        return Model.CLAUDE_CODE, Model.LOCAL, "High-criticality research — Claude Code for reasoning."
    return Model.LOCAL, Model.CLAUDE_CODE, "Lower-criticality research — local model to save tokens."


# Static + risk-resolved rules, one per task type.
ROUTING_RULES: dict[TaskType, Rule] = {
    TaskType.PLANNING: Rule(Model.CLAUDE_CODE, Model.LOCAL, "Planning needs broad reasoning."),
    TaskType.ARCHITECTURE: Rule(Model.CLAUDE_CODE, Model.CODEX, "Architecture needs deep reasoning."),
    TaskType.SETUP: Rule(Model.CODEX, Model.CLAUDE_CODE, "Setup is objective and well-defined."),
    TaskType.IMPLEMENTATION: Rule(Model.CODEX, Model.CLAUDE_CODE, "Objective implementation with clear criteria."),
    TaskType.BUGFIX: Rule(Model.CODEX, Model.CLAUDE_CODE, "Isolated bug fix — objective task."),
    TaskType.TESTING: Rule(Model.CODEX, Model.CLAUDE_CODE, "Test creation is objective."),
    TaskType.REFACTOR: Rule(Model.CLAUDE_CODE, Model.CODEX, "Refactor needs analysis of existing code."),
    TaskType.DOCUMENTATION: Rule(Model.LOCAL, Model.CLAUDE_CODE, "Docs are low risk — prefer local to save tokens."),
    TaskType.HANDOVER: Rule(Model.LOCAL, Model.CLAUDE_CODE, "Handovers are repetitive, low-value — local model."),
    TaskType.REVIEW: Rule(None, None, "Resolved by risk.", resolver=_review_resolver),
    TaskType.QUALITY_GATE: Rule(None, None, "Resolved by risk.", resolver=_quality_gate_resolver),
    TaskType.RESEARCH: Rule(None, None, "Resolved by risk.", resolver=_research_resolver),
}


def route(task: Task, override_model: Optional[Model] = None) -> RoutingDecision:
    """Produce a RoutingDecision for a task.

    If `override_model` is given, the recommendation is still computed and recorded, but the
    decision is flagged as a manual override and `effective_model` will return the override.
    """
    rule = ROUTING_RULES[task.task_type]
    if rule.resolver is not None:
        recommended, alternative, reason = rule.resolver(task.risk)
    else:
        recommended, alternative, reason = rule.recommended, rule.alternative, rule.reason

    return RoutingDecision(
        task_id=task.id,
        task_type=task.task_type,
        risk=task.risk,
        recommended_model=recommended,
        reason=reason,
        alternative_model=alternative,
        local_model_allowed=local_model_allowed(task.task_type, task.risk),
        manual_override=override_model is not None,
        override_model=override_model,
    )
