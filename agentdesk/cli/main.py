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

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from agentdesk import __version__
from agentdesk import dependency_manager as dm
from agentdesk import git_integration as git
from agentdesk.conflict_guard import ConflictDecision, check_start
from agentdesk.config import db_path, home_dir
from agentdesk.handover import generate_handover
from agentdesk.local_model import (
    MODES as LOCAL_MODES,
    LocalModelConfig,
    LocalModelError,
    get_provider,
    run_assist,
)
from agentdesk.models import (
    FileLock,
    Model,
    Project,
    RiskLevel,
    Task,
    TaskState,
    TestOutcome,
    TestResult,
)
from agentdesk.planner import PlanError, plan_project
from agentdesk.project_validator import validate_project
from agentdesk.prompt_generator import generate_prompt, prompt_relpath
from agentdesk.quality_gate import run_gate
from agentdesk.router import DEFAULT_OVERRIDE_REASON, parse_model, route
from agentdesk.scaffold import create_project_folder, slugify
from agentdesk.state_machine import InvalidTransition, apply_transition
from agentdesk.storage import FileLockConflict, Storage

app = typer.Typer(
    help="Agent Desk - coordinate work across Codex, Claude Code, and local models (local-first).",
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
    return model.value if model else "-"


def _effective_model(store: Storage, project_id: str, task: Task) -> Optional[Model]:
    """The model that would actually run a task (persisted routing, honoring overrides)."""
    decision = store.get_routing(project_id, task.id) or route(task)
    return decision.effective_model


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
    project: str = typer.Argument(..., help="The project id or name to plan."),
    force: bool = typer.Option(
        False, "--force", "-f", help="Regenerate, discarding any existing tasks for this project."
    ),
) -> None:
    """Generate base docs and a deterministic, routed task list for a project.

    Writes docs/*.md and tasks/TASK-XXX.md into the project folder and persists tasks to SQLite.
    Idempotent: without --force, an already-planned project is left unchanged.
    """
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)

        already = store.count_tasks(proj.id)
        if already and not force:
            console.print(
                f"[yellow]Project '{proj.id}' already has {already} tasks.[/yellow] "
                "Use --force to regenerate."
            )
            return

        try:
            tasks = plan_project(store, proj, force=force)
        except PlanError as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)

    ready = sum(1 for t in tasks if t.state.value == "ready")
    blocked = sum(1 for t in tasks if t.state.value == "blocked")
    console.print(
        f"[green]Planned[/green] [bold]{proj.id}[/bold]: "
        f"{len(tasks)} tasks ({ready} ready, {blocked} blocked)"
    )

    table = Table(title=f"Tasks - {proj.name}")
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
            t.recommended_model.value if t.recommended_model else "-",
            t.state.value,
            ", ".join(t.dependencies) or "-",
        )
    console.print(table)
    console.print(f"Docs + task files written under: {proj.root_path}")


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
            console.print(f"[bold]{task.id}[/bold] - {task.name}\n")
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


