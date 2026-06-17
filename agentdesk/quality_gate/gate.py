"""Advanced, deterministic quality gate.

Combines six check groups — scope, risk, diff (Git), prompt, test, handover — into a single
GateResult with structured per-check lines plus failures / warnings / human-review reasons and a
recommended action. It never runs tests or models; test results are recorded manually.

Outcome precedence: FAIL > NEEDS_HUMAN_REVIEW > PASS_WITH_WARNINGS > PASS.
"""

from __future__ import annotations

from pathlib import Path

from agentdesk.conflict_guard import check_start
from agentdesk.dependency_manager import done_ids
from agentdesk.git_integration import repo_analysis
from agentdesk.handover import PLACEHOLDER_SUMMARY
from agentdesk.models import (
    CheckLevel,
    GateCheck,
    GateOutcome,
    GateResult,
    Model,
    Project,
    RiskLevel,
    Task,
    TaskState,
    TaskType,
    TestOutcome,
)
from agentdesk.prompt_generator import MODEL_DIRS, prompt_relpath
from agentdesk.router import route
from agentdesk.storage import Storage

GATEABLE_STATES = {TaskState.DOING, TaskState.REVIEW}
CODE_TYPES = {TaskType.IMPLEMENTATION, TaskType.REFACTOR, TaskType.BUGFIX, TaskType.TESTING, TaskType.SETUP}
# Task types that do not require recorded tests.
NO_TEST_TYPES = {TaskType.DOCUMENTATION, TaskType.HANDOVER, TaskType.RESEARCH, TaskType.REVIEW}
# Heuristic markers for sensitive files (advisory human review).
SENSITIVE_MARKERS = ("config", "settings", "storage", "schema", "migration", "secret", ".env")


class _Accumulator:
    def __init__(self) -> None:
        self.checks: list[GateCheck] = []
        self.failures: list[str] = []
        self.warnings: list[str] = []
        self.reasons: list[str] = []

    def ok(self, msg: str) -> None:
        self.checks.append(GateCheck(level=CheckLevel.PASS, message=msg))

    def warn(self, msg: str, *, record: bool = True) -> None:
        self.checks.append(GateCheck(level=CheckLevel.WARN, message=msg))
        if record:
            self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.checks.append(GateCheck(level=CheckLevel.FAIL, message=msg))
        self.failures.append(msg)

    def review(self, msg: str) -> None:
        self.checks.append(GateCheck(level=CheckLevel.REVIEW, message=msg))
        self.reasons.append(msg)


def _scope_check(task: Task, acc: _Accumulator) -> None:
    if task.acceptance_criteria:
        acc.ok("Acceptance criteria found")
    else:
        acc.fail("No acceptance criteria defined.")

    if task.allowed_files:
        acc.ok("Allowed files defined")
    elif task.task_type in CODE_TYPES:
        acc.warn("Task has no allowed files defined.")
    else:
        acc.ok("Allowed files not required for this task type")

    if task.risk is RiskLevel.HIGH and not task.forbidden_files:
        acc.warn("High-risk task has no forbidden files defined.")

    if len((task.objective or "").strip()) < 15:
        acc.warn("Task description is empty or very short.")


def _state_and_deps_check(store: Storage, project: Project, task: Task, acc: _Accumulator) -> None:
    tasks = store.list_tasks(project.id)
    done = done_ids(tasks)
    pending = [d for d in task.dependencies if d not in done]
    if task.state is TaskState.BLOCKED:
        acc.fail(f"{task.id} is blocked by {', '.join(pending) or 'dependencies'}.")
    elif pending:
        acc.fail(f"Dependencies not done: {', '.join(pending)}.")
    else:
        acc.ok("Dependencies satisfied")

    conflicts = check_start(store, project.id, task).conflicts
    if conflicts:
        for path, holder in conflicts:
            acc.fail(f"File conflict: {path} locked by {holder}.")
    else:
        acc.ok("No file lock conflicts")

    if task.state not in GATEABLE_STATES and task.state is not TaskState.BLOCKED:
        acc.fail(f"Task state '{task.state.value}' does not allow a gate (need doing/review).")


def _risk_check(task: Task, routing, changed: list[str], acc: _Accumulator) -> None:
    acc.ok(f"Risk level: {task.risk.value}")
    if task.risk is RiskLevel.HIGH:
        acc.review("Task is high risk.")
    if task.task_type is TaskType.ARCHITECTURE:
        acc.review("Task type is architecture.")
    elif task.task_type is TaskType.REFACTOR and task.risk is not RiskLevel.LOW:
        acc.review(f"Task is a refactor (risk {task.risk.value}).")
    elif task.task_type is TaskType.QUALITY_GATE:
        acc.review("Task is a quality-gate task.")
    if routing.override_model is Model.LOCAL and task.risk is RiskLevel.HIGH:
        acc.review("Dangerous override: high-risk task assigned to local-model.")
    sensitive = [c for c in changed if any(m in c.lower() for m in SENSITIVE_MARKERS)]
    if sensitive:
        acc.review(f"Changed files touch sensitive areas: {', '.join(sensitive)}.")


