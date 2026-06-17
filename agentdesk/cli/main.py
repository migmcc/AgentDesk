"""Agent Desk CLI (Run A scope).

Commands:
    agentdesk new "<idea>"     create a project (folder scaffold + persisted state)
    agentdesk projects         list projects (state persists across restarts)
    agentdesk show <id>        show a project's details
    agentdesk version          print the version

Routing, planning, prompt generation, conflict guard, handover, and the quality gate arrive in
later runs (see docs/roadmap.md).
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agentdesk import __version__
from agentdesk.config import db_path, home_dir
from agentdesk.models import Project
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
    console.print("Next: planning (idea -> docs -> tasks) arrives in Run B.")


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


if __name__ == "__main__":
    app()
