"""Tests for Phase 4 Git integration. Uses temporary Git repos, never the real Agent Desk repo."""

import subprocess

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.config import db_path
from agentdesk.models import Project, RiskLevel, Task, TaskState, TaskType
from agentdesk.storage import Storage

runner = CliRunner()


def _git(root, *args):
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, check=True)


def _init_repo(root):
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "checkout", "-b", "main")
    (root / "README.md").write_text("init\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


@pytest.fixture()
def git_project(tmp_path, monkeypatch):
    """A project whose root is a Git repo, with one ready task that allows src/**."""
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    root = tmp_path / "proj"
    _init_repo(root)
    slug = "git-proj"
    with Storage(db_path()) as store:
        store.add_project(Project(id=slug, name="Git Proj", idea="x", root_path=str(root)))
        store.add_task(Task(
            id="TASK-001", project_id=slug, name="Create review parser",
            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.MEDIUM, state=TaskState.READY,
            allowed_files=["src/**"], forbidden_files=["docs/architecture.md"],
            acceptance_criteria=["parser works"],
        ))
    return slug, root


# 1: non-Git project does not crash
def test_git_status_no_repo(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    work = tmp_path / "work"
    work.mkdir()
    runner.invoke(app, ["new", "No Git", "--path", str(work)])
    r = runner.invoke(app, ["git-status", "no-git"])
    assert r.exit_code == 0
    assert "No Git repository detected" in r.output


# 2 + 3: git-status detects repo and branch
def test_git_status_detects_repo_and_branch(git_project):
    slug, _ = git_project
    r = runner.invoke(app, ["git-status", slug])
    assert r.exit_code == 0, r.output
    assert "Repository: detected" in r.output
    assert "Current branch: main" in r.output


# 4 + 5: branch creates agent/TASK-XXX-slug and stores branch_name
def test_branch_creates_and_persists(git_project):
    slug, root = git_project
    r = runner.invoke(app, ["branch", slug, "TASK-001"])
    assert r.exit_code == 0, r.output
    expected = "agent/TASK-001-create-review-parser"
    assert expected in r.output
    assert subprocess.run(["git", "branch", "--show-current"], cwd=str(root),
                          capture_output=True, text=True).stdout.strip() == expected
    with Storage(db_path()) as store:
        assert store.get_task(slug, "TASK-001").branch_name == expected


# 6: branch is not duplicated when it already exists
def test_branch_reuse(git_project):
    slug, _ = git_project
    runner.invoke(app, ["branch", slug, "TASK-001"])
    r = runner.invoke(app, ["branch", slug, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert "already existed" in r.output


# 7 + 8: diff lists changed files within allowed scope
def test_diff_lists_changed_in_scope(git_project):
    slug, root = git_project
    (root / "src").mkdir()
    (root / "src" / "parser.py").write_text("x = 1\n", encoding="utf-8")
    r = runner.invoke(app, ["diff", slug, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert "src/parser.py" in r.output
    assert "Scope warnings:" not in r.output           # within src/**
    assert "Forbidden violations:\n- none" in r.output


# 9: diff warns about files outside allowed_files
def test_diff_out_of_scope_warning(git_project):
    slug, root = git_project
    (root / "config.py").write_text("y = 2\n", encoding="utf-8")  # not under src/**
    r = runner.invoke(app, ["diff", slug, "TASK-001"])
    assert "Scope warnings:" in r.output
    assert "config.py is changed but not listed in allowed_files." in r.output


# 10 + 13: forbidden file change -> diff flags it and gate FAILs
def test_forbidden_change_flagged_and_gate_fails(git_project):
    slug, root = git_project
    (root / "docs").mkdir()
    (root / "docs" / "architecture.md").write_text("changed\n", encoding="utf-8")
    runner.invoke(app, ["branch", slug, "TASK-001"])
    runner.invoke(app, ["start", slug, "TASK-001"])
    runner.invoke(app, ["handover", slug, "TASK-001", "--summary", "did work"])

    d = runner.invoke(app, ["diff", slug, "TASK-001"])
    assert "docs/architecture.md is listed as forbidden but was changed." in d.output

    g = runner.invoke(app, ["gate", slug, "TASK-001"])
    assert "Quality Gate: FAIL" in g.output
    assert "Forbidden file changed: docs/architecture.md." in g.output


# 11: gate uses Git info (true PASS achievable inside a clean Git repo)
def test_gate_pass_in_clean_git_repo(git_project):
    slug, root = git_project
    # low-risk task, branch associated, prompt on disk, manual summary, no changes -> PASS
    with Storage(db_path()) as store:
        store.add_task(Task(
            id="TASK-002", project_id=slug, name="Write docs", task_type=TaskType.DOCUMENTATION,
            risk=RiskLevel.LOW, state=TaskState.READY, allowed_files=["docs/guide.md"],
            acceptance_criteria=["documented"],
            objective="Write the developer guide covering install and usage.",
        ))
    runner.invoke(app, ["branch", slug, "TASK-002"])
    runner.invoke(app, ["prompt", slug, "TASK-002"])
    runner.invoke(app, ["start", slug, "TASK-002"])
    runner.invoke(app, ["handover", slug, "TASK-002", "--summary", "wrote guide"])
    r = runner.invoke(app, ["gate", slug, "TASK-002"])
    assert "Quality Gate: PASS" in r.output
    assert "PASS_WITH_WARNINGS" not in r.output
    assert "[PASS] Git repository detected" in r.output
    assert "[PASS] No forbidden files changed" in r.output


# 12: gate warns (does not fail) when there is no Git repo
def test_gate_warns_without_git(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    work = tmp_path / "work"
    work.mkdir()
    runner.invoke(app, ["new", "Plain", "--path", str(work)])
    runner.invoke(app, ["plan", "plain"])
    # Use a low-risk task so the gate reaches the warnings section (not NEEDS_HUMAN_REVIEW).
    with Storage(db_path()) as store:
        store.add_task(Task(id="TASK-500", project_id="plain", name="Docs",
                            task_type=TaskType.DOCUMENTATION, risk=RiskLevel.LOW,
                            state=TaskState.READY, allowed_files=["docs/g.md"],
                            acceptance_criteria=["done"]))
    runner.invoke(app, ["start", "plain", "TASK-500"])
    runner.invoke(app, ["handover", "plain", "TASK-500", "--summary", "x"])
    r = runner.invoke(app, ["gate", "plain", "TASK-500"])
    assert r.exit_code == 0, r.output
    assert "Git repository not detected." in r.output
