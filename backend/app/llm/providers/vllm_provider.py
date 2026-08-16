"""Self-hosted vLLM provider using its OpenAI-compatible chat completions API.

vLLM's ``--served-model-name`` endpoint speaks the same wire protocol Groq
does, so this mirrors ``GroqProvider`` almost exactly (same payload shape,
same SSE framing) rather than hand-rolling a new protocol. The one behavioral
difference: a self-hosted box's dominant failure mode is "unreachable", not
"quota exceeded", so callers that want failover on ``LLMConnectionError`` /
``LLMTimeoutError`` should build a ``FallbackLLMProvider`` with
``extra_fallback_errors`` set (see ``factory.py``'s ``vllm`` branch).
"""

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


class VLLMProvider(BaseLLMProvider):
    """LLM provider for a self-hosted vLLM OpenAI-compatible endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:8000/v1",
        model: str = "Qwen/Qwen3-4B-Instruct-AWQ",
        api_key: str | None = None,
        timeout: int = 120,
    ) -> None:
        super().__init__(model)
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        """Provider identifier."""
        return "vllm"

    @property
    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

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
                return LLMQuotaExceededError(f"vLLM quota exceeded: {response_text}")
            return LLMRateLimitError(f"vLLM rate limited: {response_text}")
        if status_code == 400:
            return LLMInvalidRequestError(f"vLLM invalid request: {response_text}")
        if status_code in (408, 504):
            return LLMTimeoutError(f"vLLM timeout: {response_text}")
        if status_code >= 500:
            return LLMConnectionError(f"vLLM server error {status_code}: {response_text}")
        return LLMInvalidRequestError(f"vLLM returned {status_code}: {response_text}")

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        stop_sequences: list[str] | None = None,
        **kwargs: object,
    ) -> LLMResponse:
        """Generate completion via vLLM's chat completions endpoint."""
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
            raise LLMTimeoutError(f"vLLM request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_status_error(exc) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Cannot connect to vLLM: {exc}") from exc

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
            # Self-hosted: no per-token API charge. Amortized GPU-hour cost is
            # reported separately by bench/serving_benchmark.py, not per response.
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
        """Stream completion chunks from vLLM."""
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
            raise LLMTimeoutError(f"vLLM stream timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_status_error(exc) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"vLLM stream failed: {exc}") from exc

    async def embed(self, text: str) -> EmbeddingResponse:
        """vLLM in chat-completion mode does not serve embeddings for this app."""
        del text
        raise NotImplementedError("VLLMProvider does not support embeddings")

    async def health_check(self) -> bool:
        """Check whether the vLLM server responds on its models endpoint.

        Uses ``GET /models`` (cheap, no GPU inference) rather than a real
        generation, matching ``OllamaProvider.health_check``'s pattern of
        pinging a lightweight status endpoint instead of spending compute.
        """
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(f"{self.base_url}/models", headers=self._headers)
                return response.status_code == 200
        except httpx.HTTPError:
            return False
        except LLMProviderError:
            return False
