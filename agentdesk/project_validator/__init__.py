"""Project validator — deterministic, read-only validation of a local project folder.

A thin composition layer over existing capabilities (local Git, the gate's PASS/WARN/FAIL
vocabulary, and registered-project locks/handovers). Surfaced via `agentdesk validate-project`.
"""

from agentdesk.project_validator.validate import (
    Check,
    ValidationReport,
    validate_project,
)

__all__ = ["Check", "ValidationReport", "validate_project"]
