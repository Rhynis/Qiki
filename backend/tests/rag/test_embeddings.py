"""Tests for the Gemini-backed embedding service."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from google.genai import errors

from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.rag.embeddings import EmbeddingService

pytestmark = pytest.mark.asyncio


def _embedding(value: float) -> SimpleNamespace:
    return SimpleNamespace(values=[value] * 768)


def _client_error(code: int, message: str) -> errors.ClientError:
    return errors.ClientError(code, {"error": {"message": message}})


def _server_error(code: int, message: str) -> errors.ServerError:
    return errors.ServerError(code, {"error": {"message": message}})


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
    monkeypatch.setattr("app.llm.genai_client.genai.Client", Mock(return_value=client))
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


async def test_embed_text_maps_quota_error(mock_gemini_embed: AsyncMock) -> None:
    mock_gemini_embed.side_effect = _client_error(429, "quota exhausted")

    with pytest.raises(LLMQuotaExceededError):
        await EmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_rate_limit_error(mock_gemini_embed: AsyncMock) -> None:
    mock_gemini_embed.side_effect = _client_error(429, "too many requests")

    with pytest.raises(LLMRateLimitError):
        await EmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_invalid_request(mock_gemini_embed: AsyncMock) -> None:
    mock_gemini_embed.side_effect = _client_error(400, "bad request")

    with pytest.raises(LLMInvalidRequestError):
        await EmbeddingService().embed_text("Bình gas")


async def test_embed_batch_maps_timeout(mock_gemini_embed: AsyncMock) -> None:
    mock_gemini_embed.side_effect = _server_error(504, "deadline exceeded")

    with pytest.raises(LLMTimeoutError):
        await EmbeddingService().embed_batch(["Bình gas"])


async def test_embed_batch_maps_connection_error(mock_gemini_embed: AsyncMock) -> None:
    mock_gemini_embed.side_effect = _server_error(500, "backend unavailable")

    with pytest.raises(LLMConnectionError):
        await EmbeddingService().embed_batch(["Bình gas"])
