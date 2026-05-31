"""Vietnamese text embedding service backed by the Gemini embedding API.

Uses the hosted Gemini embedding model instead of a local SBERT model so the
container stays lightweight (no torch/sentence-transformers) and never OOMs.
"""

import unicodedata
from typing import ClassVar

from google import genai
from google.genai import errors, types

from app.core.config import get_settings
from app.core.logging import get_logger


class EmbeddingService:
    """Generate embeddings for Vietnamese text via the Gemini embedding API."""

    _instance: ClassVar["EmbeddingService | None"] = None
    _client: ClassVar[genai.Client | None] = None

    def __new__(cls, *args: object, **kwargs: object) -> "EmbeddingService":
        """Return the singleton service instance."""
        del args, kwargs
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            settings = get_settings()
            self.model_name = settings.GEMINI_EMBED_MODEL
            self.dimensions = settings.EMBEDDING_DIMENSIONS
            self._api_key = settings.GEMINI_API_KEY or ""
            self.logger = get_logger(__name__)
            self._initialized = True

    @classmethod
    def reset(cls) -> None:
        """Reset singleton state for tests."""
        cls._instance = None
        cls._client = None

    def _get_client(self) -> genai.Client:
        """Create the Gemini client lazily on first use."""
        if EmbeddingService._client is None:
            EmbeddingService._client = genai.Client(api_key=self._api_key)
        return EmbeddingService._client

    def _normalize_text(self, text: str) -> str:
        """Normalize Vietnamese text before embedding."""
        if not text:
            return ""
        normalized = unicodedata.normalize("NFC", text)
        normalized = " ".join(normalized.split())
        return normalized[:1500]

    async def embed_text(self, text: str) -> list[float]:
        """Embed one text via the Gemini embedding API."""
        normalized = self._normalize_text(text)
        if not normalized:
            return [0.0] * self.get_dimensions()
        try:
            response = await self._get_client().aio.models.embed_content(
                model=self.model_name,
                contents=normalized,
                config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
            )
        except errors.APIError as exc:
            self.logger.error("embedding_failed", error=str(exc))
            raise
        return self._values(response, 0)

    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """Embed multiple texts, chunked to keep request sizes reasonable."""
        if not texts:
            return []
        normalized = [self._normalize_text(text) for text in texts]
        results: list[list[float]] = []
        for start in range(0, len(normalized), batch_size):
            chunk = normalized[start : start + batch_size]
            try:
                response = await self._get_client().aio.models.embed_content(
                    model=self.model_name,
                    contents=chunk,
                    config=types.EmbedContentConfig(output_dimensionality=self.dimensions),
                )
            except errors.APIError as exc:
                self.logger.error("embedding_batch_failed", error=str(exc))
                raise
            results.extend(self._values(response, index) for index in range(len(chunk)))
        return results

    def _values(self, response: object, index: int) -> list[float]:
        embeddings = list(getattr(response, "embeddings", None) or [])
        if index >= len(embeddings):
            return [0.0] * self.get_dimensions()
        values = list(getattr(embeddings[index], "values", None) or [])
        return [float(value) for value in values]

    def get_dimensions(self) -> int:
        """Return embedding dimensionality."""
        return self.dimensions
