"""Workspace configuration: where Agent Desk keeps its local state.

State lives under AGENTDESK_HOME (default: ~/.agentdesk). The SQLite database is `agentdesk.db`
inside that directory. Everything is local-first; nothing leaves the machine.
"""

from __future__ import annotations

import os
from pathlib import Path


def home_dir() -> Path:
    """Resolve the Agent Desk home directory, honoring the AGENTDESK_HOME env var."""
    override = os.environ.get("AGENTDESK_HOME")
    base = Path(override).expanduser() if override else Path.home() / ".agentdesk"
    return base


def db_path() -> Path:
    """Path to the local SQLite database, ensuring the home directory exists."""
    base = home_dir()
    base.mkdir(parents=True, exist_ok=True)
    return base / "agentdesk.db"
