"""Tests for the Jina embedding fallback service."""

from typing import Any, ClassVar

import httpx
import pytest

from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.rag.jina_embeddings import JinaEmbeddingService

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

    async def post(
        self,
        url: str,
        *,
        headers: dict[str, str],
        json: dict[str, Any],
    ) -> httpx.Response:
        self.requests.append({"url": url, "headers": headers, "json": json})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@pytest.fixture(autouse=True)
def mock_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    JinaEmbeddingService.reset()
    FakeAsyncClient.requests = []
    FakeAsyncClient.response = _response(
        200,
        {"data": [{"embedding": [0.25] * 768}, {"embedding": [0.5] * 768}]},
    )
    monkeypatch.setattr("app.rag.jina_embeddings.httpx.AsyncClient", FakeAsyncClient)
    yield
    JinaEmbeddingService.reset()


def _response(status_code: int, payload: dict[str, Any] | None = None) -> httpx.Response:
    request = httpx.Request("POST", "https://api.jina.ai/v1/embeddings")
    return httpx.Response(status_code, json=payload or {}, request=request)


async def test_embed_text_sends_query_task_and_returns_768_dims() -> None:
    embedding = await JinaEmbeddingService().embed_text("Rò rỉ gas", task="retrieval.query")

    assert len(embedding) == 768
    payload = FakeAsyncClient.requests[0]["json"]
    assert payload["task"] == "retrieval.query"
    assert payload["dimensions"] == 768
    assert payload["input"] == ["Rò rỉ gas"]


async def test_embed_batch_sends_passage_task() -> None:
    embeddings = await JinaEmbeddingService().embed_batch(
        ["Đổi bình gas", "Kiểm tra dây dẫn"],
        task="retrieval.passage",
    )

    assert [len(embedding) for embedding in embeddings] == [768, 768]
    assert FakeAsyncClient.requests[0]["json"]["task"] == "retrieval.passage"


async def test_embed_text_maps_quota_error() -> None:
    FakeAsyncClient.response = _response(429, {"error": "quota exceeded"})

    with pytest.raises(LLMQuotaExceededError):
        await JinaEmbeddingService().embed_text("Bình gas", task="retrieval.query")


async def test_embed_text_maps_rate_limit_error() -> None:
    FakeAsyncClient.response = _response(429, {"error": "too many requests"})

    with pytest.raises(LLMRateLimitError):
        await JinaEmbeddingService().embed_text("Bình gas", task="retrieval.query")


async def test_embed_batch_maps_invalid_request() -> None:
    FakeAsyncClient.response = _response(400, {"error": "bad request"})

    with pytest.raises(LLMInvalidRequestError):
        await JinaEmbeddingService().embed_batch(["Bình gas"], task="retrieval.passage")


async def test_embed_batch_maps_http_timeout_status() -> None:
    FakeAsyncClient.response = _response(504, {"error": "deadline exceeded"})

    with pytest.raises(LLMTimeoutError):
        await JinaEmbeddingService().embed_batch(["Bình gas"], task="retrieval.passage")


async def test_embed_text_maps_other_status_to_connection_error() -> None:
    FakeAsyncClient.response = _response(500, {"error": "server unavailable"})

    with pytest.raises(LLMConnectionError):
        await JinaEmbeddingService().embed_text("Bình gas", task="retrieval.query")
