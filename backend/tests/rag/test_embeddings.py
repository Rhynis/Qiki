"""Tests for the Gemini-backed embedding service."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.rag.embeddings import EmbeddingService

pytestmark = pytest.mark.asyncio


def _embedding(value: float) -> SimpleNamespace:
    return SimpleNamespace(values=[value] * 768)


@pytest.fixture(autouse=True)
def mock_gemini_embed(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    EmbeddingService.reset()

    async def embed_content(*, model: str, contents: object, **kwargs: object) -> SimpleNamespace:
        del model, kwargs
        if isinstance(contents, list):
            return SimpleNamespace(
                embeddings=[_embedding(index + 1) for index, _ in enumerate(contents)]
            )
        return SimpleNamespace(embeddings=[_embedding(0.5)])

    embed_mock = AsyncMock(side_effect=embed_content)
    client = Mock()
    client.aio.models.embed_content = embed_mock
    monkeypatch.setattr("app.rag.embeddings.genai.Client", Mock(return_value=client))
    yield embed_mock
    EmbeddingService.reset()


async def test_embed_text_returns_768_dim_vector() -> None:
    embedding = await EmbeddingService().embed_text("Bình gas Petrolimex")

    assert len(embedding) == 768


async def test_embed_text_consistent() -> None:
    service = EmbeddingService()

    first = await service.embed_text("Bình gas Petrolimex")
    second = await service.embed_text("Bình gas Petrolimex")

    assert first == second


async def test_embed_batch_efficiency() -> None:
    embeddings = await EmbeddingService().embed_batch(["a", "b", "c"])

    assert len(embeddings) == 3
    assert all(len(embedding) == 768 for embedding in embeddings)


async def test_embed_handles_empty_text() -> None:
    embedding = await EmbeddingService().embed_text("")

    assert embedding == [0.0] * 768


async def test_embed_handles_long_text(mock_gemini_embed: AsyncMock) -> None:
    long_text = "gas " * 1000

    await EmbeddingService().embed_text(long_text)

    sent = mock_gemini_embed.await_args.kwargs["contents"]
    assert isinstance(sent, str)
    assert len(sent) <= 1500


async def test_embed_handles_vietnamese_diacritics() -> None:
    embedding = await EmbeddingService().embed_text("Bình gas Petrolimex")

    assert len(embedding) == 768


async def test_embed_singleton(mock_gemini_embed: AsyncMock) -> None:
    first = EmbeddingService()
    second = EmbeddingService()
    await asyncio.gather(first.embed_text("a"), second.embed_text("b"))

    assert first is second
    assert mock_gemini_embed.await_count == 2
