"""Tests for Phase 5 local-model advisory assistance (uses the deterministic fake provider)."""

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.config import db_path
from agentdesk.local_model import LocalModelConfig, get_provider
from agentdesk.models import RiskLevel, Task, TaskState, TaskType
from agentdesk.storage import Storage

runner = CliRunner()
SLUG = "review-assistant"


@pytest.fixture()
def planned_fake(tmp_path, monkeypatch):
    """Planned project + fake local provider configured."""
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("AGENTDESK_LOCAL_PROVIDER", "fake")
    monkeypatch.delenv("AGENTDESK_LOCAL_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTDESK_LOCAL_MODEL", raising=False)
    work = tmp_path / "work"
    work.mkdir()
    assert runner.invoke(app, ["new", "Review Assistant", "--path", str(work)]).exit_code == 0
    assert runner.invoke(app, ["plan", SLUG]).exit_code == 0
    return SLUG, work / SLUG


def _report(root, task_id, mode):
    return root / "reports" / f"{task_id}-{mode}.md"


# 1: local-status does not crash without configuration
def test_local_status_unconfigured(tmp_path, monkeypatch):
    monkeypatch.delenv("AGENTDESK_LOCAL_PROVIDER", raising=False)
    monkeypatch.delenv("AGENTDESK_LOCAL_BASE_URL", raising=False)
    monkeypatch.delenv("AGENTDESK_LOCAL_MODEL", raising=False)
    r = runner.invoke(app, ["local-status"])
    assert r.exit_code == 0
    assert "Local model is not configured." in r.output
    assert "AGENTDESK_LOCAL_PROVIDER" in r.output


def test_local_status_configured_fake(monkeypatch):
    monkeypatch.setenv("AGENTDESK_LOCAL_PROVIDER", "fake")
    r = runner.invoke(app, ["local-status"])
    assert r.exit_code == 0
    assert "Provider: fake" in r.output
    assert "Status: configured" in r.output


# 2: fake provider is deterministic
def test_fake_provider_deterministic():
    p = get_provider(LocalModelConfig(provider="fake"))
    assert p.complete("anything") == p.complete("something else")
    assert "fake-local-model" in p.complete("x")


# 3-7: each mode writes a report under reports/
@pytest.mark.parametrize("mode", ["summary", "prompt-review", "doc-check", "handover-draft"])
def test_modes_write_reports(planned_fake, mode):
    _, root = planned_fake
    # prompt-review reads a prompt file; generate one first so the path exists
    if mode == "prompt-review":
        runner.invoke(app, ["prompt", SLUG, "TASK-002"])  # TASK-002 is setup -> codex, low risk
    r = runner.invoke(app, ["local-assist", SLUG, "TASK-002", "--mode", mode])
    assert r.exit_code == 0, r.output
    assert f"reports/TASK-002-{mode}.md" in r.output
    report = _report(root, "TASK-002", mode)
    assert report.exists()
    content = report.read_text(encoding="utf-8")
    assert "Advisory output" in content
    assert "fake-local-model" in content


# 8 + 9 + 10: assist does not change task state, official handover, or call Git
def test_assist_is_read_only(planned_fake):
    _, root = planned_fake
    with Storage(db_path()) as store:
        before = store.get_task(SLUG, "TASK-001").state
    runner.invoke(app, ["local-assist", SLUG, "TASK-001", "--mode", "summary"])
    with Storage(db_path()) as store:
        assert store.get_task(SLUG, "TASK-001").state is before   # state unchanged
        assert store.get_handover(SLUG, "TASK-001") is None        # no official handover created
    # no Git repo was created in the project folder
    assert not (root / ".git").exists()


# 11: high-risk task triggers an advisory warning
def test_high_risk_warning(planned_fake):
    # TASK-001 is architecture / high risk
    r = runner.invoke(app, ["local-assist", SLUG, "TASK-001", "--mode", "summary"])
    assert r.exit_code == 0, r.output
    assert "high-risk task" in r.output.lower()


# 12: clear error when the model is not configured
def test_assist_unconfigured_errors(planned_fake, monkeypatch):
    monkeypatch.delenv("AGENTDESK_LOCAL_PROVIDER", raising=False)
    r = runner.invoke(app, ["local-assist", SLUG, "TASK-001", "--mode", "summary"])
    assert r.exit_code == 1
    assert "not configured" in r.output


# 13: provider error is handled with a clear message (no crash)
def test_provider_error_handled(planned_fake, monkeypatch):
    # Configure a non-fake provider pointing nowhere -> connection error, surfaced cleanly.
    monkeypatch.setenv("AGENTDESK_LOCAL_PROVIDER", "openai-compatible")
    monkeypatch.setenv("AGENTDESK_LOCAL_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("AGENTDESK_LOCAL_MODEL", "nope")
    monkeypatch.setenv("AGENTDESK_LOCAL_TIMEOUT", "1")
    r = runner.invoke(app, ["local-assist", SLUG, "TASK-001", "--mode", "summary"])
    assert r.exit_code == 1
    assert "Local model error" in r.output


def test_invalid_mode_errors(planned_fake):
    r = runner.invoke(app, ["local-assist", SLUG, "TASK-001", "--mode", "nope"])
    assert r.exit_code == 1
    assert "Invalid mode" in r.output


def test_implementation_advisory_notice(planned_fake):
    # TASK-003 is implementation
    r = runner.invoke(app, ["local-assist", SLUG, "TASK-003", "--mode", "summary"])
    assert r.exit_code == 0, r.output
    assert "advisory output" in r.output.lower()
