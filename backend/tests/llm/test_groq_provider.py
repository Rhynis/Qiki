"""Tests for the Groq LLM provider."""

import httpx
import pytest
from pytest_httpx import HTTPXMock, IteratorStream

from app.llm.exceptions import (
    LLMConnectionError,
    LLMInvalidRequestError,
    LLMQuotaExceededError,
    LLMRateLimitError,
    LLMTimeoutError,
)
from app.llm.providers.groq_provider import GroqProvider

pytestmark = pytest.mark.asyncio


def provider() -> GroqProvider:
    return GroqProvider(api_key="test-key", model="llama-test", timeout=1)


async def test_generate_returns_response(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        json={
            "model": "llama-test",
            "choices": [
                {
                    "message": {"content": "Xin chào"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 12,
                "completion_tokens": 8,
                "total_tokens": 20,
            },
        },
    )

    response = await provider().generate("Hello", system_prompt="Bạn là trợ lý")
    request = httpx_mock.get_requests()[0]

    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.read()
    assert response.text == "Xin chào"
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 8
    assert response.total_tokens == 20
    assert response.model == "llama-test"
    assert response.provider == "groq"
    assert response.finish_reason == "stop"
    assert response.cost_usd == 0.0


async def test_stream_yields_openai_compatible_sse_chunks(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        stream=IteratorStream(
            [
                b'data: {"choices":[{"delta":{"content":"Xin"},"finish_reason":null}]}\n\n',
                b'data: {"choices":[{"delta":{"content":" chao"},"finish_reason":null}]}\n\n',
                b'data: {"choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
                b"data: [DONE]\n\n",
            ]
        ),
    )

    chunks = [chunk async for chunk in provider().stream("Hello")]

    assert [chunk.delta for chunk in chunks] == ["Xin", " chao", ""]
    assert chunks[-1].finish_reason == "stop"
    assert chunks[-1].accumulated_text == "Xin chao"


async def test_generate_maps_quota_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        status_code=429,
        text="quota exceeded",
    )

    with pytest.raises(LLMQuotaExceededError):
        await provider().generate("Hello")


async def test_generate_maps_rate_limit_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        status_code=429,
        text="too many requests",
    )

    with pytest.raises(LLMRateLimitError):
        await provider().generate("Hello")


async def test_generate_maps_invalid_request(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        status_code=400,
        text="bad prompt",
    )

    with pytest.raises(LLMInvalidRequestError):
        await provider().generate("Hello")


async def test_generate_maps_timeout(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.TimeoutException("slow"))

    with pytest.raises(LLMTimeoutError):
        await provider().generate("Hello")


async def test_generate_maps_connection_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("offline"))

    with pytest.raises(LLMConnectionError):
        await provider().generate("Hello")


async def test_embed_is_not_supported() -> None:
    with pytest.raises(NotImplementedError):
        await provider().embed("gas")


async def test_health_check_returns_true_when_generate_succeeds(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        json={"choices": [{"message": {"content": "ok"}}]},
    )

    assert await provider().health_check() is True


async def test_health_check_returns_false_when_down(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("offline"))

    assert await provider().health_check() is False


async def test_stream_surfaces_usage_tokens_and_provider(httpx_mock: HTTPXMock) -> None:
    # With stream_options.include_usage, Groq emits a final usage frame; the chunk
    # must surface total_tokens plus the serving provider/model for analytics.
    httpx_mock.add_response(
        method="POST",
        url="https://api.groq.com/openai/v1/chat/completions",
        stream=IteratorStream(
            [
                b'data: {"model":"llama-test","choices":[{"delta":{"content":"Hi"},'
                b'"finish_reason":null}]}\n\n',
                b'data: {"model":"llama-test","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n',
                b'data: {"model":"llama-test","choices":[],"usage":{"total_tokens":33}}\n\n',
                b"data: [DONE]\n\n",
            ]
        ),
    )

    chunks = [chunk async for chunk in provider().stream("Hello")]

    assert "".join(chunk.delta for chunk in chunks) == "Hi"
    assert chunks[-1].total_tokens == 33
    assert chunks[-1].provider == "groq"
    assert chunks[-1].model == "llama-test"
