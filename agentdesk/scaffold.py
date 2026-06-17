"""Project scaffolding helpers: slug generation and on-disk project folder creation."""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from agentdesk.models import Project

# Subfolders created for every project (matches the intake document, PDF section 7).
PROJECT_SUBDIRS = [
    "docs",
    "tasks",
    "prompts/codex",
    "prompts/claude-code",
    "prompts/local-model",
    "handovers",
]


def slugify(text: str, max_len: int = 60) -> str:
    """Lowercase ASCII slug: words separated by '-', punctuation removed."""
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text)
    slug = ascii_text.strip("-")
    if len(slug) > max_len:
        slug = slug[:max_len].rstrip("-")
    return slug or "project"


def create_project_folder(project: Project, parent: Path) -> Path:
    """Create the on-disk project folder tree and write agentdesk.json.

    Returns the project root path. Raises FileExistsError if the folder already exists.
    """
    root = parent / project.id
    if root.exists():
        raise FileExistsError(f"Project folder already exists: {root}")
    for sub in PROJECT_SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    write_manifest(project, root)
    return root


def write_manifest(project: Project, root: Path) -> Path:
    """Write/refresh agentdesk.json in the project root."""
    manifest = root / "agentdesk.json"
    payload = {
        "id": project.id,
        "name": project.name,
        "idea": project.idea,
        "objective": project.objective,
        "status": project.status.value,
        "created_at": project.created_at.isoformat(),
        "agentdesk_version": __import__("agentdesk").__version__,
    }
    manifest.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest
