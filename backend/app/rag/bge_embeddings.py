"""BGE (bge-m3) embedding service for local/offline retrieval."""

import unicodedata
from typing import Any, ClassVar

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMTimeoutError,
)


class BgeEmbeddingService:
    """Generate 1024-dimensional embeddings with a local Ollama bge-m3 model.

    Mirrors ``OllamaEmbeddingService`` but uses the ``bge-m3`` model (1024-d,
    stronger on Vietnamese than nomic-embed-text). Same Ollama ``/api/embeddings``
    endpoint (one prompt per request); the returned vector must be 1024-d to match
    the ``embedding_bge`` column / ``vector(1024)``.
    """

    _instance: ClassVar["BgeEmbeddingService | None"] = None

    def __new__(cls, *args: object, **kwargs: object) -> "BgeEmbeddingService":
        """Return the singleton service instance."""
        del args, kwargs
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            settings = get_settings()
            self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
            self.model_name = settings.OLLAMA_BGE_MODEL
            self.dimensions = settings.BGE_EMBEDDING_DIMENSIONS
            self.timeout = settings.OLLAMA_TIMEOUT
            self.logger = get_logger(__name__)
            self._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state for tests."""
        cls._instance = None

    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text before embedding."""
        if not text:
            return ""
        normalized = unicodedata.normalize("NFC", text)
        normalized = " ".join(normalized.split())
        return normalized[:2000]

    async def embed_text(self, text: str) -> list[float]:
        """Embed one text; returns a zero vector for empty input."""
        normalized = self._normalize_text(text)
        if not normalized:
            return [0.0] * self.dimensions
        data = await self._post_embedding(normalized)
        return self._extract_embedding(data)

    async def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> list[list[float]]:
        """Embed multiple texts. Ollama embeds a single prompt per request."""
        del batch_size  # Ollama /api/embeddings accepts one prompt per call.
        if not texts:
            return []
        return [await self.embed_text(text) for text in texts]

    async def _post_embedding(self, text: str) -> dict[str, Any]:
        payload = {"model": self.model_name, "prompt": text}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException as exc:
            raise LLMTimeoutError(f"Ollama bge embedding timed out: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            raise LLMInvalidRequestError(
                f"Ollama returned {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMConnectionError(f"Cannot connect to Ollama: {exc}") from exc
        if not isinstance(data, dict):
            raise LLMInvalidRequestError("Ollama returned an invalid embedding response")
        return data

    def _extract_embedding(self, data: dict[str, Any]) -> list[float]:
        values = data.get("embedding")
        if not isinstance(values, list):
            raise LLMInvalidRequestError("Ollama embedding response missing 'embedding'")
        embedding = [float(value) for value in values]
        if len(embedding) != self.dimensions:
            raise LLMInvalidRequestError(
                f"BGE embedding has {len(embedding)} dimensions, expected {self.dimensions}"
            )
        return embedding
