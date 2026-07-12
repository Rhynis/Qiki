"""Tests for Qiki bilingual (EN/VI) replies in the RAG pipeline."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.llm.prompts.templates import PromptTemplate
from app.llm.schemas import LLMResponse, LLMStreamChunk
from app.rag.context_builder import ContextBuilder
from app.rag.pipeline import RAGPipeline
from app.rag.safety import (
    SAFETY_EMERGENCY_RESPONSE_EN,
    SAFETY_EMERGENCY_RESPONSE_VI,
    SafetyChecker,
)
from app.rag.schemas import RetrievedDocument


class FakeRetriever:
    def __init__(self) -> None:
        self.retrieve = AsyncMock(
            return_value=[
                RetrievedDocument(
                    id=uuid4(),
                    title="Delivery",
                    content="We deliver in HCMC.",
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
                text="We deliver across HCMC.",
                latency_ms=100,
                model=self.model,
                provider=self.provider_name,
            )
        )

    async def stream(self, **kwargs: object) -> AsyncIterator[LLMStreamChunk]:
        del kwargs
        yield LLMStreamChunk(delta="Hello", accumulated_text="Hello")


class FakeObservability:
    def __init__(self) -> None:
        self.track_generation = AsyncMock()


class RecordingPromptLibrary:
    """Prompt library that records which template name was requested."""

    def __init__(self) -> None:
        self.requested: list[str] = []

    def get(self, name: str) -> PromptTemplate:
        self.requested.append(name)
        return PromptTemplate(
            f"[{name}] Date: ${{current_date}}\nContext: ${{context}}\n"
            "History: ${conversation_history}",
            name=name,
        )


def pipeline() -> tuple[RAGPipeline, FakeRetriever, FakeLLM, RecordingPromptLibrary]:
    retriever = FakeRetriever()
    llm = FakeLLM()
    prompts = RecordingPromptLibrary()
    rag = RAGPipeline(
        retriever=retriever,  # type: ignore[arg-type]
        llm_provider=llm,  # type: ignore[arg-type]
        safety_checker=SafetyChecker(),
        context_builder=ContextBuilder(),
        observability=FakeObservability(),  # type: ignore[arg-type]
        prompt_library=prompts,  # type: ignore[arg-type]
    )
    return rag, retriever, llm, prompts


@pytest.mark.asyncio
async def test_english_query_uses_english_prompt() -> None:
    rag, _, llm, prompts = pipeline()

    await rag.query("Do you deliver to Thu Duc today?", language="en")

    assert prompts.requested == ["system_chatbot_en"]
    system_prompt = llm.generate.await_args.kwargs["system_prompt"]
    assert system_prompt.startswith("[system_chatbot_en]")


@pytest.mark.asyncio
async def test_vietnamese_query_uses_vietnamese_prompt_by_default() -> None:
    rag, _, _, prompts = pipeline()

    await rag.query("Có giao hàng ở Thủ Đức không?")

    assert prompts.requested == ["system_chatbot_vi"]


@pytest.mark.asyncio
async def test_english_safety_query_returns_english_constant_without_llm() -> None:
    rag, retriever, llm, prompts = pipeline()

    response = await rag.query("I smell gas leaking in my kitchen", language="en")

    assert response.is_safety_critical is True
    assert response.answer == SAFETY_EMERGENCY_RESPONSE_EN
    assert "114" in response.answer
    assert "115" in response.answer
    assert "090 3026306" in response.answer
    retriever.retrieve.assert_not_called()
    llm.generate.assert_not_called()
    assert prompts.requested == []


@pytest.mark.asyncio
async def test_vietnamese_safety_query_returns_vietnamese_constant() -> None:
    rag, _, _, _ = pipeline()

    response = await rag.query("Tôi ngửi thấy mùi gas trong nhà")

    assert response.answer == SAFETY_EMERGENCY_RESPONSE_VI


@pytest.mark.parametrize(
    "text",
    [
        "I smell a gas leak",
        "there is leaking gas near the stove",
        "the cylinder is on fire",
        "I think it will explode",
        "I can't breathe, help",
    ],
)
@pytest.mark.asyncio
async def test_english_emergencies_are_detected(text: str) -> None:
    result = await SafetyChecker().check_query(text)

    assert result.is_emergency is True


def test_get_emergency_response_selects_language() -> None:
    checker = SafetyChecker()

    assert checker.get_emergency_response("en") == SAFETY_EMERGENCY_RESPONSE_EN
    assert checker.get_emergency_response("vi") == SAFETY_EMERGENCY_RESPONSE_VI
    assert checker.get_emergency_response() == SAFETY_EMERGENCY_RESPONSE_VI
