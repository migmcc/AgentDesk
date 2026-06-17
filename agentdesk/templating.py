"""Shared Jinja2 environment for rendering Markdown docs and prompts."""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape


def templates_dir() -> Path:
    """Locate the Jinja2 templates directory (override with AGENTDESK_TEMPLATES).

    Templates live inside the package (`agentdesk/templates/`) so they ship with both editable
    and non-editable installs.
    """
    override = os.environ.get("AGENTDESK_TEMPLATES")
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parent / "templates"


def jinja_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(templates_dir())),
        autoescape=select_autoescape(enabled_extensions=()),  # plain markdown, no HTML escaping
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
