"""Tests for the `agentdesk validate-project` CLI command (v0.4.2).

Deterministic: the only thing that ever runs is a test command we pass explicitly, and we use the
pinned interpreter for it so pass/fail is reproducible across platforms.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agentdesk.cli.main import app
from agentdesk.config import db_path
from agentdesk.models import FileLock, Project, RiskLevel, Task, TaskState, TaskType
from agentdesk.storage import Storage

runner = CliRunner()

PASS_CMD = f'"{sys.executable}" -c "import sys; sys.exit(0)"'
FAIL_CMD = f'"{sys.executable}" -c "import sys; sys.exit(1)"'


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True, check=True)


def _init_repo(root: Path, *, readme: bool = True) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test")
    _git(root, "checkout", "-q", "-b", "main")
    if readme:
        (root / "README.md").write_text("# Demo\n", encoding="utf-8")
    (root / "main.py").write_text("print('hi')\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "init")


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENTDESK_HOME", str(tmp_path / "home"))
    return tmp_path


# --------------------------------------------------------------------- clean project
def test_clean_project_passes(home):
    root = home / "proj"
    _init_repo(root)
    r = runner.invoke(app, ["validate-project", str(root)])
    assert r.exit_code == 0, r.output
    assert "Result: PASS" in r.output
    assert "[PASS] git:" in r.output
    assert "Working tree clean" in r.output
    assert "[PASS] readme:" in r.output


# ----------------------------------------------------------------------- missing path
def test_missing_path_fails(home):
    r = runner.invoke(app, ["validate-project", str(home / "does-not-exist")])
    assert r.exit_code == 1
    assert "Path does not exist" in r.output


def test_path_is_file_fails(home):
    f = home / "afile.txt"
    f.write_text("x\n", encoding="utf-8")
    r = runner.invoke(app, ["validate-project", str(f)])
    assert r.exit_code == 1
    assert "Not a directory" in r.output


# -------------------------------------------------------------------- missing README
def test_missing_readme_warns(home):
    root = home / "proj"
    _init_repo(root, readme=False)
    r = runner.invoke(app, ["validate-project", str(root)])
    # Missing README is a warning, not a hard failure -> exit 0.
    assert r.exit_code == 0, r.output
    assert "[WARN] readme:" in r.output
    assert "No README found" in r.output
    assert "Result: PASS_WITH_WARNINGS" in r.output


# ----------------------------------------------------------------- non-git directory
def test_non_git_directory_warns(home):
    root = home / "plain"
    root.mkdir()
    (root / "README.md").write_text("# Plain\n", encoding="utf-8")
    r = runner.invoke(app, ["validate-project", str(root)])
    assert r.exit_code == 0, r.output
    assert "Git repository not detected." in r.output
    assert "Result: PASS_WITH_WARNINGS" in r.output


# ----------------------------------------------------------- test command pass / fail
def test_passing_test_command(home):
    root = home / "proj"
    _init_repo(root)
    r = runner.invoke(app, ["validate-project", str(root), "--test-command", PASS_CMD])
    assert r.exit_code == 0, r.output
    assert "[PASS] tests:" in r.output
    assert "Result: PASS" in r.output


def test_failing_test_command_fails(home):
    root = home / "proj"
    _init_repo(root)
    r = runner.invoke(app, ["validate-project", str(root), "--test-command", FAIL_CMD])
    assert r.exit_code == 1
    assert "[FAIL] tests:" in r.output
    assert "Result: FAIL" in r.output


# ------------------------------------------------------------------------ JSON output
def test_json_output_is_parseable(home):
    root = home / "proj"
    _init_repo(root)
    r = runner.invoke(app, ["validate-project", str(root), "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["outcome"] == "PASS"
    names = {c["name"] for c in data["checks"]}
    assert {"git", "readme", "tests", "conflict", "handover"} <= names


def test_json_output_failure_exit_code(home):
    root = home / "proj"
    _init_repo(root)
    r = runner.invoke(app, ["validate-project", str(root), "--json", "--test-command", FAIL_CMD])
    assert r.exit_code == 1
    data = json.loads(r.output)
    assert data["outcome"] == "FAIL"


# ----------------------------------------------------- registered project: locks + handover
def test_registered_project_surfaces_locks_and_handover(home):
    root = home / "proj"
    _init_repo(root)
    slug = "demo"
    with Storage(db_path()) as store:
        store.add_project(Project(id=slug, name="Demo", idea="x", root_path=str(root)))
        store.add_task(Task(
            id="TASK-001", project_id=slug, name="Impl", task_type=TaskType.IMPLEMENTATION,
            risk=RiskLevel.MEDIUM, state=TaskState.DOING, allowed_files=["main.py"],
            acceptance_criteria=["works"], objective="Implement the entrypoint module.",
        ))
        store.add_lock(FileLock(project_id=slug, task_id="TASK-001", file_path="main.py"))

    r = runner.invoke(app, ["validate-project", str(root)])
    assert r.exit_code == 0, r.output
    # Active lock -> conflict warning; in-progress task without a handover -> handover warning.
    assert "[WARN] conflict:" in r.output
    assert "main.py" in r.output
    assert "[WARN] handover:" in r.output
    assert "TASK-001" in r.output
    assert "Result: PASS_WITH_WARNINGS" in r.output


# ----------------------------------------------------------------- help includes command
def test_help_lists_validate_project():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    assert "validate-project" in r.output
