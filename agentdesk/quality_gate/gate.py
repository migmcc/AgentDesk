"""Deterministic quality-gate logic.

Precedence: FAIL > NEEDS_HUMAN_REVIEW > PASS_WITH_WARNINGS > PASS.
Everything is derived from observable data (task, handover, locks, dependencies, routing).
"""

from __future__ import annotations

from pathlib import Path

from agentdesk.conflict_guard import check_start
from agentdesk.dependency_manager import done_ids
from agentdesk.git_integration import gate_findings as git_gate_findings
from agentdesk.handover import PLACEHOLDER_SUMMARY
from agentdesk.models import (
    GateOutcome,
    GateResult,
    Model,
    Project,
    RiskLevel,
    Task,
    TaskState,
    TaskType,
)
from agentdesk.prompt_generator import prompt_relpath
from agentdesk.router import route
from agentdesk.storage import Storage

TESTS_NOTE = "Tests not recorded automatically in MVP."
GATEABLE_STATES = {TaskState.DOING, TaskState.REVIEW}
HUMAN_REVIEW_TYPES = {TaskType.ARCHITECTURE, TaskType.REFACTOR, TaskType.QUALITY_GATE}


def run_gate(store: Storage, project: Project, task: Task) -> GateResult:
    """Evaluate a task and return a persisted-ready GateResult (caller persists)."""
    all_tasks = store.list_tasks(project.id)
    done = done_ids(all_tasks)
    pending_deps = [d for d in task.dependencies if d not in done]
    conflicts = check_start(store, project.id, task).conflicts
    handover = store.get_handover(project.id, task.id)
    routing = store.get_routing(project.id, task.id) or route(task)
    effective = routing.effective_model

    # Git-derived findings (warning if no repo; FAIL on forbidden change / missing branch).
    git_checks, git_failures, git_warnings = git_gate_findings(project.root_path, task)

    checks = {
        "Handover": "found" if handover else "missing",
        "Dependencies": "satisfied" if not pending_deps else "not satisfied",
        "Acceptance criteria": "found" if task.acceptance_criteria else "missing",
        "File conflicts": "none" if not conflicts else "detected",
        "Risk": task.risk.value,
        **git_checks,
    }

    # ---- FAIL conditions (hard blockers) ----
    failures: list[str] = list(git_failures)
    if handover is None:
        failures.append("Handover not found.")
    if task.state is TaskState.BLOCKED:
        failures.append(f"{task.id} is blocked by {', '.join(pending_deps) or 'dependencies'}.")
    elif pending_deps:
        failures.append(f"Dependencies not done: {', '.join(pending_deps)}.")
    if conflicts:
        for path, holder in conflicts:
            failures.append(f"File conflict: {path} locked by {holder}.")
    if not task.acceptance_criteria:
        failures.append("No acceptance criteria defined.")
    if task.state not in GATEABLE_STATES and task.state is not TaskState.BLOCKED:
        failures.append(f"Task state '{task.state.value}' does not allow a gate (need doing/review).")

    if failures:
        return GateResult(
            task_id=task.id, project_id=project.id, outcome=GateOutcome.FAIL,
            checks=checks, failures=failures,
        )

    # ---- NEEDS_HUMAN_REVIEW reasons ----
    reasons: list[str] = []
    if task.risk is RiskLevel.HIGH:
        reasons.append("Task is high risk.")
    if task.task_type is TaskType.ARCHITECTURE:
        reasons.append("Task type is architecture.")
    elif task.task_type is TaskType.REFACTOR:
        reasons.append("Task is a large refactor.")
    elif task.task_type is TaskType.QUALITY_GATE:
        reasons.append("Task is a quality-gate task.")
    if routing.override_model is Model.LOCAL and task.risk is RiskLevel.HIGH:
        reasons.append("Dangerous override: high-risk task assigned to local-model.")

    if reasons:
        return GateResult(
            task_id=task.id, project_id=project.id, outcome=GateOutcome.NEEDS_HUMAN_REVIEW,
            checks=checks, reasons=reasons,
        )

    # ---- Minor warnings (downgrade PASS -> PASS_WITH_WARNINGS) ----
    downgrade: list[str] = list(git_warnings)
    if not task.allowed_files:
        downgrade.append("Task has no allowed files defined.")
    if task.risk is RiskLevel.MEDIUM:
        downgrade.append("Task is medium risk.")
    if handover and handover.summary == PLACEHOLDER_SUMMARY:
        downgrade.append("Handover summary is a placeholder.")
    if effective is not None and project.root_path:
        prompt_path = Path(project.root_path) / prompt_relpath(effective, task.id)
        if not prompt_path.exists():
            downgrade.append("Prompt not generated on disk.")

    warnings = downgrade + [TESTS_NOTE]
    outcome = GateOutcome.PASS_WITH_WARNINGS if downgrade else GateOutcome.PASS
    return GateResult(
        task_id=task.id, project_id=project.id, outcome=outcome,
        checks=checks, warnings=warnings,
    )
