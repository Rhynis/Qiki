"""Test doubles shared across backend/tests/agent/ (not a test module itself)."""

from collections.abc import AsyncIterator
from typing import Any
from unittest.mock import AsyncMock

from app.llm.schemas import LLMStreamChunk


class FakeLLMProvider:
    """A BaseLLMProvider stand-in that streams a fixed reply and records calls.

    Not a bare MagicMock: tests assert ``generate.assert_not_called()`` (the
    safety short-circuit must never reach it — the issue's literal acceptance
    wording) while other tests need genuine async-generator streaming from
    ``stream()``, which the responder node actually calls.
    """

    def __init__(self, reply: str = "OK", provider_name: str = "fake") -> None:
        self.reply = reply
        self._provider_name = provider_name
        self.generate = AsyncMock()
        self.stream_calls: list[dict[str, Any]] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def stream(self, **kwargs: Any) -> AsyncIterator[LLMStreamChunk]:
        self.stream_calls.append(kwargs)
        yield LLMStreamChunk(
            delta=self.reply,
            accumulated_text=self.reply,
            provider=self._provider_name,
            model="fake-model",
            total_tokens=None,
        )