def _diff_check(project: Project, task: Task, acc: _Accumulator):
    analysis = repo_analysis(project.root_path, task)
    if not analysis.is_repo:
        acc.warn("Git repository not detected.")
        return analysis
    acc.ok("Git repository detected")
    if analysis.error:
        acc.fail(f"Git command failed: {analysis.error}")
        return analysis
    if analysis.branch_missing:
        acc.fail(f"Branch '{analysis.branch_name}' associated with {task.id} does not exist.")
        return analysis
    if analysis.branch_associated:
        acc.ok(f"Branch associated: {analysis.branch_name}")
    elif task.task_type in CODE_TYPES:
        acc.warn("No branch associated with the task.")

    if analysis.forbidden:
        for f in analysis.forbidden:
            acc.fail(f"Forbidden file changed: {f}.")
    else:
        acc.ok("No forbidden files changed")

    if analysis.out_of_scope:
        for f in analysis.out_of_scope:
            acc.warn(f"Changed file outside allowed scope: {f}.")
    if not analysis.changed and task.task_type is TaskType.IMPLEMENTATION:
        acc.warn("No changes detected for an implementation task.")
    return analysis


def _prompt_check(project: Project, task: Task, routing, acc: _Accumulator) -> None:
    effective = routing.effective_model
    if effective is None:
        acc.ok("No prompt required (internal task)")
        return
    root = Path(project.root_path) if project.root_path else None
    if root and (root / prompt_relpath(effective, task.id)).exists():
        acc.ok(f"Prompt generated for {effective.value}")
        return
    # Effective prompt missing — is there one for a different model?
    other = []
    if root:
        for model, sub in MODEL_DIRS.items():
            if model is not effective and (root / "prompts" / sub / f"{task.id}.md").exists():
                other.append(model.value)
    if other:
        acc.warn(f"Prompt exists for {', '.join(other)} but not the effective model "
                 f"({effective.value}).")
    else:
        acc.warn("Prompt not generated on disk.")


def _test_check(store: Storage, project: Project, task: Task, acc: _Accumulator) -> None:
    result = store.get_test_result(project.id, task.id)
    if result is None:
        if task.task_type in NO_TEST_TYPES:
            acc.ok(f"Tests not required for {task.task_type.value}")
        else:
            acc.warn("Tests not recorded.")
        return
    if result.result is TestOutcome.PASSED:
        acc.ok(f"Tests passed ({result.command or 'recorded'})")
    elif result.result is TestOutcome.FAILED:
        acc.fail(f"Tests failed: {result.notes or result.command or 'recorded as failed'}.")
    elif result.result is TestOutcome.NOT_RUN:
        acc.warn("Tests recorded as not-run.")
    else:
        acc.warn("Test result is unknown.")


def _handover_check(store: Storage, project: Project, task: Task, acc: _Accumulator) -> None:
    handover = store.get_handover(project.id, task.id)
    if handover is None:
        acc.fail("Handover not found.")
        return
    acc.ok("Handover found")
    if handover.summary.strip() == PLACEHOLDER_SUMMARY or not handover.summary.strip():
        acc.warn("Handover summary is a placeholder.")


def run_gate(store: Storage, project: Project, task: Task) -> GateResult:
    """Evaluate a task across all checks and return a persisted-ready GateResult."""
    acc = _Accumulator()
    routing = store.get_routing(project.id, task.id) or route(task)

    _scope_check(task, acc)
    _state_and_deps_check(store, project, task, acc)
    analysis = _diff_check(project, task, acc)
    _risk_check(task, routing, analysis.changed, acc)
    _prompt_check(project, task, routing, acc)
    _test_check(store, project, task, acc)
    _handover_check(store, project, task, acc)

    if acc.failures:
        outcome = GateOutcome.FAIL
        action = "Resolve the failures above before accepting this task."
    elif acc.reasons:
        outcome = GateOutcome.NEEDS_HUMAN_REVIEW
        action = "Review manually before marking as done."
    elif acc.warnings:
        outcome = GateOutcome.PASS_WITH_WARNINGS
        action = "Review warnings before marking task as done."
    else:
        outcome = GateOutcome.PASS
        action = "Task looks ready to accept."

    return GateResult(
        task_id=task.id,
        project_id=project.id,
        outcome=outcome,
        checks=acc.checks,
        failures=acc.failures,
        warnings=acc.warnings,
        reasons=acc.reasons,
        recommended_action=action,
    )
