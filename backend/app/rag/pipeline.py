"""Main RAG pipeline orchestrating safety, retrieval, and generation."""

import time
from collections.abc import AsyncIterator, Mapping, Sequence
from uuid import UUID

from sqlalchemy.exc import SQLAlchemyError

from app.core.logging import get_logger
from app.llm.base import BaseLLMProvider
from app.llm.exceptions import LLMProviderError
from app.llm.observability import LLMObservability
from app.llm.prompts.templates import PromptLibrary
from app.rag.context_builder import ContextBuilder
from app.rag.retriever import BaseRetriever
from app.rag.safety import SafetyChecker
from app.rag.schemas import RAGResponse, RetrievedDocument


class RAGPipeline:
    """End-to-end RAG pipeline with safety check first."""

    def __init__(
        self,
        retriever: BaseRetriever,
        llm_provider: BaseLLMProvider,
        safety_checker: SafetyChecker,
        context_builder: ContextBuilder,
        observability: LLMObservability,
        prompt_library: PromptLibrary,
    ) -> None:
        self.retriever = retriever
        self.llm_provider = llm_provider
        self.safety_checker = safety_checker
        self.context_builder = context_builder
        self.observability = observability
        self.prompts = prompt_library
        self.logger = get_logger(__name__)

    async def query(
        self,
        query: str,
        conversation_history: Sequence[Mapping[str, str]] | None = None,
        category_filter: str | None = None,
        top_k: int = 5,
        conversation_id: UUID | None = None,
        user_id: UUID | None = None,
        product_context: str | None = None,
    ) -> RAGResponse:
        """Execute safety check, retrieval, context construction, and generation."""
        start_time = time.monotonic()
        safety = await self.safety_checker.check_query(query)
        if safety.is_emergency:
            total_latency_ms = int((time.monotonic() - start_time) * 1000)
            self.logger.warning(
                "rag_emergency_response",
                query=query[:100],
                latency_ms=total_latency_ms,
            )
            return RAGResponse(
                answer=self.safety_checker.get_emergency_response(),
                sources=[],
                query=query,
                processed_query=query,
                llm_response=None,
                retrieval_count=0,
                is_safety_critical=True,
                safety_result=safety,
                confidence_score=1.0,
                total_latency_ms=total_latency_ms,
            )

        documents = await self._retrieve(query, top_k, category_filter)
        context = self.context_builder.build_context(
            documents,
            product_context=product_context,
        )
        history = self.context_builder.format_conversation_history(conversation_history or [])
        system_prompt = self.prompts.get("system_chatbot_vi").render(
            context=context,
            conversation_history=history,
        )
        llm_response = await self.llm_provider.generate(
            prompt=query,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2048,
        )
        await self.observability.track_generation(
            provider=self.llm_provider.provider_name,
            model=self.llm_provider.model,
            prompt=query,
            system_prompt=system_prompt,
            response=llm_response,
            metadata={
                "conversation_id": str(conversation_id) if conversation_id else None,
                "user_id": str(user_id) if user_id else None,
                "retrieved_doc_count": len(documents),
                "top_similarity": documents[0].similarity if documents else 0.0,
                "category_filter": category_filter,
                "has_product_context": bool(product_context),
            },
        )

        total_latency_ms = int((time.monotonic() - start_time) * 1000)
        confidence = documents[0].similarity if documents else 0.0
        self.logger.info(
            "rag_response_generated",
            latency_ms=total_latency_ms,
            doc_count=len(documents),
            confidence=confidence,
        )
        return RAGResponse(
            answer=llm_response.text,
            sources=documents,
            query=query,
            processed_query=query,
            llm_response=llm_response,
            retrieval_count=len(documents),
            is_safety_critical=False,
            safety_result=safety,
            confidence_score=confidence,
            total_latency_ms=total_latency_ms,
        )

    async def query_stream(
        self,
        query: str,
        conversation_history: Sequence[Mapping[str, str]] | None = None,
        category_filter: str | None = None,
        top_k: int = 5,
        product_context: str | None = None,
    ) -> AsyncIterator[str]:
        """Stream an answer while keeping the same safety-first behavior."""
        safety = await self.safety_checker.check_query(query)
        if safety.is_emergency:
            yield self.safety_checker.get_emergency_response()
            return

        documents = await self._retrieve(query, top_k, category_filter)
        context = self.context_builder.build_context(
            documents,
            product_context=product_context,
        )
        history = self.context_builder.format_conversation_history(conversation_history or [])
        system_prompt = self.prompts.get("system_chatbot_vi").render(
            context=context,
            conversation_history=history,
        )
        async for chunk in self.llm_provider.stream(
            prompt=query,
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=2048,
        ):
            yield chunk.delta

    async def _retrieve(
        self,
        query: str,
        top_k: int,
        category_filter: str | None,
    ) -> list[RetrievedDocument]:
        try:
            documents = await self.retriever.retrieve(
                query=query,
                top_k=top_k,
                category_filter=category_filter,
            )
        except (LLMProviderError, RuntimeError, ValueError, TypeError, SQLAlchemyError) as exc:
            self.logger.error("rag_retrieval_failed", error=str(exc))
            return []
        return documents
