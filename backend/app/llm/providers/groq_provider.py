"""Groq LLM provider using the OpenAI-compatible HTTP API."""

import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.llm.base import BaseLLMProvider
from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMProviderError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.schemas import EmbeddingResponse, LLMResponse, LLMStreamChunk


class GroqProvider(BaseLLMProvider):
    """LLM provider for Groq's OpenAI-compatible chat completions API."""

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: int = 60,
    ) -> None:
        super().__init__(model)
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "groq"

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        prompt: str,
        system_prompt: str | None,
        temperature: float,
        max_tokens: int,
        stream: bool,
        stop_sequences: list[str] | None = None,
    ) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }
        if stream:
            # Ask Groq to emit a final usage chunk so a streamed answer can record
            # its token count (OpenAI-compatible streaming option).
            payload["stream_options"] = {"include_usage": True}
        if stop_sequences:
            payload["stop"] = stop_sequences
        return payload

    def _map_http_status_error(self, exc: httpx.HTTPStatusError) -> Exception:
        status_code = exc.response.status_code
        response_text = exc.response.text
        message = response_text.lower()
        if status_code == 429:
            if "quota" in message or "exceeded" in message:
                return LLMQuotaExceededError(f"Groq quota exceeded: {response_text}")
            return LLMRateLimitError(f"Groq rate limited: {response_text}")
        if status_code == 400:
            return LLMInvalidRequestError(f"Groq invalid request: {response_text}")
        if status_code in (408, 504):
            return LLMTimeoutError(f"Groq timeout: {response_text}")
        if status_code >= 500:
            return LLMConnectionError(f"Groq server error {status_code}: {response_text}")
        return LLMInvalidRequestError(f"Groq returned {status_code}: {response_text}")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Generate completion via Groq chat completions API."""
        del kwargs
        start = time.monotonic()
        payload = self._payload(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
            stop_sequences=stop_sequences,
        )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Groq request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_status_error(exc) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Cannot connect to Groq: {exc}") from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        choices = list(data.get("choices", []))
        first_choice = choices[0] if choices else {}
        message = first_choice.get("message", {})
        usage = data.get("usage", {})
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)

        return LLMResponse(
            text=str(message.get("content", "")),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            model=str(data.get("model", self.model)),
            provider=self.provider_name,
            finish_reason=first_choice.get("finish_reason"),
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
        """Stream completion chunks from Groq."""
        del kwargs
        payload = self._payload(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        accumulated = ""

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._headers,
                    json=payload,
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line.startswith("data: "):
                            continue
                        payload_line = line.removeprefix("data: ").strip()
                        if payload_line == "[DONE]":
                            break
                        data = json.loads(payload_line)
                        # The final usage frame (stream_options.include_usage) has
                        # empty choices and a usage block; surface its token count.
                        usage = data.get("usage")
                        total_tokens = (
                            int(usage.get("total_tokens", 0) or 0)
                            if isinstance(usage, dict)
                            else None
                        )
                        choice: dict[str, Any] = next(iter(data.get("choices", [{}])), {})
                        delta = str(choice.get("delta", {}).get("content", ""))
                        finish_reason = choice.get("finish_reason")
                        if not delta and finish_reason is None and total_tokens is None:
                            continue
                        accumulated += delta
                        yield LLMStreamChunk(
                            delta=delta,
                            finish_reason=finish_reason,
                            accumulated_text=accumulated,
                            provider=self.provider_name,
                            model=str(data.get("model", self.model)),
                            total_tokens=total_tokens,
                        )
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Groq stream timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_status_error(exc) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Groq stream failed: {exc}") from exc

    async def embed(self, text: str) -> EmbeddingResponse:
        """Groq does not provide embeddings for this app."""
        del text
        raise NotImplementedError("GroqProvider does not support embeddings")

    async def health_check(self) -> bool:
        """Check whether Groq responds to a tiny generation request."""
        try:
            response = await self.generate("ping", temperature=0.0, max_tokens=8)
            return bool(response.text)
        except LLMProviderError:
            return False
