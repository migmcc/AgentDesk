"""Deterministic task blueprint for the planning engine.

The planner does NOT call any LLM. It instantiates this fixed, ordered skeleton of standard
software-project tasks for the project, then applies the routing rules. The result is fully
reproducible — which is what makes Run B testable. A model (Claude Code / Codex) refines the
generated tasks later; the engine itself stays deterministic.

Each spec yields one task. `depends_on` references the 1-based positions in this list, resolved to
concrete TASK-IDs by the engine. Files are sensible placeholders meant to be refined per project.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agentdesk.models import RiskLevel, TaskType


@dataclass(frozen=True)
class TaskSpec:
    name: str
    task_type: TaskType
    risk: RiskLevel
    objective: str
    depends_on: tuple[int, ...] = ()  # 1-based indices into DEFAULT_BLUEPRINT
    allowed_files: tuple[str, ...] = ()
    forbidden_files: tuple[str, ...] = ()
    acceptance_criteria: tuple[str, ...] = ()
    test_command: str | None = None


# Ordered skeleton — 12 tasks (>= the 10 required). Order defines TASK-001..TASK-012.
DEFAULT_BLUEPRINT: list[TaskSpec] = [
    TaskSpec(
        name="Design initial architecture",
        task_type=TaskType.ARCHITECTURE,
        risk=RiskLevel.HIGH,
        objective="Define the stack, module boundaries, and data flow for {project}.",
        allowed_files=("docs/architecture.md",),
        forbidden_files=("src/**",),
        acceptance_criteria=(
            "Architecture document covers stack, modules, and data flow.",
            "Key technical decisions are recorded.",
        ),
    ),
    TaskSpec(
        name="Set up project scaffolding and tooling",
        task_type=TaskType.SETUP,
        risk=RiskLevel.LOW,
        objective="Create the repository scaffold, packaging, and developer tooling.",
        depends_on=(1,),
        allowed_files=("pyproject.toml", "src/**", ".gitignore"),
        forbidden_files=("docs/**",),
        acceptance_criteria=("Project installs cleanly.", "Lint/test tooling runs."),
    ),
    TaskSpec(
        name="Implement core data model",
        task_type=TaskType.IMPLEMENTATION,
        risk=RiskLevel.MEDIUM,
        objective="Implement the core domain types and persistence for {project}.",
        depends_on=(2,),
        allowed_files=("src/**",),
        forbidden_files=("tests/**",),
        acceptance_criteria=("Core types defined.", "Round-trips through storage."),
    ),
    TaskSpec(
        name="Implement primary feature module",
        task_type=TaskType.IMPLEMENTATION,
        risk=RiskLevel.MEDIUM,
        objective="Implement the primary user-facing capability of {project}.",
        depends_on=(3,),
        allowed_files=("src/**",),
        forbidden_files=("tests/**",),
        acceptance_criteria=("Primary flow works end to end.",),
    ),
    TaskSpec(
        name="Implement secondary feature module",
        task_type=TaskType.IMPLEMENTATION,
        risk=RiskLevel.MEDIUM,
        objective="Implement the secondary capability of {project}.",
        depends_on=(3,),
        allowed_files=("src/**",),
        forbidden_files=("tests/**",),
        acceptance_criteria=("Secondary flow works end to end.",),
    ),
    TaskSpec(
        name="Write tests for core modules",
        task_type=TaskType.TESTING,
        risk=RiskLevel.MEDIUM,
        objective="Add unit tests covering the core and feature modules.",
        depends_on=(4, 5),
        allowed_files=("tests/**",),
        forbidden_files=("src/**",),
        acceptance_criteria=("Critical paths covered.", "Test suite is green."),
        test_command="pytest",
    ),
    TaskSpec(
        name="Fix issues found during testing",
        task_type=TaskType.BUGFIX,
        risk=RiskLevel.MEDIUM,
        objective="Resolve defects surfaced by the test pass.",
        depends_on=(6,),
        allowed_files=("src/**",),
        acceptance_criteria=("Known defects fixed.", "Tests still green."),
        test_command="pytest",
    ),
    TaskSpec(
        name="Refactor for clarity after first pass",
        task_type=TaskType.REFACTOR,
        risk=RiskLevel.MEDIUM,
        objective="Improve structure and naming without changing behavior.",
        depends_on=(6,),
        allowed_files=("src/**",),
        acceptance_criteria=("No behavior change.", "Tests still green."),
        test_command="pytest",
    ),
    TaskSpec(
        name="Write user and developer documentation",
        task_type=TaskType.DOCUMENTATION,
        risk=RiskLevel.LOW,
        objective="Document how to install, use, and develop {project}.",
        depends_on=(4, 5),
        allowed_files=("docs/**", "README.md"),
        forbidden_files=("src/**",),
        acceptance_criteria=("Install + usage documented.",),
    ),
    TaskSpec(
        name="Structural review of the implementation",
        task_type=TaskType.REVIEW,
        risk=RiskLevel.MEDIUM,
        objective="Review the implementation for correctness and structure.",
        depends_on=(7, 8),
        acceptance_criteria=("Review notes captured.", "Follow-ups filed as tasks."),
    ),
    TaskSpec(
        name="Run quality gate before release",
        task_type=TaskType.QUALITY_GATE,
        risk=RiskLevel.HIGH,
        objective="Validate the work against acceptance criteria before acceptance.",
        depends_on=(10,),
        acceptance_criteria=("Gate outcome recorded.",),
    ),
    TaskSpec(
        name="Produce handover and next steps",
        task_type=TaskType.HANDOVER,
        risk=RiskLevel.LOW,
        objective="Summarize what changed and recommend the next task.",
        depends_on=(11,),
        allowed_files=("handovers/**",),
        acceptance_criteria=("Handover is readable by humans and models.",),
    ),
]
