"""Integration test: the streaming endpoint persists the reply to the DB."""

from collections.abc import AsyncIterator, Iterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_user_optional
from app.api.v1.endpoints.conversations import get_intent_classifier
from app.intent.base import BaseIntentClassifier
from app.intent.categories import IntentCategory
from app.intent.schemas import IntentResult
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_llm_provider
from app.llm.schemas import EmbeddingResponse, LLMResponse, LLMStreamChunk
from app.main import app
from app.rag.dependencies import get_rag_pipeline

pytestmark = pytest.mark.asyncio


class GeneralInfoClassifier(BaseIntentClassifier):
    """Force the open-ended RAG branch so the answer streams."""

    async def classify(self, text: str, conversation_history: object = None) -> IntentResult:
        del text, conversation_history
        return IntentResult(
            category=IntentCategory.GENERAL_INFO,
            confidence=0.9,
            reasoning="test",
            classifier="test",
        )


class UnusedLLMProvider(BaseLLMProvider):
    """The streaming path uses the (faked) pipeline, never this provider directly."""

    def __init__(self) -> None:
        super().__init__(model="unused")

    @property
    def provider_name(self) -> str:
        return "unused"

    async def generate(self, *args: object, **kwargs: object) -> LLMResponse:
        raise AssertionError("generate must not be called")

    async def stream(self, *args: object, **kwargs: object) -> AsyncIterator[LLMStreamChunk]:
        raise AssertionError("stream must not be called")
        yield LLMStreamChunk(delta="", accumulated_text="")  # pragma: no cover

    async def embed(self, text: str) -> EmbeddingResponse:
        raise NotImplementedError

    async def health_check(self) -> bool:
        return True


class StreamingRAGPipeline:
    """Fake pipeline that streams tokens and reports the serving provider/usage."""

    async def query_stream(
        self,
        query: str,
        sources_sink: list[object] | None = None,
        generation_sink: dict[str, object] | None = None,
        **kwargs: object,
    ) -> AsyncIterator[str]:
        del query, sources_sink, kwargs
        for token in ("Hello ", "from ", "streaming ", "RAG"):
            yield token
        if generation_sink is not None:
            generation_sink["provider"] = "groq"
            generation_sink["model"] = "llama-3.3-70b-versatile"
            generation_sink["total_tokens"] = 55

    async def query(self, *args: object, **kwargs: object) -> object:
        raise AssertionError("the streaming path must not call the blocking query()")


@pytest.fixture(autouse=True)
def stream_overrides() -> Iterator[None]:
    app.dependency_overrides[get_current_user_optional] = lambda: None
    app.dependency_overrides[get_intent_classifier] = lambda: GeneralInfoClassifier()
    app.dependency_overrides[get_llm_provider] = lambda: UnusedLLMProvider()
    app.dependency_overrides[get_rag_pipeline] = lambda: StreamingRAGPipeline()
    yield
    app.dependency_overrides.clear()


async def test_stream_endpoint_persists_reply_with_actual_provider(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    # The order_session fixture already provisions a clean schema; the assertions
    # below scope to this conversation's own id, so no destructive truncate (which
    # would hold a table lock and block the endpoint's own session) is needed.
    del order_session

    started = await test_client.post(
        "/api/v1/conversations/start",
        json={"session_id": "stream-persist"},
    )
    assert started.status_code == 200
    conversation_id = started.json()["id"]

    # httpx buffers the whole SSE body from the real StreamingResponse endpoint.
    streamed = await test_client.post(
        f"/api/v1/conversations/{conversation_id}/messages/stream",
        json={"content": "What are your opening hours?"},
    )
    assert streamed.status_code == 200
    assert "event: delta" in streamed.text
    assert "event: done" in streamed.text

    # The streamed reply is persisted to the DB and readable via the messages API,
    # attributed to the provider that actually served (not the "fallback" wrapper).
    listing = await test_client.get(f"/api/v1/conversations/{conversation_id}/messages")
    assert listing.status_code == 200
    assistant = [item for item in listing.json()["items"] if item["role"] == "assistant"]
    saved = next(item for item in assistant if item["content"] == "Hello from streaming RAG")
    assert saved["llm_provider"] == "groq"
    assert saved["llm_model"] == "llama-3.3-70b-versatile"
    assert saved["tokens_used"] == 55
