"""Tests for the SQLite storage layer, including persistence across reopen."""

import pytest

from agentdesk.models import FileLock, Project, Task, TaskState
from agentdesk.storage import FileLockConflict, Storage


@pytest.fixture()
def db_file(tmp_path):
    return tmp_path / "agentdesk.db"


def test_project_persists_across_reopen(db_file):
    store = Storage(db_file)
    store.add_project(Project(id="demo", name="Demo", idea="idea"))
    store.close()

    # Reopen a fresh Storage on the same file — state must survive.
    store2 = Storage(db_file)
    loaded = store2.get_project("demo")
    assert loaded is not None
    assert loaded.name == "Demo"
    assert [p.id for p in store2.list_projects()] == ["demo"]
    store2.close()


def test_task_crud_and_count(db_file):
    with Storage(db_file) as store:
        store.add_project(Project(id="demo", name="Demo", idea="idea"))
        assert store.count_tasks("demo") == 0

        store.add_task(Task(id="TASK-001", project_id="demo", name="First"))
        store.add_task(Task(id="TASK-002", project_id="demo", name="Second"))
        assert store.count_tasks("demo") == 2

        t = store.get_task("demo", "TASK-001")
        t.state = TaskState.DOING
        store.update_task(t)
        assert store.get_task("demo", "TASK-001").state is TaskState.DOING


def test_file_lock_blocks_second_task_on_same_file(db_file):
    with Storage(db_file) as store:
        store.add_project(Project(id="demo", name="Demo", idea="idea"))
        store.add_lock(FileLock(project_id="demo", task_id="TASK-001", file_path="src/app.py"))

        with pytest.raises(FileLockConflict) as exc:
            store.add_lock(FileLock(project_id="demo", task_id="TASK-002", file_path="src/app.py"))
        assert exc.value.held_by == "TASK-001"

        # Releasing TASK-001's locks frees the file.
        assert store.release_task_locks("demo", "TASK-001") == 1
        store.add_lock(FileLock(project_id="demo", task_id="TASK-002", file_path="src/app.py"))
        assert store.lock_for_file("demo", "src/app.py").task_id == "TASK-002"


def test_locks_are_scoped_per_project(db_file):
    with Storage(db_file) as store:
        store.add_project(Project(id="a", name="A", idea="i"))
        store.add_project(Project(id="b", name="B", idea="i"))
        store.add_lock(FileLock(project_id="a", task_id="T1", file_path="shared.py"))
        # Same path in a different project is fine.
        store.add_lock(FileLock(project_id="b", task_id="T1", file_path="shared.py"))
        assert len(store.locks_for_project("a")) == 1
        assert len(store.locks_for_project("b")) == 1
