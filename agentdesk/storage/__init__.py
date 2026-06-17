"""Local persistence layer (SQLite)."""

from agentdesk.storage.db import FileLockConflict, Storage

__all__ = ["Storage", "FileLockConflict"]
