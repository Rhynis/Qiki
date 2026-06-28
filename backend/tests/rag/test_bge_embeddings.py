"""Tests for the local bge-m3 embedding service."""

from typing import Any, ClassVar

import httpx
import pytest

from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMTimeoutError,
)
from app.rag.bge_embeddings import BgeEmbeddingService

pytestmark = pytest.mark.asyncio


class FakeAsyncClient:
    requests: ClassVar[list[dict[str, Any]]] = []
    response: ClassVar[httpx.Response | Exception]

    def __init__(self, *, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self) -> "FakeAsyncClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        del args

    async def post(self, url: str, *, json: dict[str, Any]) -> httpx.Response:
        self.requests.append({"url": url, "json": json})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture(autouse=True)
def mock_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    BgeEmbeddingService.reset()
    FakeAsyncClient.requests = []
    FakeAsyncClient.response = _response(200, {"embedding": [0.25] * 1024})
    monkeypatch.setattr("app.rag.bge_embeddings.httpx.AsyncClient", FakeAsyncClient)
    yield
    BgeEmbeddingService.reset()


def _response(status_code: int, payload: dict[str, Any] | None = None) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost:11434/api/embeddings")
    return httpx.Response(status_code, json=payload or {}, request=request)


async def test_embed_text_returns_1024_dims_and_posts_bge_model() -> None:
    embedding = await BgeEmbeddingService().embed_text("Rò rỉ gas")

    assert len(embedding) == 1024
    request = FakeAsyncClient.requests[0]
    assert request["url"].endswith("/api/embeddings")
    assert request["json"]["prompt"] == "Rò rỉ gas"
    assert request["json"]["model"] == "bge-m3"


async def test_embed_batch_sends_one_request_per_text() -> None:
    embeddings = await BgeEmbeddingService().embed_batch(["Đổi bình gas", "Kiểm tra dây dẫn"])

    assert [len(embedding) for embedding in embeddings] == [1024, 1024]
    assert len(FakeAsyncClient.requests) == 2


async def test_embed_text_empty_returns_zero_vector_without_request() -> None:
    embedding = await BgeEmbeddingService().embed_text("   ")

    assert embedding == [0.0] * 1024
    assert FakeAsyncClient.requests == []


async def test_embed_text_raises_on_dimension_mismatch() -> None:
    FakeAsyncClient.response = _response(200, {"embedding": [0.1] * 768})

    with pytest.raises(LLMInvalidRequestError):
        await BgeEmbeddingService().embed_text("Bình gas")


async def test_embed_text_raises_when_embedding_missing() -> None:
    FakeAsyncClient.response = _response(200, {"unexpected": True})

    with pytest.raises(LLMInvalidRequestError):
        await BgeEmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_http_status_error() -> None:
    FakeAsyncClient.response = _response(500, {"error": "model not found"})

    with pytest.raises(LLMInvalidRequestError):
        await BgeEmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_connection_error() -> None:
    FakeAsyncClient.response = httpx.ConnectError("connection refused")

    with pytest.raises(LLMConnectionError):
        await BgeEmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_timeout() -> None:
    FakeAsyncClient.response = httpx.TimeoutException("deadline exceeded")

    with pytest.raises(LLMTimeoutError):
        await BgeEmbeddingService().embed_text("Bình gas")
