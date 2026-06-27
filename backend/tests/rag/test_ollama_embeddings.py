"""Tests for the local Ollama embedding service."""

from typing import Any, ClassVar

import httpx
import pytest

from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMTimeoutError,
)
from app.rag.ollama_embeddings import OllamaEmbeddingService

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
    OllamaEmbeddingService.reset()
    FakeAsyncClient.requests = []
    FakeAsyncClient.response = _response(200, {"embedding": [0.25] * 768})
    monkeypatch.setattr("app.rag.ollama_embeddings.httpx.AsyncClient", FakeAsyncClient)
    yield
    OllamaEmbeddingService.reset()


def _response(status_code: int, payload: dict[str, Any] | None = None) -> httpx.Response:
    request = httpx.Request("POST", "http://localhost:11434/api/embeddings")
    return httpx.Response(status_code, json=payload or {}, request=request)


async def test_embed_text_returns_768_dims_and_posts_model_prompt() -> None:
    embedding = await OllamaEmbeddingService().embed_text("Rò rỉ gas")

    assert len(embedding) == 768
    request = FakeAsyncClient.requests[0]
    assert request["url"].endswith("/api/embeddings")
    assert request["json"]["prompt"] == "Rò rỉ gas"
    assert request["json"]["model"] == "nomic-embed-text"


async def test_embed_batch_sends_one_request_per_text() -> None:
    embeddings = await OllamaEmbeddingService().embed_batch(["Đổi bình gas", "Kiểm tra dây dẫn"])

    assert [len(embedding) for embedding in embeddings] == [768, 768]
    assert len(FakeAsyncClient.requests) == 2


async def test_embed_text_empty_returns_zero_vector_without_request() -> None:
    embedding = await OllamaEmbeddingService().embed_text("   ")

    assert embedding == [0.0] * 768
    assert FakeAsyncClient.requests == []


async def test_embed_text_raises_on_dimension_mismatch() -> None:
    FakeAsyncClient.response = _response(200, {"embedding": [0.1] * 512})

    with pytest.raises(LLMInvalidRequestError):
        await OllamaEmbeddingService().embed_text("Bình gas")


async def test_embed_text_raises_when_embedding_missing() -> None:
    FakeAsyncClient.response = _response(200, {"unexpected": True})

    with pytest.raises(LLMInvalidRequestError):
        await OllamaEmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_http_status_error() -> None:
    FakeAsyncClient.response = _response(500, {"error": "model not found"})

    with pytest.raises(LLMInvalidRequestError):
        await OllamaEmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_connection_error() -> None:
    FakeAsyncClient.response = httpx.ConnectError("connection refused")

    with pytest.raises(LLMConnectionError):
        await OllamaEmbeddingService().embed_text("Bình gas")


async def test_embed_text_maps_timeout() -> None:
    FakeAsyncClient.response = httpx.TimeoutException("deadline exceeded")

    with pytest.raises(LLMTimeoutError):
        await OllamaEmbeddingService().embed_text("Bình gas")
