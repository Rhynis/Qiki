"""LLM provider using Google Gemini via the google-genai SDK.

Thinking is disabled (thinking_budget=0): the free flash models otherwise spend
hundreds of output tokens reasoning before answering, making each call 20-30s.
"""

import time
from collections.abc import AsyncIterator
from typing import Any, ClassVar

import httpx
from google import genai
from google.genai import errors, types
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.llm.base import BaseLLMProvider
from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.schemas import EmbeddingResponse, LLMResponse, LLMStreamChunk

# thinking_budget=0 turns off the model's hidden reasoning tokens -> fast, small,
# deterministic output that fits the request budget.
_THINKING_OFF = types.ThinkingConfig(thinking_budget=0)


def _map_error(exc: errors.APIError) -> Exception:
    """Translate a google-genai APIError into the app's LLM exception types."""
    code = getattr(exc, "code", None)
    message = str(getattr(exc, "message", exc) or exc)
    if code == 429:
        if "quota" in message.lower() or "exhausted" in message.lower():
            return LLMQuotaExceededError(f"Gemini quota exceeded: {message}")
        return LLMRateLimitError(f"Gemini rate limited: {message}")
    if code == 400:
        return LLMInvalidRequestError(f"Gemini invalid request: {message}")
    if code in (408, 504):
        return LLMTimeoutError(f"Gemini timeout: {message}")
    return LLMConnectionError(f"Gemini error: {message}")


def _response_text(response: Any) -> str:
    """Extract text from a response, tolerating empty/thinking-only candidates."""
    text = getattr(response, "text", None)
    if text:
        return str(text)
    candidates = list(getattr(response, "candidates", None) or [])
    if not candidates:
        return ""
    content = getattr(candidates[0], "content", None)
    parts = list(getattr(content, "parts", None) or [])
    return "".join(str(getattr(part, "text", "")) for part in parts if getattr(part, "text", ""))


class GeminiProvider(BaseLLMProvider):
    """LLM provider using Google Gemini (google-genai SDK), thinking disabled."""

    PRICING_PER_1M: ClassVar[dict[str, dict[str, float]]] = {
        "gemini-2.0-flash-exp": {"input": 0.075, "output": 0.30},
        "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
        "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    }

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash",
        embed_model: str = "text-embedding-004",
    ) -> None:
        super().__init__(model)
        self.embed_model = embed_model
        self._client = genai.Client(api_key=api_key)

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "gemini"

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate generation cost in USD."""
        pricing = self.PRICING_PER_1M.get(self.model, {"input": 0.0, "output": 0.0})
        return (
            input_tokens / 1_000_000 * pricing["input"]
            + output_tokens / 1_000_000 * pricing["output"]
        )

    def _config(
        self,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        stop_sequences: list[str] | None = None,
    ) -> types.GenerateContentConfig:
        return types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            stop_sequences=stop_sequences or [],
            thinking_config=_THINKING_OFF,
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
        """Generate completion via Gemini API."""
        del kwargs
        async for attempt in AsyncRetrying(
            retry=retry_if_exception_type((LLMConnectionError, LLMTimeoutError)),
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.1, min=0.1, max=1),
            reraise=True,
        ):
            with attempt:
                return await self._generate_once(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stop_sequences=stop_sequences,
                )
        raise LLMConnectionError("Gemini generation failed")

    async def _generate_once(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        stop_sequences: list[str] | None,
    ) -> LLMResponse:
        """Run one Gemini generation attempt."""
        start = time.monotonic()
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=self._config(system_prompt, temperature, max_tokens, stop_sequences),
            )
        except errors.APIError as exc:
            raise _map_error(exc) from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError(f"Gemini connection error: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        usage = getattr(response, "usage_metadata", None)
        prompt_tokens = int(getattr(usage, "prompt_token_count", 0) or 0)
        completion_tokens = int(getattr(usage, "candidates_token_count", 0) or 0)
        candidates = list(getattr(response, "candidates", None) or [])
        finish_reason = str(getattr(candidates[0], "finish_reason", "")) if candidates else None
        return LLMResponse(
            text=_response_text(response),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            latency_ms=latency_ms,
            model=self.model,
            provider=self.provider_name,
            finish_reason=finish_reason,
            cost_usd=self.calculate_cost(prompt_tokens, completion_tokens),
        )

    async def stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        **kwargs: object,
    ) -> AsyncIterator[LLMStreamChunk]:
        """Stream generation chunks from Gemini."""
        del kwargs
        accumulated = ""
        try:
            stream = await self._client.aio.models.generate_content_stream(
                model=self.model,
                contents=prompt,
                config=self._config(system_prompt, temperature, max_tokens),
            )
            async for chunk in stream:
                delta = _response_text(chunk)
                accumulated += delta
                candidates = list(getattr(chunk, "candidates", None) or [])
                finish_reason = (
                    str(getattr(candidates[0], "finish_reason", "")) if candidates else None
                )
                yield LLMStreamChunk(
                    delta=delta,
                    finish_reason=finish_reason,
                    accumulated_text=accumulated,
                )
        except errors.APIError as exc:
            raise _map_error(exc) from exc
        except httpx.HTTPError as exc:
            raise LLMConnectionError(f"Gemini connection error: {exc}") from exc

    async def embed(self, text: str) -> EmbeddingResponse:
        """Generate embeddings via Gemini."""
        try:
            response = await self._client.aio.models.embed_content(
                model=self.embed_model,
                contents=text,
            )
        except errors.APIError as exc:
            raise _map_error(exc) from exc

        embeddings = list(getattr(response, "embeddings", None) or [])
        values = list(getattr(embeddings[0], "values", None) or []) if embeddings else []
        embedding = [float(value) for value in values]
        return EmbeddingResponse(
            embedding=embedding,
            dimensions=len(embedding),
            model=self.embed_model,
        )

    async def health_check(self) -> bool:
        """Check whether Gemini responds to a tiny request."""
        try:
            response = await self._client.aio.models.generate_content(
                model=self.model,
                contents="ping",
                config=types.GenerateContentConfig(
                    max_output_tokens=8,
                    thinking_config=_THINKING_OFF,
                ),
            )
            return bool(_response_text(response))
        except (errors.APIError, httpx.HTTPError):
            return False
