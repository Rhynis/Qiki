"""Offline LLM reranker for RAG candidates (local Ollama model)."""

import json
import re

from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider
from app.llm.prompts.templates import PromptLibrary
from app.rag.schemas import RetrievedDocument

_JSON_ARRAY = re.compile(r"\[[^\]]*\]")
_CONTENT_SNIPPET = 240


class LlmReranker:
    """Listwise rerank retrieved documents with the local Ollama LLM.

    The model receives the query and the numbered candidates and returns a JSON
    array of indices ordered by relevance (dropping irrelevant ones). Any failure
    (timeout, HTTP error, JSON parse error, invalid indices) falls back to the
    original vector ranking and never raises, so the pipeline cannot 500 on rerank.
    """

    def __init__(self, llm_provider: BaseLLMProvider, prompt_library: PromptLibrary) -> None:
        self.llm_provider = llm_provider
        self.prompts = prompt_library
        self.logger = get_logger(__name__)

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedDocument],
        top_n: int,
    ) -> list[RetrievedDocument]:
        """Reorder candidates by LLM-judged relevance, keeping at most top_n."""
        if len(candidates) <= 1:
            return candidates[:top_n]
        try:
            order = await self._rank_indices(query, candidates)
        except Exception as exc:  # noqa: BLE001 - rerank must never raise (no prod 500)
            self.logger.warning("rerank_failed_using_vector_order", error=str(exc))
            return candidates[:top_n]
        if not order:
            # A valid empty array means the model judged nothing relevant.
            return []
        reranked = [candidates[index] for index in order]
        return reranked[:top_n]

    async def _rank_indices(
        self,
        query: str,
        candidates: list[RetrievedDocument],
    ) -> list[int]:
        prompt = self.prompts.get("rerank_vi").render(
            query=query,
            candidates=self._format_candidates(candidates),
        )
        response = await self.llm_provider.generate(
            prompt=prompt,
            temperature=0.0,
            max_tokens=128,
        )
        return self._parse_order(response.text, len(candidates))

    @staticmethod
    def _format_candidates(candidates: list[RetrievedDocument]) -> str:
        lines: list[str] = []
        for index, doc in enumerate(candidates):
            snippet = " ".join(doc.content.split())[:_CONTENT_SNIPPET]
            lines.append(f"{index}. {doc.title}: {snippet}")
        return "\n".join(lines)

    @staticmethod
    def _parse_order(text: str, count: int) -> list[int]:
        match = _JSON_ARRAY.search(text)
        if not match:
            raise ValueError("no JSON array in rerank response")
        parsed = json.loads(match.group(0))
        if not isinstance(parsed, list):
            raise ValueError("rerank response is not a JSON array")
        if not parsed:
            return []
        seen: set[int] = set()
        order: list[int] = []
        for value in parsed:
            index = int(value)
            if 0 <= index < count and index not in seen:
                seen.add(index)
                order.append(index)
        if not order:
            raise ValueError("rerank response had no valid indices")
        return order
