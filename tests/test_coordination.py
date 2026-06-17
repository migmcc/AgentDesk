"""Tests for Run D: status / start / done / review / reject + conflict guard + state machine."""

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.config import db_path
from agentdesk.models import Task, TaskState
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


def _tasks():
    with Storage(db_path()) as store:
        return {t.id: t for t in store.list_tasks(SLUG)}


def _locks():
    with Storage(db_path()) as store:
        return store.locks_for_project(SLUG)


def _complete(task_id):
    assert runner.invoke(app, ["start", SLUG, task_id]).exit_code == 0
    assert runner.invoke(app, ["done", SLUG, task_id]).exit_code == 0


# 1: status shows counts
def test_status_shows_counts(planned):
    r = runner.invoke(app, ["status", SLUG])
    assert r.exit_code == 0, r.output
    assert "Tasks:" in r.output
    assert "ready: 1" in r.output      # only TASK-001 is ready at plan time
    assert "blocked: 11" in r.output
    assert "Next recommended tasks:" in r.output
    assert "TASK-001" in r.output


# 2 + 3 + 17: start moves ready->doing, creates persisted locks
def test_start_moves_to_doing_and_locks(planned):
    r = runner.invoke(app, ["start", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert "Status: doing" in r.output
    assert _tasks()["TASK-001"].state is TaskState.DOING
    locks = _locks()
    assert any(lk.file_path == "docs/architecture.md" and lk.task_id == "TASK-001" for lk in locks)


# 4: start fails when blocked
def test_start_blocked_task_fails(planned):
    r = runner.invoke(app, ["start", SLUG, "TASK-002"])  # depends on TASK-001
    assert r.exit_code == 1
    assert "blocked" in r.output.lower()
    assert "TASK-001" in r.output


# 5: start fails on a file already locked by another task
def test_start_file_conflict_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    work = tmp_path / "work"
    work.mkdir()
    assert runner.invoke(app, ["new", "Conflict Demo", "--path", str(work)]).exit_code == 0
    slug = "conflict-demo"
    with Storage(db_path()) as store:
        store.add_task(Task(id="T1", project_id=slug, name="One",
                            state=TaskState.READY, allowed_files=["src/shared.py"]))
        store.add_task(Task(id="T2", project_id=slug, name="Two",
                            state=TaskState.READY, allowed_files=["src/shared.py"]))

    assert runner.invoke(app, ["start", slug, "T1"]).exit_code == 0
    r = runner.invoke(app, ["start", slug, "T2"])
    assert r.exit_code == 1
    assert "conflict" in r.output.lower()
    assert "src/shared.py locked by T1" in r.output


# 6 + 7 + 8: review keeps locks and does not unblock dependents
def test_review_keeps_locks_and_does_not_unblock(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    r = runner.invoke(app, ["review", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert _tasks()["TASK-001"].state is TaskState.REVIEW
    assert any(lk.task_id == "TASK-001" for lk in _locks())   # locks kept
    assert _tasks()["TASK-002"].state is TaskState.BLOCKED     # dependent still blocked


# 9 + 10 + 11: done from doing releases locks and recomputes (unblocks dependents)
def test_done_releases_locks_and_unblocks(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    r = runner.invoke(app, ["done", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert _tasks()["TASK-001"].state is TaskState.DONE
    assert not any(lk.task_id == "TASK-001" for lk in _locks())  # released
    assert _tasks()["TASK-002"].state is TaskState.READY         # recomputed
    assert "Newly ready tasks" in r.output and "TASK-002" in r.output


def test_done_from_review(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    runner.invoke(app, ["review", SLUG, "TASK-001"])
    r = runner.invoke(app, ["done", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert _tasks()["TASK-001"].state is TaskState.DONE


# 12: dependent becomes ready only when ALL its dependencies are done
def test_dependent_ready_only_when_all_deps_done(planned):
    for tid in ("TASK-001", "TASK-002", "TASK-003", "TASK-004"):
        _complete(tid)
    # TASK-006 depends on TASK-004 and TASK-005; TASK-005 not done yet
    assert _tasks()["TASK-006"].state is TaskState.BLOCKED
    _complete("TASK-005")
    assert _tasks()["TASK-006"].state is TaskState.READY


# 13: a dependency in review does not unblock its dependents
def test_review_dependency_does_not_unblock(planned):
    for tid in ("TASK-001", "TASK-002", "TASK-003"):
        _complete(tid)
    _complete("TASK-005")
    runner.invoke(app, ["start", SLUG, "TASK-004"])
    runner.invoke(app, ["review", SLUG, "TASK-004"])  # 004 in review, not done
    assert _tasks()["TASK-006"].state is TaskState.BLOCKED


# 14 + 15: reject releases locks but does not unblock dependents
def test_reject_releases_locks_no_unblock(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    r = runner.invoke(app, ["reject", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert _tasks()["TASK-001"].state is TaskState.REJECTED
    assert not any(lk.task_id == "TASK-001" for lk in _locks())  # released
    assert _tasks()["TASK-002"].state is TaskState.BLOCKED        # not unblocked


# 16: invalid transitions are refused with a clear error
def test_invalid_transitions(planned):
    # ready -> done is not allowed (must go through doing)
    r1 = runner.invoke(app, ["done", SLUG, "TASK-001"])
    assert r1.exit_code == 1
    assert "Cannot move TASK-001" in r1.output

    # done -> start (doing) is not allowed
    _complete("TASK-001")
    r2 = runner.invoke(app, ["start", SLUG, "TASK-001"])
    assert r2.exit_code == 1
    assert "not 'ready'" in r2.output


def test_unknown_project_and_task_error(planned):
    assert runner.invoke(app, ["status", "nope"]).exit_code == 1
    assert runner.invoke(app, ["start", SLUG, "TASK-999"]).exit_code == 1
