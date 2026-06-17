"""Build, render, and persist task handovers. No LLM, no Git — deterministic only."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agentdesk.models import Handover, Model, Project, Task
from agentdesk.storage import Storage
from agentdesk.templating import jinja_env

# Used when the user does not pass --summary. The quality gate treats this as a minor warning.
PLACEHOLDER_SUMMARY = "Not recorded automatically in MVP."


def next_recommended_task(task: Task, all_tasks: list[Task]) -> Optional[str]:
    """First task that depends on `task` (a natural next step), else None."""
    for t in all_tasks:
        if task.id in t.dependencies:
            return f"{t.id} - {t.name}"
    return None


def build_handover(
    task: Task,
    project: Project,
    all_tasks: list[Task],
    summary: Optional[str] = None,
) -> Handover:
    """Assemble a Handover model from observable task data."""
    return Handover(
        task_id=task.id,
        project_id=project.id,
        summary=summary or PLACEHOLDER_SUMMARY,
        files_changed=[],
        next_recommended_task=next_recommended_task(task, all_tasks),
        risks_remaining=f"Risk level: {task.risk.value}.",
    )


def render_handover(handover: Handover, task: Task, model: Optional[Model]) -> str:
    template = jinja_env().get_template("handover.md.j2")
    return template.render(
        handover=handover,
        task=task,
        model_label=model.value if model else "—",
    )


def generate_handover(
    store: Storage,
    project: Project,
    task: Task,
    model: Optional[Model],
    summary: Optional[str] = None,
) -> tuple[Handover, Path]:
    """Build, write to <root>/handovers/TASK-XXX.md, and persist the handover. Returns (handover, path)."""
    all_tasks = store.list_tasks(project.id)
    handover = build_handover(task, project, all_tasks, summary=summary)

    root = Path(project.root_path)
    out = root / "handovers" / f"{task.id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render_handover(handover, task, model), encoding="utf-8")

    handover.handover_path = f"handovers/{task.id}.md"
    store.save_handover(project.id, handover)
    return handover, out