@app.command("status")
def status_command(project: str = typer.Argument(..., help="Project id or name.")) -> None:
    """Show a project summary: state counts, in-progress tasks, locks, and next ready tasks."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        tasks = store.list_tasks(proj.id)
        locks = store.locks_for_project(proj.id)
        done = dm.done_ids(tasks)
        routing = {t.id: _effective_model(store, proj.id, t) for t in tasks}

    console.print(f"Project: {proj.name}\n")

    console.print("Tasks:")
    for state in TaskState:
        count = sum(1 for t in tasks if t.state is state)
        console.print(f"- {state.value}: {count}")

    doing = [t for t in tasks if t.state is TaskState.DOING]
    if doing:
        console.print("\nIn progress:")
        for t in doing:
            console.print(f"- {t.id} - {t.name}")

    console.print("\nActive locks:")
    if locks:
        for lock in locks:
            console.print(f"- {lock.task_id} -> {lock.file_path}")
    else:
        console.print("- (none)")

    ready = [t for t in tasks if t.state is TaskState.READY]
    console.print("\nNext recommended tasks:")
    if ready:
        for t in ready:
            console.print(f"- {t.id} - {t.name} [{_model_label(routing[t.id])}]")
    else:
        console.print("- (none ready)")

    blocked = [t for t in tasks if t.state is TaskState.BLOCKED]
    if blocked:
        console.print("\nBlocked tasks:")
        for t in blocked:
            pending = [d for d in t.dependencies if d not in done]
            console.print(f"- {t.id} - {t.name} (waiting on: {', '.join(pending) or '-'})")


@app.command("start")
def start_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id, e.g. TASK-003."),
) -> None:
    """Start a task: check dependencies + file conflicts, lock files, move to `doing`."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)

        # 1. Dependency manager: is the task ordered to run?
        if task.state is TaskState.BLOCKED:
            done = dm.done_ids(store.list_tasks(proj.id))
            console.print(f"Cannot start {task.id}.\n")
            console.print("Status: blocked\n")
            console.print("Blocked by:")
            for dep in task.dependencies:
                if dep not in done:
                    console.print(f"- {dep} - not done")
            console.print("\nRun these tasks first.")
            raise typer.Exit(code=1)

        if task.state is not TaskState.READY:
            console.print(
                f"[red]Cannot start {task.id}: it is '{task.state.value}', not 'ready'.[/red]"
            )
            raise typer.Exit(code=1)

        # 2. Conflict guard: are the files free?
        result = check_start(store, proj.id, task)
        if result.decision is ConflictDecision.BLOCK:
            console.print(f"Cannot start {task.id}.\n")
            console.print("File conflict detected:")
            for path, holder in result.conflicts:
                console.print(f"- {path} locked by {holder}")
            for reason in result.reasons:
                if not result.conflicts:
                    console.print(f"- {reason}")
            console.print("\nFinish or reject the blocking task first.")
            raise typer.Exit(code=1)
        if result.decision is ConflictDecision.WARN:
            console.print(f"[yellow]Warning:[/yellow] {' '.join(result.reasons)}\n")

        # 3. Both passed: lock files, move to doing.
        locked: list[str] = []
        try:
            for path in task.allowed_files:
                store.add_lock(FileLock(project_id=proj.id, task_id=task.id, file_path=path))
                locked.append(path)
        except FileLockConflict as exc:
            console.print(f"[red]Cannot start {task.id}: {exc}[/red]")
            raise typer.Exit(code=1)

        apply_transition(task, TaskState.DOING)
        store.update_task(task)

        model = _effective_model(store, proj.id, task)
        rel = prompt_relpath(model, task.id) if model else None
        prompt_exists = bool(rel) and (Path(proj.root_path) / rel).exists()

    console.print(f"{task.id} started.\n")
    console.print(f"Model: {_model_label(model)}")
    console.print("Status: doing\n")
    console.print("Files locked:")
    if locked:
        for path in locked:
            console.print(f"- {path}")
    else:
        console.print("- (none)")
    console.print("")
    if task.branch_name:
        console.print(f"Branch:\n{task.branch_name}\n")
    if prompt_exists:
        console.print(f"Prompt:\n{rel}")
    else:
        console.print("Prompt not found.\nRun:")
        console.print(f'agentdesk prompt "{project}" {task.id}')


