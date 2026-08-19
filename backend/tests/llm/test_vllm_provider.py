"""Tests for the self-hosted vLLM LLM provider."""

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
from app.llm.providers.vllm_provider import VLLMProvider

pytestmark = pytest.mark.asyncio

BASE_URL = "http://vllm.test/v1"


def provider(api_key: str | None = None) -> VLLMProvider:
    return VLLMProvider(base_url=BASE_URL, model="qwen-awq-test", api_key=api_key, timeout=1)


async def test_generate_returns_response(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
        json={
            "model": "qwen-awq-test",
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

    response = await provider(api_key="secret").generate("Hello", system_prompt="Bạn là trợ lý")
    request = httpx_mock.get_requests()[0]

    assert request.headers["Authorization"] == "Bearer secret"
    assert response.text == "Xin chào"
    assert response.prompt_tokens == 12
    assert response.completion_tokens == 8
    assert response.total_tokens == 20
    assert response.model == "qwen-awq-test"
    assert response.provider == "vllm"
    assert response.finish_reason == "stop"
    assert response.cost_usd == 0.0


async def test_generate_omits_auth_header_without_api_key(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
        json={"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}]},
    )

    await provider(api_key=None).generate("Hello")
    request = httpx_mock.get_requests()[0]

    assert "Authorization" not in request.headers


async def test_stream_yields_openai_compatible_sse_chunks(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
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
    assert chunks[-1].provider == "vllm"


async def test_generate_maps_invalid_request(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
        status_code=400,
        text="bad prompt",
    )

    with pytest.raises(LLMInvalidRequestError):
        await provider().generate("Hello")


async def test_generate_maps_server_error_to_connection_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
        status_code=503,
        text="engine overloaded",
    )

    with pytest.raises(LLMConnectionError):
        await provider().generate("Hello")


async def test_generate_maps_rate_limit_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
        status_code=429,
        text="too many requests",
    )

    with pytest.raises(LLMRateLimitError):
        await provider().generate("Hello")


async def test_generate_maps_quota_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        method="POST",
        url=f"{BASE_URL}/chat/completions",
        status_code=429,
        text="quota exceeded",
    )

    with pytest.raises(LLMQuotaExceededError):
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


async def test_health_check_hits_models_endpoint(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(method="GET", url=f"{BASE_URL}/models", json={"data": []})

    assert await provider().health_check() is True

    request = httpx_mock.get_requests()[0]
    assert request.method == "GET"
    assert str(request.url) == f"{BASE_URL}/models"


async def test_health_check_returns_false_when_down(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("offline"))

    assert await provider().health_check() is False
