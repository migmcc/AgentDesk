"""Local model — advisory assistance for low-risk support tasks (Phase 5).

The local model summarizes, reviews prompts/docs, and drafts handovers. It is an assistant, not an
executor: it never changes code, task state, the official handover, or Git.
"""

from agentdesk.local_model.assist import MODES, build_prompt, run_assist
from agentdesk.local_model.config import LocalModelConfig
from agentdesk.local_model.providers import (
    BaseProvider,
    FakeProvider,
    LocalModelError,
    OpenAICompatibleProvider,
    get_provider,
)

__all__ = [
    "LocalModelConfig",
    "LocalModelError",
    "BaseProvider",
    "FakeProvider",
    "OpenAICompatibleProvider",
    "get_provider",
    "run_assist",
    "build_prompt",
    "MODES",
]