def _terminal_command(project: str, task_id: str, target: TaskState) -> None:
    """Shared logic for done / review / reject."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)

        # Guide the flow (warn, do not block) when accepting a task.
        if target is TaskState.DONE:
            if store.get_handover(proj.id, task.id) is None:
                console.print(
                    f"[yellow]Warning:[/yellow]\nNo handover found for {task.id}.\nRun:\n"
                    f'agentdesk handover "{project}" {task.id}\n'
                )
            if store.get_gate_result(proj.id, task.id) is None:
                console.print(
                    f"[yellow]Warning:[/yellow]\nNo quality gate result found for {task.id}.\nRun:\n"
                    f'agentdesk gate "{project}" {task.id}\n'
                )

        try:
            apply_transition(task, target)
        except InvalidTransition as exc:
            console.print(f"[red]{exc}[/red]")
            raise typer.Exit(code=1)
        store.update_task(task)

        released = [lk.file_path for lk in store.locks_for_project(proj.id) if lk.task_id == task.id]

        if target is TaskState.REVIEW:
            # Keep locks; do not unblock dependents.
            console.print(f"{task.id} moved to review.\n")
            console.print("Locks kept active (task may still need fixes).")
            return

        # done / rejected both release locks.
        store.release_task_locks(proj.id, task.id)

        if target is TaskState.REJECTED:
            console.print(f"{task.id} rejected.\n")
            console.print("Released locks:")
            for path in released:
                console.print(f"- {path}")
            if not released:
                console.print("- (none)")
            dependents = [
                t for t in store.list_tasks(proj.id)
                if task.id in t.dependencies and t.state is TaskState.BLOCKED
            ]
            console.print("\nDependents remain blocked:")
            for t in dependents:
                console.print(f"- {t.id} - {t.name}")
            if not dependents:
                console.print("- (none)")
            return

        # target is DONE: recompute dependencies and report newly ready tasks.
        tasks = store.list_tasks(proj.id)
        before_ready = {t.id for t in tasks if t.state is TaskState.READY}
        changed = dm.recompute_states(tasks)
        for t in changed:
            store.update_task(t)
        newly_ready = [t for t in tasks if t.state is TaskState.READY and t.id not in before_ready]

        console.print(f"{task.id} marked as done.\n")
        console.print("Released locks:")
        for path in released:
            console.print(f"- {path}")
        if not released:
            console.print("- (none)")
        console.print("")
        if newly_ready:
            console.print("Newly ready tasks:")
            for t in newly_ready:
                console.print(f"- {t.id} - {t.name}")
        else:
            console.print("No newly ready tasks.")


@app.command("done")
def done_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
) -> None:
    """Mark a task done (from doing/review): release locks and recompute dependencies."""
    _terminal_command(project, task_id, TaskState.DONE)


@app.command("review")
def review_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
) -> None:
    """Move a task from doing to review (keeps locks; does not unblock dependents)."""
    _terminal_command(project, task_id, TaskState.REVIEW)


@app.command("reject")
def reject_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
) -> None:
    """Reject a task (from doing/review): release locks; does not unblock dependents."""
    _terminal_command(project, task_id, TaskState.REJECTED)


@app.command("handover")
def handover_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
    summary: Optional[str] = typer.Option(
        None, "--summary", "-s", help="Optional manual summary to record in the handover."
    ),
) -> None:
    """Generate and persist a handover document for a task."""
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

        model = _effective_model(store, proj.id, task)
        _, path = generate_handover(store, proj, task, model, summary=summary)
        rel = f"handovers/{task.id}.md"

    console.print("Handover generated:")
    console.print(rel)
    console.print(f"[dim]({path})[/dim]")


@app.command("gate")
def gate_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
) -> None:
    """Run the advanced quality gate for a task and persist the detailed result."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)

        result = run_gate(store, proj, task)
        store.save_gate_result(proj.id, result)

    console.print(f"Quality Gate: {result.outcome.value}\n")

    console.print("Checks:")
    for c in result.checks:
        console.print(f"[{c.level.value}] {c.message}")

    console.print("\nFailures:")
    for f in result.failures:
        console.print(f"- {f}")
    if not result.failures:
        console.print("- none")

    console.print("\nWarnings:")
    for w in result.warnings:
        console.print(f"- {w}")
    if not result.warnings:
        console.print("- none")

    console.print("\nHuman review reasons:")
    for r in result.reasons:
        console.print(f"- {r}")
    if not result.reasons:
        console.print("- none")

    console.print(f"\nRecommended action:\n{result.recommended_action}")


_VALIDATION_TAGS = {
    "PASS": "[green]PASS[/green]",
    "WARN": "[yellow]WARN[/yellow]",
    "FAIL": "[red]FAIL[/red]",
    "SKIP": "[dim]SKIP[/dim]",
}
_OUTCOME_STYLE = {
    "PASS": "green",
    "PASS_WITH_WARNINGS": "yellow",
    "FAIL": "red",
}


def _print_validation_report(report) -> None:
    console.print(f"Project validation: [bold]{report.path}[/bold]\n")
    console.print("Checks:")
    for c in report.checks:
        tag = _VALIDATION_TAGS.get(c.level, c.level)
        console.print(f"[{tag}] {c.name}: {c.message}")
    style = _OUTCOME_STYLE.get(report.outcome.value, "white")
    console.print(f"\nResult: [{style}]{report.outcome.value}[/{style}]")


