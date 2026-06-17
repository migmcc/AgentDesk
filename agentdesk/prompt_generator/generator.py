"""Render and write per-model prompts. No LLM is called — this only produces text files."""

from __future__ import annotations

from pathlib import Path

from agentdesk.models import Model, Project, Task
from agentdesk.templating import jinja_env

# Where each model's prompts live, and which template renders them.
MODEL_DIRS: dict[Model, str] = {
    Model.CODEX: "codex",
    Model.CLAUDE_CODE: "claude-code",
    Model.LOCAL: "local-model",
}

MODEL_TEMPLATES: dict[Model, str] = {
    Model.CODEX: "codex_prompt.md.j2",
    Model.CLAUDE_CODE: "claude_code_prompt.md.j2",
    Model.LOCAL: "local_model_prompt.md.j2",
}


def prompt_relpath(model: Model, task_id: str) -> str:
    """Project-relative path where a prompt is written, e.g. prompts/codex/TASK-003.md."""
    return f"prompts/{MODEL_DIRS[model]}/{task_id}.md"


def render_prompt(
    task: Task,
    model: Model,
    project: Project | None = None,
    blocking_deps: list[str] | None = None,
) -> str:
    """Render a prompt for a task and model. `blocking_deps` adds a dependency-warning section."""
    env = jinja_env()
    template = env.get_template(MODEL_TEMPLATES[model])
    blocking_deps = blocking_deps or []
    return template.render(
        task=task,
        project=project,
        project_context=task.context,
        blocked=bool(blocking_deps),
        blocking_deps=blocking_deps,
    )


def generate_prompt(
    task: Task,
    model: Model,
    root: Path,
    project: Project | None = None,
    blocking_deps: list[str] | None = None,
) -> Path:
    """Render the prompt and write it under <root>/prompts/<model-dir>/TASK-XXX.md.

    Returns the absolute path written.
    """
    content = render_prompt(task, model, project=project, blocking_deps=blocking_deps)
    out = root / "prompts" / MODEL_DIRS[model] / f"{task.id}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return out
