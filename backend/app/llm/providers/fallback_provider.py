"""Fallback LLM provider for quota and rate-limit failover."""

from collections.abc import AsyncIterator

import sentry_sdk

from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMQuotaExceededError, LLMRateLimitError
from app.llm.schemas import EmbeddingResponse, LLMResponse, LLMStreamChunk

FALLBACK_ERRORS = (LLMQuotaExceededError, LLMRateLimitError)


class FallbackLLMProvider(BaseLLMProvider):
    """Try providers in order, falling back only on quota/rate-limit errors."""

    def __init__(self, providers: list[BaseLLMProvider]) -> None:
        if not providers:
            raise ValueError("FallbackLLMProvider requires at least one provider")
        super().__init__(providers[0].model)
        self.providers = providers

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "fallback"

    def _capture_fallback(self, provider: BaseLLMProvider) -> None:
        sentry_sdk.capture_message(
            f"{provider.provider_name} quota/rate exceeded, falling back",
            level="warning",
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Generate with the first provider that is not quota/rate limited."""
        last_error: LLMQuotaExceededError | LLMRateLimitError | None = None
        for provider in self.providers:
            try:
                return await provider.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop_sequences=stop_sequences,
                    **kwargs,
                )
            except FALLBACK_ERRORS as exc:
                last_error = exc
                if provider is not self.providers[-1]:
                    self._capture_fallback(provider)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Fallback provider failed without an error")

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: object,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream with fallback if quota/rate fails before the first chunk."""
        last_error: LLMQuotaExceededError | LLMRateLimitError | None = None
        for provider in self.providers:
            yielded = False
            try:
                async for chunk in provider.stream(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                ):
                    yielded = True
                    # Attribute the chunk to the provider that actually served it,
                    # not the "fallback" wrapper, so analytics/cost are accurate.
                    yield chunk.model_copy(
                        update={
                            "provider": chunk.provider or provider.provider_name,
                            "model": chunk.model or provider.model,
                        }
                    )
                return
            except FALLBACK_ERRORS as exc:
                if yielded:
                    raise
                last_error = exc
                if provider is not self.providers[-1]:
                    self._capture_fallback(provider)

        if last_error is not None:
            raise last_error
        raise RuntimeError("Fallback provider stream failed without an error")

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embeddings with the primary provider only."""
        return await self.providers[0].embed(text)

    async def health_check(self) -> bool:
        """Return true if any provider in the fallback chain is healthy."""
        for provider in self.providers:
            if await provider.health_check():
                return True
        return False
