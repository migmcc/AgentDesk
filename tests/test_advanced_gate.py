"""Tests for Phase 6 advanced quality gate: structured checks + test-result command."""

import subprocess

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.config import db_path
from agentdesk.models import RiskLevel, Task, TaskState, TaskType
from agentdesk.storage import Storage

runner = CliRunner()
SLUG = "review-assistant"


@pytest.fixture()
def planned(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    work = tmp_path / "work"
    work.mkdir()
    assert runner.invoke(app, ["new", "Review Assistant", "--path", str(work)]).exit_code == 0
    assert runner.invoke(app, ["plan", SLUG]).exit_code == 0
    return SLUG, work / SLUG


def _gate(task_id):
    return runner.invoke(app, ["gate", SLUG, task_id])


def _start_with_handover(task_id, summary="did the work"):
    runner.invoke(app, ["start", SLUG, task_id])
    runner.invoke(app, ["handover", SLUG, task_id, "--summary", summary])


# 16: output includes the structured sections
def test_gate_output_is_structured(planned):
    _start_with_handover("TASK-001")
    r = _gate("TASK-001")
    assert r.exit_code == 0, r.output
    for header in ("Checks:", "Failures:", "Warnings:", "Human review reasons:", "Recommended action:"):
        assert header in r.output
    assert "[" in r.output and "]" in r.output  # per-check level tags


# 1: still works for projects without Git
def test_gate_without_git_no_crash(planned):
    _start_with_handover("TASK-001")
    r = _gate("TASK-001")
    assert r.exit_code == 0
    assert "Git repository not detected." in r.output


# 4 + 5: missing handover / missing acceptance criteria -> FAIL
def test_fail_without_handover(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    r = _gate("TASK-001")
    assert "Quality Gate: FAIL" in r.output
    assert "Handover not found." in r.output


def test_fail_without_criteria(planned):
    with Storage(db_path()) as store:
        store.add_task(Task(id="TASK-100", project_id=SLUG, name="No criteria",
                            task_type=TaskType.DOCUMENTATION, risk=RiskLevel.LOW,
                            state=TaskState.READY, allowed_files=["docs/x.md"],
                            objective="A reasonably long objective here."))
    _start_with_handover("TASK-100")
    r = _gate("TASK-100")
    assert "Quality Gate: FAIL" in r.output
    assert "No acceptance criteria defined." in r.output


# 6 + 7: high risk / architecture -> NEEDS_HUMAN_REVIEW
def test_high_risk_architecture_needs_review(planned):
    _start_with_handover("TASK-001")  # architecture / high risk
    r = _gate("TASK-001")
    assert "Quality Gate: NEEDS_HUMAN_REVIEW" in r.output
    assert "[REVIEW] Task is high risk." in r.output
    assert "Task type is architecture." in r.output


# 8 + 9: prompt missing -> warning; prompt present -> positive check
def test_prompt_checks(planned):
    _start_with_handover("TASK-001")
    r_missing = _gate("TASK-001")
    assert "Prompt not generated on disk." in r_missing.output
    runner.invoke(app, ["prompt", SLUG, "TASK-001"])  # architecture -> claude-code
    r_present = _gate("TASK-001")
    assert "[PASS] Prompt generated for claude-code" in r_present.output


# 10 + 11 + 12: test-result drives the gate
def test_test_result_passed_recorded(planned):
    _start_with_handover("TASK-001")
    r = runner.invoke(app, ["test-result", SLUG, "TASK-001", "--command", "pytest", "--result", "passed"])
    assert r.exit_code == 0, r.output
    assert "passed" in r.output
    with Storage(db_path()) as store:
        assert store.get_test_result(SLUG, "TASK-001").result.value == "passed"
    g = _gate("TASK-001")
    assert "[PASS] Tests passed (pytest)" in g.output


def test_test_result_failed_makes_gate_fail(planned):
    _start_with_handover("TASK-001")
    runner.invoke(app, ["test-result", SLUG, "TASK-001", "--command", "pytest",
                        "--result", "failed", "--notes", "1 failing test"])
    g = _gate("TASK-001")
    assert "Quality Gate: FAIL" in g.output
    assert "Tests failed: 1 failing test." in g.output


def test_no_test_result_warns(planned):
    # implementation task -> tests expected -> warning when none recorded
    with Storage(db_path()) as store:
        store.add_task(Task(id="TASK-200", project_id=SLUG, name="Impl",
                            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.MEDIUM,
                            state=TaskState.READY, allowed_files=["src/a.py"],
                            acceptance_criteria=["works"], objective="Implement the core feature."))
    _start_with_handover("TASK-200")
    g = _gate("TASK-200")
    assert "Tests not recorded." in g.output


def test_invalid_test_result_errors(planned):
    r = runner.invoke(app, ["test-result", SLUG, "TASK-001", "--result", "bogus"])
    assert r.exit_code == 1
    assert "Invalid result" in r.output


# 13: blocked dependency -> FAIL
def test_blocked_dependency_fails(planned):
    runner.invoke(app, ["handover", SLUG, "TASK-002"])  # blocked by TASK-001
    g = _gate("TASK-002")
    assert "Quality Gate: FAIL" in g.output
    assert "blocked by TASK-001" in g.output


# 14: lock conflict -> FAIL
def test_lock_conflict_fails(planned):
    # Two ready tasks sharing a file; start one (locks it), gate the other.
    with Storage(db_path()) as store:
        store.add_task(Task(id="T1", project_id=SLUG, name="One", state=TaskState.READY,
                            allowed_files=["src/shared.py"], acceptance_criteria=["a"],
                            objective="First task touching the shared file."))
        store.add_task(Task(id="T2", project_id=SLUG, name="Two", state=TaskState.DOING,
                            allowed_files=["src/shared.py"], acceptance_criteria=["a"],
                            objective="Second task touching the shared file."))
    runner.invoke(app, ["start", SLUG, "T1"])             # T1 locks src/shared.py
    runner.invoke(app, ["handover", SLUG, "T2", "--summary", "x"])
    g = _gate("T2")
    assert "Quality Gate: FAIL" in g.output
    assert "File conflict: src/shared.py locked by T1." in g.output


# 2 + 3 + 15: forbidden file -> FAIL; out-of-scope -> warning; result persisted (Git repo)
def test_git_forbidden_and_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    root = tmp_path / "proj"
    root.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "T"], cwd=root, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "main"], cwd=root, check=True)
    (root / "README.md").write_text("init\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)

    from agentdesk.models import Project
    with Storage(db_path()) as store:
        store.add_project(Project(id="gp", name="GP", idea="x", root_path=str(root)))
        store.add_task(Task(id="TASK-001", project_id="gp", name="Impl",
                            task_type=TaskType.IMPLEMENTATION, risk=RiskLevel.MEDIUM,
                            state=TaskState.DOING, allowed_files=["src/**"],
                            forbidden_files=["docs/architecture.md"],
                            acceptance_criteria=["works"], objective="Implement the parser module."))
    (root / "docs").mkdir()
    (root / "docs" / "architecture.md").write_text("x\n", encoding="utf-8")  # forbidden
    (root / "config.py").write_text("y\n", encoding="utf-8")                  # out of scope
    runner.invoke(app, ["handover", "gp", "TASK-001", "--summary", "did work"])

    g = runner.invoke(app, ["gate", "gp", "TASK-001"])
    assert "Quality Gate: FAIL" in g.output
    assert "Forbidden file changed: docs/architecture.md." in g.output
    assert "Changed file outside allowed scope: config.py." in g.output
    with Storage(db_path()) as store:
        assert store.get_gate_result("gp", "TASK-001").outcome.value == "FAIL"
