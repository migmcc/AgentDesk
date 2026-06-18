"""Real-project validation layer (v0.4.1).

Points the existing Agent Desk engine at small but realistic local projects (checked-in fixtures
under tests/fixtures/real_projects/) and asserts the outcomes are correct and deterministic.

This adds no new features: it only *reuses* planner, router, conflict_guard, git_integration,
handover and quality_gate. See docs/validation/real-project-validation-v0.4.1.md.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from agentdesk.conflict_guard import ConflictDecision, check_start
from agentdesk.config import db_path
from agentdesk.git_integration import is_clean, is_git_repo, repo_analysis
from agentdesk.handover import generate_handover
from agentdesk.models import (
    FileLock,
    GateOutcome,
    Model,
    Project,
    RiskLevel,
    Task,
    TaskState,
    TaskType,
)
# Aliased so pytest does not try to collect these as test classes (names start with "Test").
from agentdesk.models import TestOutcome as Outcome
from agentdesk.models import TestResult as RecordedTest
from agentdesk.prompt_generator import generate_prompt
from agentdesk.quality_gate import run_gate
from agentdesk.router import route
from agentdesk.storage import Storage

FIXTURES = Path(__file__).parent / "fixtures" / "real_projects"


# --------------------------------------------------------------------------- helpers
def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, check=True)


def _copy_fixture(name: str, dest: Path) -> Path:
    shutil.copytree(FIXTURES / name, dest)
    return dest


def _init_repo(root: Path) -> None:
    """Initialise a committed Git repo on `main` from whatever is already in `root`."""
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "validator@example.com")
    _git(root, "config", "user.name", "Validator")
    _git(root, "checkout", "-q", "-b", "main")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "import fixture")


def _run_fixture_tests(root: Path) -> subprocess.CompletedProcess:
    """Run a fixture's own test suite in an isolated subprocess (pinned interpreter)."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(root / "tests")],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@pytest.fixture()
def home(tmp_path, monkeypatch):
    """Isolate Agent Desk state under a temp AGENTDESK_HOME so the DB is fresh per test."""
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    return tmp_path


def _add_project(store: Storage, slug: str, root: Path) -> Project:
    project = Project(id=slug, name=slug.replace("-", " ").title(), idea="fixture", root_path=str(root))
    store.add_project(project)
    return project


def _messages(result) -> str:
    return "\n".join(f"[{c.level.value}] {c.message}" for c in result.checks)


# ------------------------------------------------------- 1. clean Python CLI project
def test_clean_cli_project_passes_gate(home):
    root = _copy_fixture("clean_cli", home / "proj")
    _init_repo(root)
    # An agent "did the work": associated branch + an in-scope, uncommitted change.
    _git(root, "checkout", "-q", "-b", "agent/todo-extra")
    (root / "src" / "todo_cli" / "extra.py").write_text("VALUE = 1\n", encoding="utf-8")

    with Storage(db_path()) as store:
        project = _add_project(store, "clean-cli", root)
        task = Task(
            id="TASK-001", project_id="clean-cli", name="Add extra helper",
            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.LOW, state=TaskState.DOING,
            allowed_files=["src/**"], acceptance_criteria=["extra helper exposed"],
            objective="Add a small in-scope helper module to the todo CLI package.",
            branch_name="agent/todo-extra",
        )
        store.add_task(task)

        # router reused directly: an objective implementation routes to Codex.
        decision = route(task)
        assert decision.effective_model is Model.CODEX
        store.save_routing("clean-cli", decision)

        generate_prompt(task, Model.CODEX, root, project=project)
        store.save_test_result("clean-cli", RecordedTest(
            task_id="TASK-001", command="pytest", result=Outcome.PASSED))
        generate_handover(store, project, task, Model.CODEX, summary="Added the extra helper module.")

        result = run_gate(store, project, task)

    msgs = _messages(result)
    assert result.outcome is GateOutcome.PASS, msgs
    assert result.failures == []
    assert result.reasons == []
    assert "[PASS] Git repository detected" in msgs
    assert "[PASS] Prompt generated for codex" in msgs
    assert "[PASS] Tests passed (pytest)" in msgs
    assert "[PASS] Handover found" in msgs


