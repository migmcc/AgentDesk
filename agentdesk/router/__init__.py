"""Model router — chooses the best model for each task using fixed rules + manual override."""

from agentdesk.router.rules import route, ROUTING_RULES, local_model_allowed

__all__ = ["route", "ROUTING_RULES", "local_model_allowed"]
