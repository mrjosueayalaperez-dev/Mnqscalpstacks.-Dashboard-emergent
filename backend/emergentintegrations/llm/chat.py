"""Drop-in replacement for Emergent's ``emergentintegrations.llm.chat``.

Same interface (LlmChat / UserMessage / TextDelta / StreamDone), backed by
``litellm`` instead of Emergent's private API. litellm routes ``gpt-*``
models to OpenAI and supports 100+ other providers.

Configuration (in priority order):
  1. ``OPENAI_API_KEY`` environment variable (recommended going forward)
  2. The ``api_key`` argument passed to ``LlmChat``
  3. ``EMERGENT_LLM_KEY`` environment variable (backward compatibility)

``is_llm_configured()`` reports whether any usable key is present, so routes
can fail fast with a clear message instead of a cryptic provider error.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import AsyncIterator, List, Optional

import litellm


def resolve_api_key(passed: Optional[str] = None) -> str:
    """Return the API key to use, or raise a clear error if none is set."""
    for candidate in (
        os.environ.get("OPENAI_API_KEY", ""),
        (passed or ""),
        os.environ.get("EMERGENT_LLM_KEY", ""),
    ):
        if candidate and candidate.strip():
            return candidate.strip()
    raise RuntimeError(
        "LLM not configured: set the OPENAI_API_KEY environment variable."
    )


def is_llm_configured() -> bool:
    """True when an LLM key is available from any supported source."""
    try:
        resolve_api_key()
        return True
    except RuntimeError:
        return False


@dataclass
class UserMessage:
    text: str


@dataclass
class TextDelta:
    content: str = ""


@dataclass
class StreamDone:
    pass


class LlmChat:
    """Conversational LLM client with the same shape as Emergent's."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        session_id: str = "",
        system_message: str = "",
    ) -> None:
        self._passed_key = api_key
        self.session_id = session_id
        self.system_message = system_message
        self._provider = "openai"
        self._model = "gpt-4o"

    def with_model(self, provider: str, model: str) -> "LlmChat":
        self._provider = (provider or "openai").lower()
        self._model = model
        return self

    def _messages(self, user_text: str) -> List[dict]:
        messages: List[dict] = []
        if self.system_message:
            messages.append({"role": "system", "content": self.system_message})
        messages.append({"role": "user", "content": user_text})
        return messages

    def _litellm_model(self) -> str:
        # litellm routes bare "gpt-*" names to OpenAI automatically.
        if self._provider in ("openai", ""):
            return self._model
        return f"{self._provider}/{self._model}"

    async def send_message(self, message: UserMessage) -> str:
        key = resolve_api_key(self._passed_key)
        response = await litellm.acompletion(
            model=self._litellm_model(),
            messages=self._messages(message.text),
            api_key=key,
        )
        return response.choices[0].message.content or ""

    async def stream_message(self, message: UserMessage) -> AsyncIterator:
        key = resolve_api_key(self._passed_key)
        stream = await litellm.acompletion(
            model=self._litellm_model(),
            messages=self._messages(message.text),
            api_key=key,
            stream=True,
        )
        async for chunk in stream:
            delta = None
            try:
                delta = chunk.choices[0].delta.content
            except Exception:
                delta = None
            if delta:
                yield TextDelta(content=delta)
        yield StreamDone()