@app.command("validate-project")
def validate_project_command(
    path: Path = typer.Argument(..., help="Path to the local project folder to validate."),
    test_command: Optional[str] = typer.Option(
        None, "--test-command", help='Optional test command to run in the project (e.g. "pytest").'
    ),
    json_output: bool = typer.Option(False, "--json", help="Emit the report as JSON instead of text."),
) -> None:
    """Run a deterministic validation of a local project folder.

    Reports Git state, README presence, an optional test command, and (for registered projects)
    file-lock conflicts and handover presence, then a PASS / PASS_WITH_WARNINGS / FAIL summary.
    Exits non-zero only on FAIL.
    """
    root = path.expanduser()
    if not root.exists():
        console.print(f"[red]Path does not exist: {root}[/red]")
        raise typer.Exit(code=1)
    if not root.is_dir():
        console.print(f"[red]Not a directory: {root}[/red]")
        raise typer.Exit(code=1)

    with _storage() as store:
        report = validate_project(root, test_command=test_command, store=store)

    if json_output:
        # Plain JSON (no Rich markup) so the output is reliably machine-parseable.
        typer.echo(json.dumps(report.to_dict(), indent=2))
    else:
        _print_validation_report(report)

    if report.failed:
        raise typer.Exit(code=1)


@app.command("test-result")
def test_result_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
    command: Optional[str] = typer.Option(None, "--command", help="The test command that was run."),
    result: str = typer.Option(..., "--result", help="passed | failed | not-run | unknown."),
    notes: Optional[str] = typer.Option(None, "--notes", help="Optional notes."),
) -> None:
    """Record a test result for a task (Agent Desk never runs tests itself)."""
    try:
        outcome = TestOutcome(result.strip().lower())
    except ValueError:
        valid = ", ".join(o.value for o in TestOutcome)
        console.print(f"[red]Invalid result '{result}'. Valid: {valid}.[/red]")
        raise typer.Exit(code=1)

    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)
        store.save_test_result(
            proj.id,
            TestResult(task_id=task.id, project_id=proj.id, command=command,
                       result=outcome, notes=notes or ""),
        )

    console.print(f"Test result recorded for {task_id}: {outcome.value}")
    if command:
        console.print(f"Command: {command}")
    if notes:
        console.print(f"Notes: {notes}")


@app.command("git-status")
def git_status_command(project: str = typer.Argument(..., help="Project id or name.")) -> None:
    """Show the project's local Git status (never crashes on non-Git projects)."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)

    console.print(f"Git status for project: {proj.name}\n")
    if not git.is_git_repo(proj.root_path):
        console.print("No Git repository detected for this project.")
        return

    try:
        branch = git.current_branch(proj.root_path)
        clean = git.is_clean(proj.root_path)
        changed = git.changed_files(proj.root_path)
    except git.GitError as exc:
        console.print(f"[red]Git error: {exc}[/red]")
        raise typer.Exit(code=1)

    console.print("Repository: detected")
    console.print(f"Current branch: {branch or '(detached)'}")
    console.print(f"Clean: {'yes' if clean else 'no'}\n")
    console.print("Changed files:")
    if changed:
        for f in changed:
            console.print(f"- {f}")
    else:
        console.print("- none")


@app.command("branch")
def branch_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
) -> None:
    """Create (or reuse) and check out a Git branch for a task: agent/TASK-XXX-<slug>."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)
        if not git.is_git_repo(proj.root_path):
            console.print("No Git repository detected for this project.")
            raise typer.Exit(code=1)

        try:
            if not git.is_clean(proj.root_path):
                console.print(
                    "[yellow]Warning:[/yellow] working tree has uncommitted changes; "
                    "they will carry over to the new branch.\n"
                )
            name = f"agent/{task.id}-{slugify(task.name)}"
            created = git.create_branch(proj.root_path, name)
        except git.GitError as exc:
            console.print(f"[red]Git error: {exc}[/red]")
            raise typer.Exit(code=1)

        task.branch_name = name
        store.update_task(task)

    if created:
        console.print(f"Branch created and checked out:\n{name}\n")
    else:
        console.print(f"Branch already existed; checked out:\n{name}\n")
    console.print(f"Task updated:\n{task.id} -> branch_name: {name}")


