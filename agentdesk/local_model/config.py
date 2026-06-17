"""Local-model configuration, read from environment variables.

The local model is an advisory assistant for low-risk support tasks. Configuration is intentionally
simple (env vars) in this phase; agentdesk.toml support can come later.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

VALID_PROVIDERS = {"fake", "openai-compatible", "ollama"}
# Local models (especially larger ones on a cold start) can take ~1 min for the first response,
# so the default is generous; override with AGENTDESK_LOCAL_TIMEOUT.
DEFAULT_TIMEOUT = 120


@dataclass
class LocalModelConfig:
    provider: Optional[str] = None
    base_url: Optional[str] = None
    model: Optional[str] = None
    timeout: int = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls) -> "LocalModelConfig":
        raw_timeout = os.environ.get("AGENTDESK_LOCAL_TIMEOUT")
        try:
            timeout = int(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT
        except ValueError:
            timeout = DEFAULT_TIMEOUT
        provider = os.environ.get("AGENTDESK_LOCAL_PROVIDER")
        return cls(
            provider=provider.strip().lower() if provider else None,
            base_url=os.environ.get("AGENTDESK_LOCAL_BASE_URL"),
            model=os.environ.get("AGENTDESK_LOCAL_MODEL"),
            timeout=timeout,
        )

    def is_configured(self) -> bool:
        """A fake provider is always usable; HTTP providers need a base_url and model."""
        if self.provider not in VALID_PROVIDERS:
            return False
        if self.provider == "fake":
            return True
        return bool(self.base_url and self.model)

    def missing(self) -> list[str]:
        """Which required settings are missing (for a clear error message)."""
        if self.provider not in VALID_PROVIDERS:
            return ["AGENTDESK_LOCAL_PROVIDER"]
        if self.provider == "fake":
            return []
        miss = []
        if not self.base_url:
            miss.append("AGENTDESK_LOCAL_BASE_URL")
        if not self.model:
            miss.append("AGENTDESK_LOCAL_MODEL")
        return miss
