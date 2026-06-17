"""SQLite storage layer for Agent Desk.

Persistence strategy: each table keeps a few indexed key columns plus a `data` TEXT column holding
the full Pydantic model as JSON. This keeps the schema small and forward-compatible — new optional
fields (e.g. the Git-ready Task fields) ride along in the JSON without a migration.

The conflict guard relies on a UNIQUE(project_id, file_path) constraint on `locks`: the database
itself prevents two tasks from reserving the same file.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from agentdesk.models import (
    FileLock,
    GateResult,
    Handover,
    Project,
    RoutingDecision,
    Task,
)


class FileLockConflict(Exception):
    """Raised when a task tries to reserve a file already locked by another task."""

    def __init__(self, file_path: str, held_by: str):
        self.file_path = file_path
        self.held_by = held_by
        super().__init__(f"File '{file_path}' is already locked by task '{held_by}'.")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id      TEXT PRIMARY KEY,
    status  TEXT NOT NULL,
    data    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT NOT NULL,
    project_id  TEXT NOT NULL,
    state       TEXT NOT NULL,
    data        TEXT NOT NULL,
    PRIMARY KEY (project_id, id),
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS locks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id  TEXT NOT NULL,
    task_id     TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    data        TEXT NOT NULL,
    UNIQUE (project_id, file_path)
);

CREATE TABLE IF NOT EXISTS handovers (
    task_id  TEXT PRIMARY KEY,
    data     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS gate_results (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  TEXT NOT NULL,
    data     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS routing_decisions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id  TEXT NOT NULL,
    data     TEXT NOT NULL
);
"""


class Storage:
    """Thin wrapper around a SQLite connection. Safe to reopen — state persists on disk."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._migrate()

    def _migrate(self) -> None:
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ------------------------------------------------------------------ projects
    def add_project(self, project: Project) -> Project:
        self._conn.execute(
            "INSERT INTO projects (id, status, data) VALUES (?, ?, ?)",
            (project.id, project.status.value, project.model_dump_json()),
        )
        self._conn.commit()
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        row = self._conn.execute(
            "SELECT data FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return Project.model_validate_json(row["data"]) if row else None

    def list_projects(self) -> list[Project]:
        rows = self._conn.execute("SELECT data FROM projects ORDER BY id").fetchall()
        return [Project.model_validate_json(r["data"]) for r in rows]

    def update_project(self, project: Project) -> Project:
        self._conn.execute(
            "UPDATE projects SET status = ?, data = ? WHERE id = ?",
            (project.status.value, project.model_dump_json(), project.id),
        )
        self._conn.commit()
        return project

    # --------------------------------------------------------------------- tasks
    def add_task(self, task: Task) -> Task:
        self._conn.execute(
            "INSERT INTO tasks (id, project_id, state, data) VALUES (?, ?, ?, ?)",
            (task.id, task.project_id, task.state.value, task.model_dump_json()),
        )
        self._conn.commit()
        return task

    def get_task(self, project_id: str, task_id: str) -> Optional[Task]:
        row = self._conn.execute(
            "SELECT data FROM tasks WHERE project_id = ? AND id = ?",
            (project_id, task_id),
        ).fetchone()
        return Task.model_validate_json(row["data"]) if row else None

    def list_tasks(self, project_id: str) -> list[Task]:
        rows = self._conn.execute(
            "SELECT data FROM tasks WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        return [Task.model_validate_json(r["data"]) for r in rows]

    def count_tasks(self, project_id: str) -> int:
        row = self._conn.execute(
            "SELECT COUNT(*) AS n FROM tasks WHERE project_id = ?", (project_id,)
        ).fetchone()
        return int(row["n"])

    def update_task(self, task: Task) -> Task:
        self._conn.execute(
            "UPDATE tasks SET state = ?, data = ? WHERE project_id = ? AND id = ?",
            (task.state.value, task.model_dump_json(), task.project_id, task.id),
        )
        self._conn.commit()
        return task

    # --------------------------------------------------------------------- locks
    def add_lock(self, lock: FileLock) -> FileLock:
        """Reserve a file for a task. Raises FileLockConflict if already reserved."""
        existing = self.lock_for_file(lock.project_id, lock.file_path)
        if existing is not None:
            raise FileLockConflict(lock.file_path, existing.task_id)
        cur = self._conn.execute(
            "INSERT INTO locks (project_id, task_id, file_path, data) VALUES (?, ?, ?, ?)",
            (lock.project_id, lock.task_id, lock.file_path, lock.model_dump_json()),
        )
        self._conn.commit()
        lock.id = cur.lastrowid
        return lock

    def lock_for_file(self, project_id: str, file_path: str) -> Optional[FileLock]:
        row = self._conn.execute(
            "SELECT data FROM locks WHERE project_id = ? AND file_path = ?",
            (project_id, file_path),
        ).fetchone()
        return FileLock.model_validate_json(row["data"]) if row else None

    def locks_for_project(self, project_id: str) -> list[FileLock]:
        rows = self._conn.execute(
            "SELECT data FROM locks WHERE project_id = ? ORDER BY id", (project_id,)
        ).fetchall()
        return [FileLock.model_validate_json(r["data"]) for r in rows]

    def release_task_locks(self, project_id: str, task_id: str) -> int:
        cur = self._conn.execute(
            "DELETE FROM locks WHERE project_id = ? AND task_id = ?", (project_id, task_id)
        )
        self._conn.commit()
        return cur.rowcount

    # ----------------------------------------------------------------- handovers
    def save_handover(self, handover: Handover) -> Handover:
        self._conn.execute(
            "INSERT INTO handovers (task_id, data) VALUES (?, ?) "
            "ON CONFLICT(task_id) DO UPDATE SET data = excluded.data",
            (handover.task_id, handover.model_dump_json()),
        )
        self._conn.commit()
        return handover

    def get_handover(self, task_id: str) -> Optional[Handover]:
        row = self._conn.execute(
            "SELECT data FROM handovers WHERE task_id = ?", (task_id,)
        ).fetchone()
        return Handover.model_validate_json(row["data"]) if row else None

    # -------------------------------------------------------------- gate results
    def save_gate_result(self, result: GateResult) -> GateResult:
        self._conn.execute(
            "INSERT INTO gate_results (task_id, data) VALUES (?, ?)",
            (result.task_id, result.model_dump_json()),
        )
        self._conn.commit()
        return result

    # -------------------------------------------------------- routing decisions
    def save_routing_decision(self, decision: RoutingDecision) -> RoutingDecision:
        self._conn.execute(
            "INSERT INTO routing_decisions (task_id, data) VALUES (?, ?)",
            (decision.task_id, decision.model_dump_json()),
        )
        self._conn.commit()
        return decision
