"""Planning engine (Run B).

Turns a project idea into base Markdown docs and a deterministic, routed task list. No LLM calls:
the task list comes from the fixed blueprint and routing comes from the fixed rules, so the whole
operation is reproducible.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from agentdesk import dependency_manager as deps
from agentdesk.models import Project, ProjectStatus, Task
from agentdesk.planner.blueprint import DEFAULT_BLUEPRINT, TaskSpec
from agentdesk.router import route
from agentdesk.scaffold import write_manifest
from agentdesk.storage import Storage

DOC_FILES = ["vision", "scope", "architecture", "risks", "success-criteria"]


class PlanError(Exception):
    """Raised when planning cannot proceed (e.g. missing project root)."""


def templates_dir() -> Path:
    """Locate the Jinja2 templates directory (override with AGENTDESK_TEMPLATES)."""
    override = os.environ.get("AGENTDESK_TEMPLATES")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[2] / "templates"


def _env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir())),
        autoescape=select_autoescape(enabled_extensions=()),  # plain text/markdown, no HTML escaping
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )


def task_id(index: int) -> str:
    """1-based index -> TASK-001 style id."""
    return f"TASK-{index:03d}"


def build_tasks(project: Project, blueprint: list[TaskSpec] | None = None) -> list[Task]:
    """Instantiate the blueprint into routed Task objects with initial states.

    - dependency indices are resolved to concrete TASK-IDs
    - the fixed router sets the recommended model
    - state is READY when there are no dependencies, otherwise BLOCKED
    """
    specs = blueprint or DEFAULT_BLUEPRINT
    tasks: list[Task] = []
    for i, spec in enumerate(specs, start=1):
        task = Task(
            id=task_id(i),
            project_id=project.id,
            name=spec.name,
            objective=spec.objective.format(project=project.name),
            context=f"Part of project '{project.name}'. Idea: {project.idea}",
            task_type=spec.task_type,
            risk=spec.risk,
            allowed_files=list(spec.allowed_files),
            forbidden_files=list(spec.forbidden_files),
            dependencies=[task_id(d) for d in spec.depends_on],
            acceptance_criteria=list(spec.acceptance_criteria),
            test_command=spec.test_command,
            definition_of_done="All acceptance criteria met; handover updated.",
        )
        decision = route(task)
        task.recommended_model = decision.effective_model
        tasks.append(task)

    # Validate the dependency graph, then derive initial ready/blocked states from it.
    issues = deps.validate(tasks)
    if not issues.ok:
        raise PlanError(f"Invalid task dependencies: {issues}")
    deps.recompute_states(tasks)
    return tasks


def _doc_context(project: Project) -> dict:
    return {
        "project": project,
        # vision
        "problem": project.idea,
        "solution": project.objective or "(to be refined during planning)",
        "success_criteria": [
            "The MVP goal is delivered and demonstrable.",
            "Core flows work end to end.",
        ],
        "risks": ["Scope creep", "Unclear acceptance criteria"],
        "decision": "advance",
        # scope
        "in_scope": [f"Deliver an MVP for: {project.idea}"],
        "out_scope": ["Anything not required for the MVP"],
        # risks.md
        "product_risks": ["Scope too broad for an MVP"],
        "technical_risks": ["Integration complexity", "State/data consistency"],
        "operational_risks": ["Single maintainer"],
        "mitigations": ["Hold a hard MVP line", "Generate only execution-useful artifacts"],
        # success-criteria.md
        "mvp_goal": project.objective or project.idea,
        "criteria": [
            "At least 10 structured, routed tasks generated.",
            "Base documents produced from the idea.",
        ],
    }


def write_docs(project: Project, root: Path) -> list[Path]:
    """Render the base Markdown documents into <root>/docs/."""
    env = _env()
    ctx = _doc_context(project)
    docs_dir = root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in DOC_FILES:
        template = env.get_template(f"{name}.md.j2")
        out = docs_dir / f"{name}.md"
        out.write_text(template.render(**ctx), encoding="utf-8")
        written.append(out)
    return written


def write_task_files(tasks: list[Task], root: Path) -> list[Path]:
    """Render each task into <root>/tasks/TASK-XXX.md."""
    env = _env()
    template = env.get_template("task.md.j2")
    tasks_dir = root / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for task in tasks:
        out = tasks_dir / f"{task.id}.md"
        out.write_text(template.render(task=task), encoding="utf-8")
        written.append(out)
    return written


def plan_project(store: Storage, project: Project, force: bool = False) -> list[Task]:
    """Generate the plan: docs + routed tasks, persisted to SQLite and written to disk.

    Idempotent: if the project already has tasks and `force` is False, returns the existing tasks
    without changes. With `force=True`, the existing plan is cleared and regenerated.
    Raises PlanError if the project has no on-disk root.
    """
    if not project.root_path:
        raise PlanError(f"Project '{project.id}' has no root_path; cannot write plan files.")
    root = Path(project.root_path)

    existing = store.list_tasks(project.id)
    if existing and not force:
        return existing
    if existing and force:
        store.clear_plan(project.id)

    tasks = build_tasks(project)
    for task in tasks:
        store.add_task(task)
        store.save_routing_decision(route(task))

    write_docs(project, root)
    write_task_files(tasks, root)

    project.status = ProjectStatus.PLANNING
    store.update_project(project)
    write_manifest(project, root)

    return tasks
