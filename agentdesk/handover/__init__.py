"""Handover generator — produce handover.md for continuity between models and sessions.

Run E. Deterministic: it records what the system can observe and writes "Not recorded
automatically in MVP." for anything that would require Git/diffs/test runs.
"""

from agentdesk.handover.generator import (
    PLACEHOLDER_SUMMARY,
    build_handover,
    generate_handover,
    next_recommended_task,
)

__all__ = [
    "build_handover",
    "generate_handover",
    "next_recommended_task",
    "PLACEHOLDER_SUMMARY",
]
