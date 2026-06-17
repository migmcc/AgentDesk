"""Advisory assist engine: gather task context, ask the local model, write a report.

Never changes task state, the official handover, project code, or Git. Output is advisory and lands
in the project's reports/ directory for the user to act on.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from agentdesk.local_model.providers import BaseProvider
from agentdesk.models import Project, Task
from agentdesk.prompt_generator import prompt_relpath
from agentdesk.router import route
from agentdesk.storage import Storage
from agentdesk.templating import jinja_env

MODES = ["summary", "prompt-review", "doc-check", "handover-draft"]

MODE_TEMPLATE = {
    "summary": "local_summary.md.j2",
    "prompt-review": "local_prompt_review.md.j2",
    "doc-check": "local_doc_check.md.j2",
    "handover-draft": "local_handover_draft.md.j2",
}

DOC_NAMES = ["vision", "scope", "architecture", "risks", "success-criteria"]


def _read(path: Path) -> Optional[str]:
    return path.read_text(encoding="utf-8") if path.exists() else None


def build_prompt(store: Storage, project: Project, task: Task, mode: str) -> str:
    """Render the internal prompt sent to the local model for `mode`."""
    template = jinja_env().get_template(MODE_TEMPLATE[mode])
    root = Path(project.root_path) if project.root_path else None
    routing = store.get_routing(project.id, task.id) or route(task)
    ctx: dict = {
        "task": task,
        "project": project,
        "routing": routing,
        "effective_model": routing.effective_model,
    }

    if mode == "prompt-review":
        prompt_text = None
        if root and routing.effective_model:
            prompt_text = _read(root / prompt_relpath(routing.effective_model, task.id))
        ctx["prompt_text"] = prompt_text
    elif mode == "doc-check":
        ctx["docs"] = {n: (_read(root / "docs" / f"{n}.md") if root else None) for n in DOC_NAMES}
    elif mode == "handover-draft":
        ctx["gate"] = store.get_gate_result(project.id, task.id)
        ctx["diff_summary"] = task.diff_summary

    return template.render(**ctx)


def run_assist(
    store: Storage, project: Project, task: Task, mode: str, provider: BaseProvider
) -> Path:
    """Build the prompt, call the provider, and write reports/TASK-XXX-<mode>.md. Returns the path."""
    prompt = build_prompt(store, project, task, mode)
    output = provider.complete(prompt)

    root = Path(project.root_path)
    out = root / "reports" / f"{task.id}-{mode}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    header = (
        f"# Local Model Report - {task.id} ({mode})\n\n"
        f"- Provider: {provider.name}\n"
        f"- Task: {task.id} - {task.name}\n"
        f"- State: {task.state.value}\n\n"
        "> Advisory output. The local model did not execute code or modify any files.\n\n"
        "---\n\n"
    )
    out.write_text(header + output.strip() + "\n", encoding="utf-8")
    return out
