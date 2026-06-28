"""Tests for the offline LLM reranker (success + mandatory fallback)."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest

import app.llm.prompts as prompts_pkg
from app.llm.exceptions import LLMTimeoutError
from app.llm.prompts.templates import PromptLibrary
from app.rag.reranker import LlmReranker
from app.rag.schemas import RetrievedDocument

pytestmark = pytest.mark.asyncio


class _Response:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeLLMProvider:
    """LLM provider stub that returns a fixed text (or raises) on generate."""

    provider_name = "fake"
    model = "fake-model"

    def __init__(self, text: str = "[]", error: Exception | None = None) -> None:
        self._text = text
        self._error = error
        self.generate_calls = 0

    async def generate(self, *args: object, **kwargs: object) -> _Response:
        del args, kwargs
        self.generate_calls += 1
        if self._error is not None:
            raise self._error
        return _Response(self._text)

    def stream(self, *args: object, **kwargs: object) -> AsyncIterator[object]:  # pragma: no cover
        raise NotImplementedError

    async def health_check(self) -> bool:  # pragma: no cover
        return True


def _prompt_library() -> PromptLibrary:
    library = PromptLibrary()
    library.load_from_directory(Path(prompts_pkg.__file__).parent / "templates")
    return library


def _docs(count: int) -> list[RetrievedDocument]:
    return [
        RetrievedDocument(
            id=uuid4(),
            title=f"Doc {index}",
            content=f"content {index}",
            category="faq",
            similarity=1.0 - index * 0.1,
            source_type="vector",
        )
        for index in range(count)
    ]


async def test_rerank_reorders_by_llm_indices() -> None:
    provider = FakeLLMProvider(text="[2, 0, 1]")
    reranker = LlmReranker(provider, _prompt_library())
    docs = _docs(3)

    result = await reranker.rerank("rò rỉ gas", docs, top_n=3)

    assert [doc.title for doc in result] == ["Doc 2", "Doc 0", "Doc 1"]


async def test_rerank_drops_irrelevant_and_limits_top_n() -> None:
    provider = FakeLLMProvider(text="here is the answer: [1, 0]")
    reranker = LlmReranker(provider, _prompt_library())
    docs = _docs(3)

    result = await reranker.rerank("rò rỉ gas", docs, top_n=1)

    assert [doc.title for doc in result] == ["Doc 1"]


async def test_rerank_empty_array_returns_nothing() -> None:
    provider = FakeLLMProvider(text="[]")
    reranker = LlmReranker(provider, _prompt_library())

    result = await reranker.rerank("không có tài liệu", _docs(3), top_n=3)

    assert result == []


async def test_rerank_falls_back_to_vector_order_on_llm_error() -> None:
    provider = FakeLLMProvider(error=LLMTimeoutError("ollama timed out"))
    reranker = LlmReranker(provider, _prompt_library())
    docs = _docs(3)

    result = await reranker.rerank("rò rỉ gas", docs, top_n=2)

    # Original vector order preserved, never raises.
    assert [doc.title for doc in result] == ["Doc 0", "Doc 1"]


async def test_rerank_falls_back_when_response_unparseable() -> None:
    provider = FakeLLMProvider(text="I think all of them are relevant, sorry.")
    reranker = LlmReranker(provider, _prompt_library())
    docs = _docs(3)

    result = await reranker.rerank("rò rỉ gas", docs, top_n=3)

    assert [doc.title for doc in result] == ["Doc 0", "Doc 1", "Doc 2"]


async def test_rerank_falls_back_when_indices_all_invalid() -> None:
    provider = FakeLLMProvider(text="[9, 8, 7]")
    reranker = LlmReranker(provider, _prompt_library())
    docs = _docs(3)

    result = await reranker.rerank("rò rỉ gas", docs, top_n=3)

    assert [doc.title for doc in result] == ["Doc 0", "Doc 1", "Doc 2"]


async def test_rerank_single_candidate_skips_llm() -> None:
    provider = FakeLLMProvider(text="[0]")
    reranker = LlmReranker(provider, _prompt_library())
    docs = _docs(1)

    result = await reranker.rerank("rò rỉ gas", docs, top_n=3)

    assert [doc.title for doc in result] == ["Doc 0"]
    assert provider.generate_calls == 0
