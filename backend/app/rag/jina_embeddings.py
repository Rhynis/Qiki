"""Jina embedding service for retrieval fallback."""

import unicodedata
from typing import Any, ClassVar, Literal

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)

JinaEmbeddingTask = Literal["retrieval.query", "retrieval.passage"]


class JinaEmbeddingService:
    """Generate 768-dimensional embeddings with Jina v3."""

    _instance: ClassVar["JinaEmbeddingService | None"] = None

    def __new__(cls, *args: object, **kwargs: object) -> "JinaEmbeddingService":
        """Return the singleton service instance."""
        del args, kwargs
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            settings = get_settings()
            self.api_key = settings.JINA_API_KEY or ""
            self.model_name = settings.JINA_EMBED_MODEL
            self.dimensions = settings.EMBEDDING_DIMENSIONS
            self.base_url = "https://api.jina.ai/v1"
            self.timeout = 60
            self.logger = get_logger(__name__)
            self._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state for tests."""
        cls._instance = None

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text before embedding."""
        if not text:
            return ""
        normalized = unicodedata.normalize("NFC", text)
        normalized = " ".join(normalized.split())
        return normalized[:1500]

    async def embed_text(self, text: str, *, task: JinaEmbeddingTask) -> list[float]:
        """Embed one text with the specified Jina retrieval task."""
        normalized = self._normalize_text(text)
        if not normalized:
            return [0.0] * self.dimensions
        embeddings = await self.embed_batch([normalized], task=task, batch_size=1)
        return embeddings[0] if embeddings else [0.0] * self.dimensions

    async def embed_batch(
        self,
        texts: list[str],
        *,
        task: JinaEmbeddingTask,
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed multiple texts in chunks."""
        if not texts:
            return []
        normalized = [self._normalize_text(text) for text in texts]
        results: list[list[float]] = []
        for start in range(0, len(normalized), batch_size):
            chunk = normalized[start : start + batch_size]
            data = await self._post_embeddings(chunk, task)
            results.extend(self._extract_embedding(item) for item in data.get("data", []))
        return results

    async def _post_embeddings(
        self,
        texts: list[str],
        task: JinaEmbeddingTask,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model_name,
            "input": texts,
            "dimensions": self.dimensions,
            "task": task,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._headers,
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Jina request timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise self._map_http_status_error(exc) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Cannot connect to Jina: {exc}") from exc
        if not isinstance(data, dict):
            raise LLMInvalidRequestError("Jina returned an invalid embedding response")
        return data

    def _map_http_status_error(self, exc: httpx.HTTPStatusError) -> Exception:
        status_code = exc.response.status_code
        response_text = exc.response.text
        message = response_text.lower()
        if status_code == 429:
            if "quota" in message or "exceeded" in message:
                return LLMQuotaExceededError(f"Jina quota exceeded: {response_text}")
            return LLMRateLimitError(f"Jina rate limited: {response_text}")
        if status_code == 400:
            return LLMInvalidRequestError(f"Jina invalid request: {response_text}")
        if status_code in (408, 504):
            return LLMTimeoutError(f"Jina timeout: {response_text}")
        return LLMConnectionError(f"Jina returned {status_code}: {response_text}")

    def _extract_embedding(self, item: Any) -> list[float]:
        if not isinstance(item, dict):
            return [0.0] * self.dimensions
        values = item.get("embedding", [])
        if not isinstance(values, list):
            return [0.0] * self.dimensions
        return [float(value) for value in values]
