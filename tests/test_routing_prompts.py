"""Tests for Run C: `agentdesk route` (+ --override) and `agentdesk prompt` (+ --model)."""

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.config import db_path
from agentdesk.models import Model
from agentdesk.storage import Storage

runner = CliRunner()

SLUG = "review-assistant"


@pytest.fixture()
def planned(tmp_path, monkeypatch):
    """A project created and planned in an isolated home; returns (slug, project_root)."""
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    work = tmp_path / "work"
    work.mkdir()
    assert runner.invoke(app, ["new", "Review Assistant", "--path", str(work)]).exit_code == 0
    assert runner.invoke(app, ["plan", SLUG]).exit_code == 0
    return SLUG, work / SLUG


def _routing(task_id):
    with Storage(db_path()) as store:
        return store.get_routing(SLUG, task_id)


# 1 + 2: route shows the recommended model and applies the fixed rules
def test_route_shows_recommended_and_applies_rules(planned):
    r3 = runner.invoke(app, ["route", SLUG, "TASK-003"])  # implementation -> codex
    assert r3.exit_code == 0, r3.output
    assert "Recommended model: codex" in r3.output
    assert "Task type: implementation" in r3.output

    r1 = runner.invoke(app, ["route", SLUG, "TASK-001"])  # architecture -> claude-code
    assert "Recommended model: claude-code" in r1.output


def test_route_resolves_project_by_name(planned):
    r = runner.invoke(app, ["route", "Review Assistant", "TASK-001"])
    assert r.exit_code == 0, r.output
    assert "TASK-001" in r.output


# 3 + 4: override is persisted and does not change type/risk/deps
def test_override_is_persisted_and_preserves_task(planned):
    before = _routing("TASK-003")
    with Storage(db_path()) as store:
        task_before = store.get_task(SLUG, "TASK-003")

    r = runner.invoke(app, ["route", SLUG, "TASK-003", "--override", "claude-code"])
    assert r.exit_code == 0, r.output
    assert "routing updated" in r.output
    assert "Override model: claude-code" in r.output
    assert "Reason: Manual override by user" in r.output

    after = _routing("TASK-003")
    assert after.manual_override is True
    assert after.override_model is Model.CLAUDE_CODE
    assert after.recommended_model is Model.CODEX  # original preserved
    assert after.effective_model is Model.CLAUDE_CODE

    # task type / risk / dependencies unchanged
    with Storage(db_path()) as store:
        task_after = store.get_task(SLUG, "TASK-003")
    assert task_after.task_type == task_before.task_type
    assert task_after.risk == task_before.risk
    assert task_after.dependencies == task_before.dependencies
    assert before.task_type == after.task_type and before.risk == after.risk


def test_invalid_override_model_errors(planned):
    r = runner.invoke(app, ["route", SLUG, "TASK-003", "--override", "gpt-9"])
    assert r.exit_code == 1
    assert "Invalid model" in r.output


# 5 + 8: prompt uses recommended model by default and writes to the right folder
def test_prompt_default_uses_recommended_and_writes_codex(planned):
    _, root = planned
    r = runner.invoke(app, ["prompt", SLUG, "TASK-003"])
    assert r.exit_code == 0, r.output
    assert "prompts/codex/TASK-003.md" in r.output
    assert (root / "prompts" / "codex" / "TASK-003.md").exists()


# 9: claude-code path
def test_prompt_claude_code_path(planned):
    _, root = planned
    r = runner.invoke(app, ["prompt", SLUG, "TASK-001"])  # architecture -> claude-code
    assert r.exit_code == 0, r.output
    assert (root / "prompts" / "claude-code" / "TASK-001.md").exists()


# 6: prompt uses the override when one exists
def test_prompt_uses_override(planned):
    _, root = planned
    runner.invoke(app, ["route", SLUG, "TASK-003", "--override", "claude-code"])
    r = runner.invoke(app, ["prompt", SLUG, "TASK-003"])
    assert r.exit_code == 0, r.output
    assert (root / "prompts" / "claude-code" / "TASK-003.md").exists()


# 7 + 10: --model writes that model's prompt but does NOT change persisted routing
def test_prompt_model_flag_does_not_change_routing(planned):
    _, root = planned
    before = _routing("TASK-003")
    r = runner.invoke(app, ["prompt", SLUG, "TASK-003", "--model", "local-model"])
    assert r.exit_code == 0, r.output
    assert (root / "prompts" / "local-model" / "TASK-003.md").exists()
    after = _routing("TASK-003")
    assert after.effective_model == before.effective_model
    assert after.manual_override == before.manual_override


# 11 + 12: blocked task warns on the CLI and the prompt file includes a dependency warning
def test_blocked_task_warning_and_prompt_section(planned):
    _, root = planned
    r = runner.invoke(app, ["prompt", SLUG, "TASK-003"])  # blocked by TASK-002
    assert r.exit_code == 0, r.output
    assert "blocked" in r.output.lower()
    content = (root / "prompts" / "codex" / "TASK-003.md").read_text(encoding="utf-8")
    assert "Dependency warning" in content
    assert "TASK-002" in content


def test_ready_task_has_no_dependency_warning(planned):
    _, root = planned
    runner.invoke(app, ["prompt", SLUG, "TASK-001"])  # ready, no deps
    content = (root / "prompts" / "claude-code" / "TASK-001.md").read_text(encoding="utf-8")
    assert "Dependency warning" not in content


# 13: unknown task errors clearly
def test_unknown_task_errors(planned):
    assert runner.invoke(app, ["route", SLUG, "TASK-999"]).exit_code == 1
    r = runner.invoke(app, ["prompt", SLUG, "TASK-999"])
    assert r.exit_code == 1
    assert "No task" in r.output


# 14: invalid model on prompt errors
def test_prompt_invalid_model_errors(planned):
    r = runner.invoke(app, ["prompt", SLUG, "TASK-003", "--model", "nope"])
    assert r.exit_code == 1
    assert "Invalid model" in r.output


def test_high_risk_local_override_warns_but_saves(planned):
    # TASK-011 is quality-gate / high risk
    r = runner.invoke(app, ["route", SLUG, "TASK-011", "--override", "local-model"])
    assert r.exit_code == 0, r.output
    assert "high-risk" in r.output.lower()
    after = _routing("TASK-011")
    assert after.override_model is Model.LOCAL  # saved anyway
