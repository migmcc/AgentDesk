"""Tests for Run E: handover generation, quality gate, and the end-to-end MVP flow."""

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


def _add_task(slug, **kwargs):
    defaults = dict(project_id=slug, state=TaskState.READY, acceptance_criteria=["works"],
                    allowed_files=["docs/x.md"])
    defaults.update(kwargs)
    with Storage(db_path()) as store:
        store.add_task(Task(**defaults))


def _gate_output(slug, task_id):
    return runner.invoke(app, ["gate", slug, task_id])


# 1 + 2 + 4: handover creates a file, persists, and does not invent changes
def test_handover_creates_file_and_persists(planned):
    _, root = planned
    r = runner.invoke(app, ["handover", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert "handovers/TASK-001.md" in r.output
    path = root / "handovers" / "TASK-001.md"
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "# Handover TASK-001" in content
    assert "Not recorded automatically in MVP." in content  # no invented changes
    with Storage(db_path()) as store:
        assert store.get_handover(SLUG, "TASK-001") is not None


# 3: --summary stored in file and DB
def test_handover_summary_recorded(planned):
    _, root = planned
    summary = "Implemented parser skeleton and validation rules."
    r = runner.invoke(app, ["handover", SLUG, "TASK-001", "--summary", summary])
    assert r.exit_code == 0, r.output
    assert summary in (root / "handovers" / "TASK-001.md").read_text(encoding="utf-8")
    with Storage(db_path()) as store:
        assert store.get_handover(SLUG, "TASK-001").summary == summary


# 5: gate FAIL when no handover
def test_gate_fails_without_handover(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    r = _gate_output(SLUG, "TASK-001")
    assert r.exit_code == 0, r.output
    assert "Quality Gate: FAIL" in r.output
    assert "Handover not found." in r.output


# 6: gate detects unsatisfied dependencies
def test_gate_detects_unsatisfied_dependencies(planned):
    runner.invoke(app, ["handover", SLUG, "TASK-002"])  # has handover but is blocked by TASK-001
    r = _gate_output(SLUG, "TASK-002")
    assert "Quality Gate: FAIL" in r.output
    assert "blocked by TASK-001" in r.output


# 7: gate detects missing acceptance criteria
def test_gate_detects_missing_criteria(planned):
    _add_task(SLUG, id="TASK-100", name="No criteria", task_type=TaskType.DOCUMENTATION,
              risk=RiskLevel.LOW, acceptance_criteria=[])
    runner.invoke(app, ["start", SLUG, "TASK-100"])
    runner.invoke(app, ["handover", SLUG, "TASK-100", "--summary", "x"])
    r = _gate_output(SLUG, "TASK-100")
    assert "Quality Gate: FAIL" in r.output
    assert "No acceptance criteria defined." in r.output


# 8: gate is clean (no hard failures) when minimal conditions are satisfied.
# Note: a non-Git project yields PASS_WITH_WARNINGS (git-not-detected is a minor warning per spec);
# a true PASS requires a Git repo and is covered in tests/test_git_integration.py.
def test_gate_pass_minimal_non_git(planned):
    _add_task(SLUG, id="TASK-200", name="Docs", task_type=TaskType.DOCUMENTATION,
              risk=RiskLevel.LOW, allowed_files=["docs/guide.md"], acceptance_criteria=["doc done"])
    runner.invoke(app, ["prompt", SLUG, "TASK-200"])      # prompt on disk
    runner.invoke(app, ["start", SLUG, "TASK-200"])
    runner.invoke(app, ["handover", SLUG, "TASK-200", "--summary", "wrote the guide"])
    r = _gate_output(SLUG, "TASK-200")
    assert "Quality Gate: PASS_WITH_WARNINGS" in r.output
    assert "Git repository not detected." in r.output
    assert "FAIL" not in r.output


# 9: gate PASS_WITH_WARNINGS for minor warnings (medium risk)
def test_gate_pass_with_warnings(planned):
    _add_task(SLUG, id="TASK-300", name="Impl", task_type=TaskType.IMPLEMENTATION,
              risk=RiskLevel.MEDIUM, allowed_files=["src/a.py"], acceptance_criteria=["impl"])
    runner.invoke(app, ["prompt", SLUG, "TASK-300"])
    runner.invoke(app, ["start", SLUG, "TASK-300"])
    runner.invoke(app, ["handover", SLUG, "TASK-300", "--summary", "implemented"])
    r = _gate_output(SLUG, "TASK-300")
    assert "Quality Gate: PASS_WITH_WARNINGS" in r.output
    assert "Tests not recorded." in r.output


# 10: gate NEEDS_HUMAN_REVIEW for high-risk / architecture
def test_gate_needs_human_review_high_risk(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])       # architecture / high risk
    runner.invoke(app, ["handover", SLUG, "TASK-001", "--summary", "designed"])
    r = _gate_output(SLUG, "TASK-001")
    assert "Quality Gate: NEEDS_HUMAN_REVIEW" in r.output
    assert "high risk" in r.output.lower()


# 11: done warns when handover/gate are missing (but does not block)
def test_done_warns_without_handover_and_gate(planned):
    runner.invoke(app, ["start", SLUG, "TASK-001"])
    r = runner.invoke(app, ["done", SLUG, "TASK-001"])
    assert r.exit_code == 0, r.output
    assert "No handover found" in r.output
    assert "No quality gate result found" in r.output
    with Storage(db_path()) as store:
        assert store.get_task(SLUG, "TASK-001").state is TaskState.DONE  # still completes


# 12: full end-to-end MVP flow
def test_end_to_end_flow(planned):
    _, root = planned
    steps = [
        ["status", SLUG],
        ["route", SLUG, "TASK-001"],
        ["prompt", SLUG, "TASK-001"],
        ["start", SLUG, "TASK-001"],
        ["handover", SLUG, "TASK-001", "--summary", "Initial architecture task prepared."],
        ["gate", SLUG, "TASK-001"],
        ["done", SLUG, "TASK-001"],
        ["status", SLUG],
    ]
    for args in steps:
        res = runner.invoke(app, args)
        assert res.exit_code == 0, (args, res.output)

    with Storage(db_path()) as store:
        assert store.get_task(SLUG, "TASK-001").state is TaskState.DONE
        assert store.get_task(SLUG, "TASK-002").state is TaskState.READY  # unblocked
        assert store.get_handover(SLUG, "TASK-001") is not None
        assert store.get_gate_result(SLUG, "TASK-001") is not None
