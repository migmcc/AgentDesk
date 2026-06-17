"""Task state machine — validate and apply user-initiated state transitions.

This governs transitions a *user* triggers via the CLI (start/done/review/reject). The automatic
`blocked` ⇄ `ready` movement driven by dependencies is the dependency manager's job, not this
module's — keep the two concerns separate.
"""

from agentdesk.state_machine.transitions import (
    ALLOWED_TRANSITIONS,
    InvalidTransition,
    apply_transition,
    can_transition,
    validate_transition,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "InvalidTransition",
    "apply_transition",
    "can_transition",
    "validate_transition",
]
