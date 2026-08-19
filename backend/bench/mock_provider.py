"""Deterministic in-process mock LLM provider for CI-safe benchmarking.

No network calls, no GPU, no external process — this is what
``--provider mock`` builds in both ``serving_benchmark.py`` and
``quality_quantization.py`` so the harnesses have a real, exercised code path
in CI instead of being skipped outright.
"""

import asyncio
import time
from collections.abc import AsyncIterator

from app.llm.base import BaseLLMProvider
from app.llm.schemas import EmbeddingResponse, LLMResponse, LLMStreamChunk

DEFAULT_RESPONSE_TEXT = (
    "Bình gas Petrolimex 12kg giá 450000 đồng, hiện còn hàng tại kho Bình Thạnh."
)


class MockLLMProvider(BaseLLMProvider):
    """In-process provider that simulates streaming latency without any I/O."""

    def __init__(
        self,
        model: str = "mock-model",
        response_text: str = DEFAULT_RESPONSE_TEXT,
        first_token_delay_s: float = 0.02,
        chunk_delay_s: float = 0.005,
    ) -> None:
        super().__init__(model)
        self.response_text = response_text
        self.first_token_delay_s = first_token_delay_s
        self.chunk_delay_s = chunk_delay_s

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "mock"

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Return the canned response after a simulated generation delay."""
        del system_prompt, temperature, max_tokens, stop_sequences, kwargs
        start = time.monotonic()
        word_count = len(self.response_text.split())
        await asyncio.sleep(self.first_token_delay_s + self.chunk_delay_s * word_count)
        latency_ms = int((time.monotonic() - start) * 1000)
        completion_tokens = self.estimate_tokens(self.response_text)
        return LLMResponse(
            text=self.response_text,
            prompt_tokens=self.estimate_tokens(prompt),
            completion_tokens=completion_tokens,
            total_tokens=completion_tokens,
            latency_ms=latency_ms,
            model=self.model,
            provider=self.provider_name,
            finish_reason="stop",
            cost_usd=0.0,
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: object,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream the canned response word by word with simulated per-token delay."""
        del prompt, system_prompt, temperature, max_tokens, kwargs
        words = self.response_text.split(" ")
        accumulated = ""
        await asyncio.sleep(self.first_token_delay_s)
        for index, word in enumerate(words):
            delta = word if index == 0 else f" {word}"
            accumulated += delta
            yield LLMStreamChunk(
                delta=delta,
                finish_reason=None,
                accumulated_text=accumulated,
                provider=self.provider_name,
                model=self.model,
            )
            await asyncio.sleep(self.chunk_delay_s)
        yield LLMStreamChunk(
            delta="",
            finish_reason="stop",
            accumulated_text=accumulated,
            provider=self.provider_name,
            model=self.model,
            total_tokens=self.estimate_tokens(accumulated),
        )

    async def embed(self, text: str) -> EmbeddingResponse:
        """Return a trivial deterministic embedding."""
        return EmbeddingResponse(embedding=[float(len(text))], dimensions=1, model=self.model)

    async def health_check(self) -> bool:
        """Always healthy — there is nothing to reach."""
        return True
