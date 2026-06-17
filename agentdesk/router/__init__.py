"""Model router — chooses the best model for each task using fixed rules + manual override."""

from agentdesk.router.rules import (
    DEFAULT_OVERRIDE_REASON,
    ROUTING_RULES,
    local_model_allowed,
    parse_model,
    route,
)

__all__ = [
    "route",
    "ROUTING_RULES",
    "local_model_allowed",
    "parse_model",
    "DEFAULT_OVERRIDE_REASON",
]
