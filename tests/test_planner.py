"""Tests for the Run B planning engine and the `agentdesk plan` command."""

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.models import Project, TaskState
from agentdesk.planner import build_tasks, plan_project
from agentdesk.storage import Storage

runner = CliRunner()


@pytest.fixture()
def project(tmp_path):
    root = tmp_path / "demo"
    root.mkdir()
    return Project(id="demo", name="Demo Project", idea="a tool that does X", root_path=str(root))


@pytest.fixture()
def store(tmp_path):
    s = Storage(tmp_path / "agentdesk.db")
    yield s
    s.close()


# ----------------------------------------------------------------- engine level
def test_build_tasks_is_deterministic_and_routed():
    p = Project(id="demo", name="Demo", idea="idea")
    a = build_tasks(p)
    b = build_tasks(p)
    assert [t.id for t in a] == [t.id for t in b]
    assert len(a) >= 10
    # routing applied: every task has a recommended model except internal-only quality gate
    for t in a:
        if t.task_type.value == "quality-gate" and t.risk.value == "low":
            continue
        assert t.recommended_model is not None


def test_states_reflect_dependencies():
    tasks = build_tasks(Project(id="demo", name="Demo", idea="idea"))
    no_deps = [t for t in tasks if not t.dependencies]
    with_deps = [t for t in tasks if t.dependencies]
    assert no_deps and with_deps
    assert all(t.state is TaskState.READY for t in no_deps)
    assert all(t.state is TaskState.BLOCKED for t in with_deps)


def test_plan_project_writes_docs_and_tasks_and_persists(project, store):
    store.add_project(project)
    tasks = plan_project(store, project)

    # docs created
    docs = project_root_docs(project)
    for name in ["vision", "scope", "architecture", "risks", "success-criteria"]:
        f = docs / f"{name}.md"
        assert f.exists() and f.read_text(encoding="utf-8").strip()

    # task files created
    task_dir = (docs.parent / "tasks")
    assert len(list(task_dir.glob("TASK-*.md"))) >= 10

    # persisted to SQLite
    assert store.count_tasks("demo") == len(tasks) >= 10


def test_plan_is_repeatable_without_corruption(project, store):
    store.add_project(project)
    first = plan_project(store, project)
    # second call without force is a no-op: returns existing, count unchanged
    second = plan_project(store, project)
    assert store.count_tasks("demo") == len(first) == len(second)
    assert [t.id for t in first] == [t.id for t in second]


def test_force_regenerates_without_duplicating(project, store):
    store.add_project(project)
    plan_project(store, project)
    n = store.count_tasks("demo")
    plan_project(store, project, force=True)
    assert store.count_tasks("demo") == n  # regenerated, not duplicated


def project_root_docs(project):
    from pathlib import Path

    return Path(project.root_path) / "docs"


# -------------------------------------------------------------------- CLI level
def test_cli_new_then_plan(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    work = tmp_path / "work"
    work.mkdir()

    r_new = runner.invoke(app, ["new", "Review Assistant", "--path", str(work)])
    assert r_new.exit_code == 0, r_new.output

    r_plan = runner.invoke(app, ["plan", "review-assistant"])
    assert r_plan.exit_code == 0, r_plan.output
    assert "Planned" in r_plan.output
    assert "ready" in r_plan.output and "blocked" in r_plan.output

    # repeatable: second plan without --force is a clean no-op (exit 0, no crash)
    r_plan2 = runner.invoke(app, ["plan", "review-assistant"])
    assert r_plan2.exit_code == 0, r_plan2.output
    assert "already has" in r_plan2.output


def test_cli_plan_unknown_project_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    r = runner.invoke(app, ["plan", "does-not-exist"])
    assert r.exit_code == 1
    assert "No project" in r.output
