"""Tests for LLM fallback provider behavior."""

from collections.abc import AsyncIterator
from unittest.mock import Mock

import pytest

from app.llm.base import BaseLLMProvider
from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMRateLimitError,
)
from app.llm.providers.fallback_provider import FallbackLLMProvider
from app.llm.schemas import EmbeddingResponse, LLMResponse, LLMStreamChunk

pytestmark = pytest.mark.asyncio


class FakeProvider(BaseLLMProvider):
    """Minimal test provider for fallback behavior."""

    def __init__(
        self,
        provider_name: str,
        generate_error: Exception | None = None,
        stream_error: Exception | None = None,
    ) -> None:
        super().__init__(model=f"{provider_name}-model")
        self._provider_name = provider_name
        self.generate_error = generate_error
        self.stream_error = stream_error
        self.generate_calls = 0
        self.stream_calls = 0
        self.embed_calls = 0

    @property
    def provider_name(self) -> str:
        return self._provider_name

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        del prompt, system_prompt, temperature, max_tokens, stop_sequences, kwargs
        self.generate_calls += 1
        if self.generate_error:
            raise self.generate_error
        return LLMResponse(
            text=f"{self.provider_name} ok",
            latency_ms=1,
            model=self.model,
            provider=self.provider_name,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: object,
    ) -> AsyncIterator[LLMStreamChunk]:
        del prompt, system_prompt, temperature, max_tokens, kwargs
        self.stream_calls += 1
        if self.stream_error:
            raise self.stream_error
        yield LLMStreamChunk(delta=f"{self.provider_name} chunk", accumulated_text="chunk")

    async def embed(self, text: str) -> EmbeddingResponse:
        self.embed_calls += 1
        return EmbeddingResponse(embedding=[float(len(text))], dimensions=1, model=self.model)

    async def health_check(self) -> bool:
        return self.generate_error is None


async def test_generate_falls_back_on_quota_and_captures_sentry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_message = Mock()
    monkeypatch.setattr(
        "app.llm.providers.fallback_provider.sentry_sdk.capture_message",
        capture_message,
    )
    primary = FakeProvider("gemini", generate_error=LLMQuotaExceededError("quota"))
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    response = await provider.generate("Hello")

    assert response.text == "groq ok"
    assert primary.generate_calls == 1
    assert secondary.generate_calls == 1
    capture_message.assert_called_once_with(
        "gemini quota/rate exceeded, falling back",
        level="warning",
    )


async def test_generate_uses_primary_when_available(monkeypatch: pytest.MonkeyPatch) -> None:
    capture_message = Mock()
    monkeypatch.setattr(
        "app.llm.providers.fallback_provider.sentry_sdk.capture_message",
        capture_message,
    )
    primary = FakeProvider("gemini")
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    response = await provider.generate("Hello")

    assert response.text == "gemini ok"
    assert primary.generate_calls == 1
    assert secondary.generate_calls == 0
    capture_message.assert_not_called()


async def test_generate_does_not_fallback_on_invalid_request() -> None:
    primary = FakeProvider("gemini", generate_error=LLMInvalidRequestError("bad prompt"))
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    with pytest.raises(LLMInvalidRequestError):
        await provider.generate("Hello")

    assert secondary.generate_calls == 0


async def test_generate_raises_last_error_when_all_rate_limited() -> None:
    provider = FallbackLLMProvider(
        [
            FakeProvider("gemini", generate_error=LLMRateLimitError("slow down")),
            FakeProvider("groq", generate_error=LLMQuotaExceededError("quota")),
        ]
    )

    with pytest.raises(LLMQuotaExceededError):
        await provider.generate("Hello")


async def test_stream_falls_back_when_primary_fails_before_first_chunk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_message = Mock()
    monkeypatch.setattr(
        "app.llm.providers.fallback_provider.sentry_sdk.capture_message",
        capture_message,
    )
    primary = FakeProvider("gemini", stream_error=LLMQuotaExceededError("quota"))
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    chunks = [chunk async for chunk in provider.stream("Hello")]

    assert [chunk.delta for chunk in chunks] == ["groq chunk"]
    assert primary.stream_calls == 1
    assert secondary.stream_calls == 1
    capture_message.assert_called_once()


async def test_embed_uses_primary_provider_only() -> None:
    primary = FakeProvider("gemini")
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    response = await provider.embed("gas")

    assert response.embedding == [3.0]
    assert primary.embed_calls == 1
    assert secondary.embed_calls == 0


async def test_requires_at_least_one_provider() -> None:
    with pytest.raises(ValueError, match="at least one provider"):
        FallbackLLMProvider([])


async def test_generate_does_not_fallback_on_connection_error_by_default() -> None:
    # Matches today's gemini<->groq behavior: a downed provider's connection
    # error is not one of the default fallback triggers.
    primary = FakeProvider("vllm", generate_error=LLMConnectionError("offline"))
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    with pytest.raises(LLMConnectionError):
        await provider.generate("Hello")

    assert secondary.generate_calls == 0


async def test_generate_falls_back_on_connection_error_when_extended(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    capture_message = Mock()
    monkeypatch.setattr(
        "app.llm.providers.fallback_provider.sentry_sdk.capture_message",
        capture_message,
    )
    primary = FakeProvider("vllm", generate_error=LLMConnectionError("offline"))
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider(
        [primary, secondary],
        extra_fallback_errors=(LLMConnectionError,),
    )

    response = await provider.generate("Hello")

    assert response.text == "groq ok"
    assert secondary.generate_calls == 1


async def test_stream_annotates_chunks_with_serving_provider_identity() -> None:
    # The wrapper must attribute each chunk to the provider that actually served,
    # not the "fallback" name, so streamed rows record the real provider/model.
    primary = FakeProvider("gemini", stream_error=LLMQuotaExceededError("quota"))
    secondary = FakeProvider("groq")
    provider = FallbackLLMProvider([primary, secondary])

    chunks = [chunk async for chunk in provider.stream("Hello")]

    assert chunks
    assert all(chunk.provider == "groq" for chunk in chunks)
    assert all(chunk.model == "groq-model" for chunk in chunks)
