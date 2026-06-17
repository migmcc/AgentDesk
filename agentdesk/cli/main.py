"""Agent Desk CLI.

Commands:
    agentdesk new "<idea>"     create a project (folder scaffold + persisted state)
    agentdesk plan <id>        generate base docs + a routed task list for a project
    agentdesk projects         list projects (state persists across restarts)
    agentdesk show <id>        show a project's details
    agentdesk version          print the version

Prompt generation, conflict guard, handover, and the quality gate arrive in later runs
(see docs/roadmap.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agentdesk import __version__
from agentdesk import dependency_manager as dm
from agentdesk.config import db_path, home_dir
from agentdesk.models import Model, Project, RiskLevel, Task, TaskState
from agentdesk.planner import PlanError, plan_project
from agentdesk.prompt_generator import generate_prompt, prompt_relpath
from agentdesk.router import DEFAULT_OVERRIDE_REASON, parse_model, route
from agentdesk.scaffold import create_project_folder, slugify
from agentdesk.storage import Storage

app = typer.Typer(
    help="Agent Desk — coordinate work across Codex, Claude Code, and local models (local-first).",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _storage() -> Storage:
    return Storage(db_path())


def _resolve_project(store: Storage, identifier: str) -> Optional[Project]:
    """Resolve a project by id (slug), by slugified name, or by exact (case-insensitive) name."""
    found = store.get_project(identifier) or store.get_project(slugify(identifier))
    if found:
        return found
    for proj in store.list_projects():
        if proj.name.lower() == identifier.lower():
            return proj
    return None


def _blocking_dependencies(store: Storage, project_id: str, task: Task) -> list[str]:
    """Dependencies of `task` that are not yet accepted (`done`)."""
    done = dm.done_ids(store.list_tasks(project_id))
    return [dep for dep in task.dependencies if dep not in done]


def _model_label(model: Optional[Model]) -> str:
    return model.value if model else "—"


@app.command()
def version() -> None:
    """Print the Agent Desk version and home directory."""
    console.print(f"Agent Desk [bold]{__version__}[/bold]")
    console.print(f"Home: {home_dir()}")


@app.command()
def new(
    idea: str = typer.Argument(..., help="The initial project idea, in natural language."),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Project name (defaults to the idea)."),
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Parent folder for the project (defaults to current directory)."
    ),
    objective: Optional[str] = typer.Option(None, "--objective", "-o", help="Optional project objective."),
) -> None:
    """Create a new project: scaffold its folder and persist its state locally."""
    project_name = name or idea
    parent = (path or Path.cwd()).expanduser().resolve()
    slug = slugify(project_name)

    with _storage() as store:
        if store.get_project(slug) is not None:
            console.print(f"[red]A project with id '[bold]{slug}[/bold]' already exists.[/red]")
            raise typer.Exit(code=1)

        try:
            root = create_project_folder(
                Project(id=slug, name=project_name, idea=idea, objective=objective), parent
            )
        except FileExistsError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

        project = Project(
            id=slug,
            name=project_name,
            idea=idea,
            objective=objective,
            root_path=str(root),
        )
        store.add_project(project)

    console.print(f"[green]Created project[/green] [bold]{slug}[/bold]")
    console.print(f"  Folder: {root}")
    console.print(f"  State:  {db_path()}")
    console.print("Next: generate a plan with: agentdesk plan " + slug)


@app.command()
def plan(
    project_id: str = typer.Argument(..., help="The project id (slug) to plan."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Regenerate, discarding any existing tasks for this project."
    ),
) -> None:
    """Generate base docs and a deterministic, routed task list for a project.

    Writes docs/*.md and tasks/TASK-XXX.md into the project folder and persists tasks to SQLite.
    Idempotent: without --force, an already-planned project is left unchanged.
    """
    with _storage() as store:
        project = store.get_project(project_id)
        if project is None:
            console.print(f"[red]No project with id '[bold]{project_id}[/bold]'.[/red]")
            raise typer.Exit(code=1)

        already = store.count_tasks(project_id)
        if already and not force:
            console.print(
                f"[yellow]Project '{project_id}' already has {already} tasks.[/yellow] "
                "Use --force to regenerate."
            )
            return

        try:
            tasks = plan_project(store, project, force=force)
        except PlanError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    ready = sum(1 for t in tasks if t.state.value == "ready")
    blocked = sum(1 for t in tasks if t.state.value == "blocked")
    console.print(
        f"[green]Planned[/green] [bold]{project_id}[/bold]: "
        f"{len(tasks)} tasks ({ready} ready, {blocked} blocked)"
    )

    table = Table(title=f"Tasks — {project.name}")
    table.add_column("ID", style="bold")
    table.add_column("Title")
    table.add_column("Type")
    table.add_column("Risk")
    table.add_column("Model")
    table.add_column("State")
    table.add_column("Deps")
    for t in tasks:
        table.add_row(
            t.id,
            t.name,
            t.task_type.value,
            t.risk.value,
            t.recommended_model.value if t.recommended_model else "—",
            t.state.value,
            ", ".join(t.dependencies) or "—",
        )
    console.print(table)
    console.print(f"Docs + task files written under: {project.root_path}")


@app.command()
def projects() -> None:
    """List all projects (proves state persists across restarts)."""
    with _storage() as store:
        items = store.list_projects()

    if not items:
        console.print("No projects yet. Create one with: agentdesk new \"<idea>\"")
        return

    table = Table(title="Agent Desk projects")
    table.add_column("ID", style="bold")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Created")
    for p in items:
        table.add_row(p.id, p.name, p.status.value, p.created_at.strftime("%Y-%m-%d %H:%M"))
    console.print(table)


@app.command()
def show(project_id: str = typer.Argument(..., help="The project id (slug).")) -> None:
    """Show a project's details."""
    with _storage() as store:
        project = store.get_project(project_id)
        if project is None:
            console.print(f"[red]No project with id '[bold]{project_id}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task_count = store.count_tasks(project_id)

    console.print(f"[bold]{project.name}[/bold]  ([cyan]{project.id}[/cyan])")
    console.print(f"  Status:    {project.status.value}")
    console.print(f"  Idea:      {project.idea}")
    if project.objective:
        console.print(f"  Objective: {project.objective}")
    console.print(f"  Folder:    {project.root_path}")
    console.print(f"  Tasks:     {task_count}")
    console.print(f"  Created:   {project.created_at.isoformat()}")


@app.command("route")
def route_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id, e.g. TASK-003."),
    override: Optional[str] = typer.Option(
        None, "--override", help="Manually override the model (codex | claude-code | local-model)."
    ),
) -> None:
    """Show a task's model routing, or apply a manual override (persisted)."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)

        decision = store.get_routing(proj.id, task_id) or route(task)

        if override is None:
            store.save_routing(proj.id, decision)  # ensure persisted
            console.print(f"[bold]{task.id}[/bold] — {task.name}\n")
            console.print(f"Recommended model: {_model_label(decision.recommended_model)}")
            console.print(f"Alternative model: {_model_label(decision.alternative_model)}")
            console.print(f"Risk: {decision.risk.value}")
            console.print(f"Task type: {decision.task_type.value}")
            if decision.was_overridden:
                console.print(f"Override model: {_model_label(decision.override_model)}")
                console.print(f"Override reason: {decision.override_reason}")
            console.print(f"\nReason:\n{decision.reason}")
            return

        # --override: change the persisted routing, preserving the original recommendation.
        try:
            model = parse_model(override)
        except ValueError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

        original = decision.recommended_model
        decision.manual_override = True
        decision.override_model = model
        decision.override_reason = DEFAULT_OVERRIDE_REASON
        store.save_routing(proj.id, decision)

        if task.risk is RiskLevel.HIGH and model is Model.LOCAL:
            console.print(
                "[yellow]Warning:[/yellow]\nYou are assigning a high-risk task to local-model.\n"
                "This is not recommended for execution.\n"
            )

        console.print(f"[bold]{task.id}[/bold] routing updated.\n")
        console.print(f"Original model: {_model_label(original)}")
        console.print(f"Override model: {_model_label(model)}")
        console.print(f"Reason: {decision.override_reason}")


@app.command("prompt")
def prompt_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id, e.g. TASK-003."),
    model: Optional[str] = typer.Option(
        None, "--model", help="Generate for a specific model without changing saved routing."
    ),
) -> None:
    """Generate a model-specific prompt file for a task (does not execute any model)."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)
        if not proj.root_path:
            console.print(f"[red]Project '{proj.id}' has no root_path; run plan first.[/red]")
            raise typer.Exit(code=1)

        if model is not None:
            # Ad-hoc model: affects only this prompt, never the persisted routing.
            try:
                effective = parse_model(model)
            except ValueError as exc:
                console.print(f"[red]{exc}[/red]")
                raise typer.Exit(code=1)
        else:
            decision = store.get_routing(proj.id, task_id) or route(task)
            effective = decision.effective_model
            if effective is None:
                console.print(
                    "[red]No model resolved for this task (internal/quality-gate). "
                    "Use --model to choose one.[/red]"
                )
                raise typer.Exit(code=1)

        blocking = _blocking_dependencies(store, proj.id, task)

        if task.state is TaskState.BLOCKED:
            console.print("[yellow]Warning:[/yellow]")
            console.print(f"{task.id} is currently blocked.\n")
            console.print("Blocked by:")
            for dep in blocking:
                console.print(f"- {dep}")
            console.print(
                "\nThis prompt can be generated for review/preparation, but the task should not "
                "be executed until dependencies are done.\n"
            )

        if task.risk is RiskLevel.HIGH and effective is Model.LOCAL:
            console.print(
                "[yellow]Warning:[/yellow] generating a local-model prompt for a high-risk task; "
                "not recommended for execution.\n"
            )

        path = generate_prompt(
            task, effective, Path(proj.root_path), project=proj, blocking_deps=blocking
        )

    console.print("Prompt generated:")
    console.print(prompt_relpath(effective, task.id))
    console.print(f"[dim]({path})[/dim]")


if __name__ == "__main__":
    app()
