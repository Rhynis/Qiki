"""Tests for LLM provider factory behavior."""

from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_llm_provider, get_observability, get_prompt_library
from app.llm.factory import LLMProviderFactory
from app.llm.observability import LLMObservability
from app.llm.providers.fallback_provider import FallbackLLMProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.groq_provider import GroqProvider
from app.llm.providers.ollama_provider import OllamaProvider
from app.llm.providers.vllm_provider import VLLMProvider
from app.llm.schemas import LLMResponse


@pytest.fixture(autouse=True)
def reset_factory() -> object:
    LLMProviderFactory.reset()
    yield
    LLMProviderFactory.reset()


@pytest.fixture(autouse=True)
def mock_gemini(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.llm.genai_client.genai.Client", Mock())


def test_create_returns_ollama_provider() -> None:
    settings = Settings(LLM_PROVIDER="ollama", OLLAMA_BASE_URL="http://ollama.test")

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://ollama.test"


def test_create_returns_gemini_provider() -> None:
    # _env_file=None isolates from a developer's local .env (which may set GROQ/
    # GEMINI keys and change which provider the factory builds).
    settings = Settings(_env_file=None, LLM_PROVIDER="gemini", GEMINI_API_KEY="secret")

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, GeminiProvider)


def test_create_returns_groq_provider() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="groq",
        GROQ_API_KEY="groq-secret",
        GROQ_MODEL="llama-test",
        GEMINI_API_KEY=None,
        GEMINI_USE_VERTEX=False,
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, GroqProvider)
    assert provider.model == "llama-test"


def test_create_groq_primary_falls_back_to_gemini() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="groq",
        GROQ_API_KEY="groq-secret",
        GEMINI_API_KEY="gemini-secret",
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, FallbackLLMProvider)
    assert isinstance(provider.providers[0], GroqProvider)
    assert isinstance(provider.providers[1], GeminiProvider)


def test_groq_without_api_key_raises() -> None:
    settings = Settings(_env_file=None, LLM_PROVIDER="groq", GROQ_API_KEY=None)

    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        LLMProviderFactory.create(settings=settings)


def test_create_returns_fallback_provider_when_groq_key_configured() -> None:
    settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="secret",
        GROQ_API_KEY="groq-secret",
        GROQ_MODEL="llama-test",
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, FallbackLLMProvider)
    assert isinstance(provider.providers[0], GeminiProvider)
    assert isinstance(provider.providers[1], GroqProvider)
    assert provider.providers[1].model == "llama-test"


def test_create_returns_vllm_provider_standalone_without_fallback_configured() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="vllm",
        VLLM_BASE_URL="http://vllm.test/v1",
        VLLM_MODEL="qwen-awq-test",
        GROQ_API_KEY=None,
        GEMINI_API_KEY=None,
        GEMINI_USE_VERTEX=False,
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, VLLMProvider)
    assert provider.base_url == "http://vllm.test/v1"
    assert provider.model == "qwen-awq-test"


def test_create_vllm_primary_falls_back_to_groq_when_configured() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="vllm",
        GROQ_API_KEY="groq-secret",
        GEMINI_API_KEY=None,
        GEMINI_USE_VERTEX=False,
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, FallbackLLMProvider)
    assert isinstance(provider.providers[0], VLLMProvider)
    assert isinstance(provider.providers[1], GroqProvider)


def test_create_vllm_primary_falls_back_to_gemini_when_groq_not_configured() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="vllm",
        GROQ_API_KEY=None,
        GEMINI_API_KEY="gemini-secret",
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, FallbackLLMProvider)
    assert isinstance(provider.providers[0], VLLMProvider)
    assert isinstance(provider.providers[1], GeminiProvider)


def test_create_with_invalid_provider_raises() -> None:
    settings = Settings()

    with pytest.raises(ValueError, match="Unknown LLM provider"):
        LLMProviderFactory.create(provider_name="unknown", settings=settings)


def test_create_caches_instances() -> None:
    settings = Settings(LLM_PROVIDER="ollama")

    first = LLMProviderFactory.create(settings=settings)
    second = LLMProviderFactory.create(settings=settings)

    assert first is second


def test_reset_clears_cache() -> None:
    settings = Settings(LLM_PROVIDER="ollama")

    first = LLMProviderFactory.create(settings=settings)
    LLMProviderFactory.reset()
    second = LLMProviderFactory.create(settings=settings)

    assert first is not second


def test_gemini_without_api_key_raises() -> None:
    settings = Settings(
        _env_file=None, LLM_PROVIDER="gemini", GEMINI_API_KEY=None, GEMINI_USE_VERTEX=False
    )

    with pytest.raises(ValueError, match="GEMINI_API_KEY"):
        LLMProviderFactory.create(settings=settings)


def test_gemini_vertex_mode_does_not_require_api_key() -> None:
    settings = Settings(
        _env_file=None,
        LLM_PROVIDER="gemini",
        GEMINI_USE_VERTEX=True,
        GEMINI_API_KEY=None,
        GOOGLE_CLOUD_PROJECT="gasbot-prod",
    )

    provider = LLMProviderFactory.create(settings=settings)

    assert isinstance(provider, GeminiProvider)


@pytest.mark.asyncio
async def test_observability_gracefully_disables_without_keys() -> None:
    observability = LLMObservability()
    response = LLMResponse(
        text="ok",
        latency_ms=1,
        model="test",
        provider="ollama",
    )

    await observability.track_generation(
        provider="ollama",
        model="test",
        prompt="hello",
        system_prompt=None,
        response=response,
    )

    assert observability.enabled is False
    assert observability.create_trace("chat") is None


@pytest.mark.asyncio
async def test_observability_tracks_generation_and_flushes() -> None:
    langfuse = Mock()
    observability = LLMObservability(langfuse=langfuse)
    response = LLMResponse(
        text="Xin chào",
        prompt_tokens=3,
        completion_tokens=2,
        total_tokens=5,
        latency_ms=12,
        model="qwen-test",
        provider="ollama",
        finish_reason="stop",
        cost_usd=0.0,
    )

    await observability.track_generation(
        provider="ollama",
        model="qwen-test",
        prompt="Hello",
        system_prompt="System",
        response=response,
        metadata={"conversation_id": "c1"},
    )
    trace = observability.create_trace("chat", user_id="u1")
    await observability.flush()

    langfuse.generation.assert_called_once()
    langfuse.trace.assert_called_once_with(name="chat", user_id="u1")
    langfuse.flush.assert_called_once()
    assert trace is langfuse.trace.return_value


@pytest.mark.asyncio
async def test_observability_swallow_tracking_errors() -> None:
    langfuse = Mock()
    langfuse.generation.side_effect = RuntimeError("tracking down")
    observability = LLMObservability(langfuse=langfuse)
    response = LLMResponse(text="ok", latency_ms=1, model="test", provider="ollama")

    await observability.track_generation(
        provider="ollama",
        model="test",
        prompt="hello",
        system_prompt=None,
        response=response,
    )

    langfuse.generation.assert_called_once()


def test_get_llm_provider_dependency_returns_provider() -> None:
    LLMProviderFactory.reset()

    provider = get_llm_provider()

    assert isinstance(provider, BaseLLMProvider)


def test_get_observability_dependency_is_cached() -> None:
    get_observability.cache_clear()

    first = get_observability()
    second = get_observability()

    assert first is second


def test_get_prompt_library_loads_bundled_templates() -> None:
    get_prompt_library.cache_clear()

    library = get_prompt_library()

    assert "system_chatbot_vi" in library.list_templates()
    assert "context" in library.get("system_chatbot_vi").required_variables()
