"""Local-model providers. Fake (deterministic, for tests) and OpenAI-compatible HTTP (stdlib only)."""

from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request

from agentdesk.local_model.config import LocalModelConfig


class LocalModelError(Exception):
    """Raised when the local model cannot be reached or returns an unusable response."""


class BaseProvider:
    name = "base"

    def complete(self, prompt: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class FakeProvider(BaseProvider):
    """Deterministic provider for tests and offline use. Never calls the network."""

    name = "fake"

    def complete(self, prompt: str) -> str:
        return (
            "[fake-local-model] Advisory response generated deterministically without a real model.\n"
            "No code was executed and no files were modified.\n"
            "This is placeholder analysis based only on the provided context."
        )


class OpenAICompatibleProvider(BaseProvider):
    """Talks to an OpenAI-compatible /chat/completions endpoint (e.g. Ollama's /v1)."""

    name = "openai-compatible"

    def __init__(self, base_url: str, model: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except (socket.timeout, TimeoutError):
            raise LocalModelError(f"Local model timed out after {self.timeout}s ({url}).")
        except urllib.error.URLError as exc:
            raise LocalModelError(f"Could not reach local model at {url}: {exc.reason}.")
        except json.JSONDecodeError as exc:
            raise LocalModelError(f"Local model returned invalid JSON: {exc}.")
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise LocalModelError("Local model response missing choices[0].message.content.")


def get_provider(config: LocalModelConfig) -> BaseProvider:
    """Build a provider from config. Raises LocalModelError if unusable."""
    if not config.is_configured():
        raise LocalModelError("Local model is not configured.")
    if config.provider == "fake":
        return FakeProvider()
    # 'ollama' uses the same OpenAI-compatible surface (e.g. base_url .../v1).
    return OpenAICompatibleProvider(config.base_url, config.model, config.timeout)