@app.command("diff")
def diff_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
) -> None:
    """Summarize changed files for a task and check them against allowed/forbidden lists."""
    with _storage() as store:
        proj = _resolve_project(store, project)
        if proj is None:
            console.print(f"[red]No project matching '[bold]{project}[/bold]'.[/red]")
            raise typer.Exit(code=1)
        task = store.get_task(proj.id, task_id)
        if task is None:
            console.print(f"[red]No task '[bold]{task_id}[/bold]' in project '{proj.id}'.[/red]")
            raise typer.Exit(code=1)
        if not git.is_git_repo(proj.root_path):
            console.print("No Git repository detected for this project.")
            raise typer.Exit(code=1)

        try:
            changed = git.filter_task_changes(git.changed_files(proj.root_path))
            out_of_scope, forbidden_v = git.analyze_scope(
                changed, task.allowed_files, task.forbidden_files
            )
            # Persist the observed changes onto the task (Git-ready fields become functional).
            task.changed_files = changed
            task.diff_summary = git.diff_stat(proj.root_path)
        except git.GitError as exc:
            console.print(f"[red]Git error: {exc}[/red]")
            raise typer.Exit(code=1)
        store.update_task(task)

    console.print(f"Diff summary for {task.id}\n")
    console.print(f"Branch: {task.branch_name or git.current_branch(proj.root_path) or '(unknown)'}\n")
    console.print("Changed files:")
    for f in changed or []:
        console.print(f"- {f}")
    if not changed:
        console.print("- none")
    console.print("\nAllowed files:")
    for f in task.allowed_files or []:
        console.print(f"- {f}")
    if not task.allowed_files:
        console.print("- (none defined)")

    console.print("\nForbidden violations:")
    if forbidden_v:
        for f in forbidden_v:
            console.print(f"- {f} is listed as forbidden but was changed.")
    else:
        console.print("- none")

    if out_of_scope:
        console.print("\nScope warnings:")
        for f in out_of_scope:
            console.print(f"- {f} is changed but not listed in allowed_files.")


@app.command("local-status")
def local_status_command() -> None:
    """Show the local-model configuration (never crashes if unconfigured)."""
    cfg = LocalModelConfig.from_env()
    console.print("Local model configuration\n")
    if not cfg.is_configured():
        console.print("Local model is not configured.\n")
        console.print("Set:")
        console.print("AGENTDESK_LOCAL_PROVIDER")
        console.print("AGENTDESK_LOCAL_BASE_URL")
        console.print("AGENTDESK_LOCAL_MODEL")
        return
    console.print(f"Provider: {cfg.provider}")
    if cfg.provider != "fake":
        console.print(f"Base URL: {cfg.base_url}")
        console.print(f"Model: {cfg.model}")
    console.print(f"Timeout: {cfg.timeout}s")
    console.print("Status: configured")


@app.command("local-assist")
def local_assist_command(
    project: str = typer.Argument(..., help="Project id or name."),
    task_id: str = typer.Argument(..., help="Task id."),
    mode: str = typer.Option(..., "--mode", help=f"One of: {', '.join(LOCAL_MODES)}."),
) -> None:
    """Advisory local-model assistance for a task. Writes a report; never changes state or code."""
    if mode not in LOCAL_MODES:
        console.print(f"[red]Invalid mode '{mode}'. Valid modes: {', '.join(LOCAL_MODES)}.[/red]")
        raise typer.Exit(code=1)

    cfg = LocalModelConfig.from_env()
    if not cfg.is_configured():
        console.print("[red]Local model is not configured.[/red] Set: " + ", ".join(cfg.missing()))
        raise typer.Exit(code=1)

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

        # Advisory-only safety notices (do not block).
        if task.risk is RiskLevel.HIGH:
            console.print(
                "[yellow]Warning:[/yellow]\nThis is a high-risk task. Local model output should be "
                "treated as advisory only.\n"
            )
        if task.task_type.value == "implementation":
            console.print(
                "Local model will only generate advisory output. It will not modify "
                "implementation files.\n"
            )

        try:
            provider = get_provider(cfg)
            path = run_assist(store, proj, task, mode, provider)
        except LocalModelError as exc:
            console.print(f"[red]Local model error: {exc}[/red]")
            raise typer.Exit(code=1)

    console.print("Local assist report generated:")
    console.print(f"reports/{task.id}-{mode}.md")
    console.print(f"[dim]({path})[/dim]")


if __name__ == "__main__":
    app()
