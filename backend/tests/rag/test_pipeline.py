"""Tests for RAG pipeline orchestration."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.llm.exceptions import LLMQuotaExceededError
from app.llm.prompts.templates import PromptTemplate
from app.llm.schemas import LLMResponse, LLMStreamChunk
from app.rag.context_builder import ContextBuilder
from app.rag.pipeline import RAGPipeline
from app.rag.safety import SafetyChecker
from app.rag.schemas import RetrievedDocument


class FakeRetriever:
    def __init__(self) -> None:
        self.retrieve = AsyncMock(
            return_value=[
                RetrievedDocument(
                    id=uuid4(),
                    title="Giao hàng",
                    content="GasBot giao hàng trong nội thành TP.HCM.",
                    category="delivery",
                    similarity=0.85,
                    source_type="hybrid",
                )
            ]
        )


class FakeLLM:
    provider_name = "test"
    model = "test-model"

    def __init__(self) -> None:
        self.generate = AsyncMock(
            return_value=LLMResponse(
                text="GasBot có giao hàng trong nội thành TP.HCM.",
                latency_ms=100,
                model=self.model,
                provider=self.provider_name,
            )
        )

    async def stream(self, **kwargs: object) -> AsyncIterator[LLMStreamChunk]:
        del kwargs
        yield LLMStreamChunk(delta="Xin chào", accumulated_text="Xin chào")


class FakeObservability:
    def __init__(self) -> None:
        self.track_generation = AsyncMock()


class FakePromptLibrary:
    def get(self, name: str) -> PromptTemplate:
        assert name == "system_chatbot_vi"
        return PromptTemplate(
            "Date: ${current_date}\nContext: ${context}\nHistory: ${conversation_history}",
            name=name,
        )


def pipeline() -> tuple[RAGPipeline, FakeRetriever, FakeLLM, FakeObservability]:
    retriever = FakeRetriever()
    llm = FakeLLM()
    observability = FakeObservability()
    rag = RAGPipeline(
        retriever=retriever,  # type: ignore[arg-type]
        llm_provider=llm,  # type: ignore[arg-type]
        safety_checker=SafetyChecker(),
        context_builder=ContextBuilder(),
        observability=observability,  # type: ignore[arg-type]
        prompt_library=FakePromptLibrary(),  # type: ignore[arg-type]
    )
    return rag, retriever, llm, observability


@pytest.mark.asyncio
async def test_safety_query_returns_emergency_response_immediately() -> None:
    rag, _, _, _ = pipeline()

    response = await rag.query("Tôi ngửi thấy mùi gas trong nhà")

    assert response.is_safety_critical is True
    assert response.llm_response is None
    assert response.retrieval_count == 0
    assert "1900-1234" in response.answer
    assert response.confidence_score == 1.0


@pytest.mark.asyncio
async def test_safety_query_does_not_call_llm() -> None:
    rag, retriever, llm, observability = pipeline()

    await rag.query("Bình gas đang bốc lửa")

    retriever.retrieve.assert_not_called()
    llm.generate.assert_not_called()
    observability.track_generation.assert_not_called()


@pytest.mark.asyncio
async def test_normal_query_retrieves_and_generates() -> None:
    rag, retriever, llm, _ = pipeline()

    response = await rag.query("GasBot có giao hàng ở Quận 1 không?")

    assert response.is_safety_critical is False
    assert response.answer == "GasBot có giao hàng trong nội thành TP.HCM."
    assert response.retrieval_count == 1
    retriever.retrieve.assert_awaited_once()
    llm.generate.assert_awaited_once()


@pytest.mark.asyncio
async def test_query_tracks_observability() -> None:
    rag, _, _, observability = pipeline()

    await rag.query("GasBot có giao hàng ở Quận 1 không?", conversation_id=uuid4(), user_id=uuid4())

    observability.track_generation.assert_awaited_once()
    metadata = observability.track_generation.await_args.kwargs["metadata"]
    assert metadata["retrieved_doc_count"] == 1
    assert metadata["top_similarity"] == 0.85


@pytest.mark.asyncio
async def test_query_calculates_confidence_from_top_similarity() -> None:
    rag, _, _, _ = pipeline()

    response = await rag.query("Có giao hàng không?")

    assert response.confidence_score == 0.85


@pytest.mark.asyncio
async def test_query_includes_conversation_history() -> None:
    rag, _, llm, _ = pipeline()

    await rag.query(
        "Có giao hàng không?",
        conversation_history=[{"role": "user", "content": "Tôi ở Quận 1"}],
    )

    system_prompt = llm.generate.await_args.kwargs["system_prompt"]
    assert "Khách hàng: Tôi ở Quận 1" in system_prompt


@pytest.mark.asyncio
async def test_query_includes_current_date() -> None:
    rag, _, llm, _ = pipeline()

    await rag.query("Có giao hàng không?")

    system_prompt = llm.generate.await_args.kwargs["system_prompt"]
    assert f"Date: {RAGPipeline._current_date_vn()}" in system_prompt


@pytest.mark.asyncio
async def test_query_prepends_address_lookup_note() -> None:
    rag, _, llm, _ = pipeline()

    await rag.query("Tôi ở Phường Hiệp Bình Chánh có giao gas không?")

    system_prompt = llm.generate.await_args.kwargs["system_prompt"]
    assert "Phường Hiệp Bình Chánh thuộc khu vực giao Thủ Đức" in system_prompt


@pytest.mark.asyncio
async def test_query_includes_product_catalog_context() -> None:
    rag, _, llm, _ = pipeline()

    await rag.query(
        "Giá bình gas 12kg bao nhiêu?",
        product_context="Bảng giá sản phẩm hiện có:\n- Bình gas Petrolimex 12kg: 440.000đ",
    )

    system_prompt = llm.generate.await_args.kwargs["system_prompt"]
    assert "Thông tin sản phẩm đang bán" in system_prompt
    assert "Bình gas Petrolimex 12kg" in system_prompt
    assert "440.000đ" in system_prompt


@pytest.mark.asyncio
async def test_query_with_category_filter() -> None:
    rag, retriever, _, _ = pipeline()

    await rag.query("Có giao hàng không?", category_filter="delivery", top_k=3)

    retriever.retrieve.assert_awaited_once_with(
        query="Có giao hàng không?",
        top_k=3,
        category_filter="delivery",
    )


@pytest.mark.asyncio
async def test_retrieve_degrades_when_embedding_provider_fails() -> None:
    rag, retriever, _, _ = pipeline()
    retriever.retrieve.side_effect = LLMQuotaExceededError("Gemini quota exceeded")

    documents = await rag._retrieve("Có giao hàng không?", top_k=5, category_filter=None)

    assert documents == []


@pytest.mark.asyncio
async def test_query_still_generates_answer_when_retrieval_fails() -> None:
    rag, retriever, llm, observability = pipeline()
    retriever.retrieve.side_effect = LLMQuotaExceededError("Gemini quota exceeded")

    response = await rag.query("GasBot có giao hàng không?")

    assert response.answer == "GasBot có giao hàng trong nội thành TP.HCM."
    assert response.sources == []
    assert response.retrieval_count == 0
    assert response.confidence_score == 0.0
    llm.generate.assert_awaited_once()
    observability.track_generation.assert_awaited_once()


@pytest.mark.asyncio
async def test_stream_safety_query_yields_emergency_response() -> None:
    rag, _, llm, _ = pipeline()

    chunks = [chunk async for chunk in rag.query_stream("Có mùi gas nồng nặc")]

    assert chunks == [SafetyChecker().get_emergency_response()]
    llm.generate.assert_not_called()


def test_fake_types_are_runtime_compatible() -> None:
    _, retriever, llm, observability = pipeline()

    assert isinstance(retriever.retrieve, AsyncMock)
    assert isinstance(llm.generate, AsyncMock)
    assert isinstance(observability.track_generation, AsyncMock)