def test_clean_cli_fixture_tests_actually_pass(home):
    """The clean fixture is a real, runnable project whose tests genuinely pass."""
    root = _copy_fixture("clean_cli", home / "proj")
    proc = _run_fixture_tests(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ----------------------------------------------------------- 2. project with broken tests
def test_broken_tests_fixture_really_fails(home):
    """Prove the fixture is genuinely broken before feeding the result into the engine."""
    root = _copy_fixture("broken_tests", home / "proj")
    proc = _run_fixture_tests(root)
    assert proc.returncode != 0
    assert "test_subtract" in (proc.stdout + proc.stderr)


def test_broken_tests_make_gate_fail(home):
    root = _copy_fixture("broken_tests", home / "proj")
    _init_repo(root)
    proc = _run_fixture_tests(root)
    assert proc.returncode != 0  # real failure observed

    with Storage(db_path()) as store:
        project = _add_project(store, "broken", root)
        task = Task(
            id="TASK-001", project_id="broken", name="Fix subtract bug",
            task_type=TaskType.BUGFIX, risk=RiskLevel.MEDIUM, state=TaskState.DOING,
            allowed_files=["src/**"], acceptance_criteria=["subtract returns a - b"],
            objective="Fix the subtraction routine so its unit test passes.",
        )
        store.add_task(task)
        # The failing run is recorded through Agent Desk's manual TestResult mechanism.
        store.save_test_result("broken", RecordedTest(
            task_id="TASK-001", command="pytest", result=Outcome.FAILED,
            notes="test_subtract failed"))
        generate_handover(store, project, task, Model.CODEX, summary="Investigated subtract bug.")
        result = run_gate(store, project, task)

    assert result.outcome is GateOutcome.FAIL, _messages(result)
    assert any("Tests failed" in f for f in result.failures)


# --------------------------------------------------------- 3. project with missing README
def test_missing_readme_detected_and_tracked(home):
    root = _copy_fixture("missing_readme", home / "proj")
    _init_repo(root)
    assert not (root / "README.md").exists()  # fixture ships without a README

    with Storage(db_path()) as store:
        _add_project(store, "no-readme", root)
        task = Task(
            id="TASK-DOC", project_id="no-readme", name="Write the project README",
            task_type=TaskType.DOCUMENTATION, risk=RiskLevel.LOW, state=TaskState.DOING,
            allowed_files=["README.md"], acceptance_criteria=["README documents usage"],
            objective="Document installation and usage for the wordcount library in a README.",
        )
        store.add_task(task)

        # router reused: documentation is low-risk and routes to the local model.
        assert route(task).effective_model is Model.LOCAL

        # Before the work: clean tree, README absent.
        before = repo_analysis(root, task)
        assert before.is_repo and before.changed == []

        # The agent "writes" the README; git_integration must pick it up, in scope.
        (root / "README.md").write_text("# wordcount\n\nUsage docs.\n", encoding="utf-8")
        after = repo_analysis(root, task)

    assert "README.md" in after.changed
    assert after.out_of_scope == []
    assert after.forbidden == []


# ------------------------------------------------- 4. dirty git state / simulated conflict
def test_dirty_git_with_forbidden_change_fails(home):
    root = _copy_fixture("clean_cli", home / "proj")
    _init_repo(root)
    _git(root, "checkout", "-q", "-b", "agent/edit")

    with Storage(db_path()) as store:
        project = _add_project(store, "dirty", root)
        task = Task(
            id="TASK-001", project_id="dirty", name="Edit core",
            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.MEDIUM, state=TaskState.DOING,
            allowed_files=["src/**"], forbidden_files=["pyproject.toml"],
            acceptance_criteria=["core updated"], branch_name="agent/edit",
            objective="Adjust the todo core while leaving packaging metadata untouched.",
        )
        store.add_task(task)
        # Dirty the tree: one forbidden change and one out-of-scope file.
        (root / "pyproject.toml").write_text("# tampered\n", encoding="utf-8")
        (root / "notes.txt").write_text("scratch\n", encoding="utf-8")

        assert is_git_repo(root)
        assert not is_clean(root)  # dirty working tree

        analysis = repo_analysis(root, task)
        assert "pyproject.toml" in analysis.forbidden
        assert "notes.txt" in analysis.out_of_scope

        generate_handover(store, project, task, Model.CODEX, summary="Edited core.")
        result = run_gate(store, project, task)

    assert result.outcome is GateOutcome.FAIL, _messages(result)
    assert any("Forbidden file changed: pyproject.toml" in f for f in result.failures)


def test_simulated_file_conflict_blocks_and_fails_gate(home):
    root = _copy_fixture("clean_cli", home / "proj")
    _init_repo(root)
    shared = "src/todo_cli/core.py"

    with Storage(db_path()) as store:
        project = _add_project(store, "conflict", root)
        first = Task(id="T1", project_id="conflict", name="First on core", state=TaskState.DOING,
                     allowed_files=[shared], acceptance_criteria=["a"],
                     objective="First task editing the shared core module.")
        second = Task(id="T2", project_id="conflict", name="Second on core", state=TaskState.DOING,
                      allowed_files=[shared], acceptance_criteria=["b"],
                      objective="Second task editing the same shared core module.")
        store.add_task(first)
        store.add_task(second)
        # T1 holds the lock on the shared file (as `start` would create it).
        store.add_lock(FileLock(project_id="conflict", task_id="T1", file_path=shared))

        # conflict_guard reused directly: T2 must be blocked.
        decision = check_start(store, "conflict", second)
        assert decision.decision is ConflictDecision.BLOCK
        assert not decision.allowed
        assert (shared, "T1") in decision.conflicts

        generate_handover(store, project, second, Model.CODEX, summary="Tried to edit core.")
        result = run_gate(store, project, second)

    assert result.outcome is GateOutcome.FAIL, _messages(result)
    assert any(f"File conflict: {shared} locked by T1" in f for f in result.failures)


# --------------------------------------------------- 5. project requiring handover output
def test_handover_output_written_and_found_by_gate(home):
    root = _copy_fixture("clean_cli", home / "proj")
    _init_repo(root)

    with Storage(db_path()) as store:
        project = _add_project(store, "handover", root)
        done_task = Task(
            id="TASK-001", project_id="handover", name="Implement core",
            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.LOW, state=TaskState.REVIEW,
            allowed_files=["src/**"], acceptance_criteria=["core works"],
            objective="Implement the todo core so dependent work can begin.",
        )
        follow_up = Task(
            id="TASK-002", project_id="handover", name="Add CLI entrypoint",
            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.LOW, state=TaskState.BLOCKED,
            allowed_files=["src/**"], dependencies=["TASK-001"],
            acceptance_criteria=["cli runs"], objective="Wire a CLI entrypoint over the core.",
        )
        store.add_task(done_task)
        store.add_task(follow_up)

        handover, path = generate_handover(
            store, project, done_task, Model.CODEX, summary="Implemented the todo core.")

    # The continuity document is really written to disk with the task's data.
    assert path.exists()
    assert path == root / "handovers" / "TASK-001.md"
    content = path.read_text(encoding="utf-8")
    assert "Implement core" in content
    assert "Implemented the todo core." in content
    # next_recommended_task points at the dependent follow-up task.
    assert handover.next_recommended_task is not None
    assert "TASK-002" in handover.next_recommended_task

    # And the gate's handover check finds it (persisted via the store).
    with Storage(db_path()) as store:
        project = store.get_project("handover")
        task = store.get_task("handover", "TASK-001")
        result = run_gate(store, project, task)
    assert "[PASS] Handover found" in _messages(result)
