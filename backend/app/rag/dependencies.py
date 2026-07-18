"""FastAPI dependencies for RAG components."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.redis import get_redis
from app.db.session import get_db
from app.llm.base import BaseLLMProvider
from app.llm.dependencies import get_llm_provider, get_observability, get_prompt_library
from app.llm.observability import LLMObservability
from app.llm.prompts.templates import PromptLibrary
from app.rag.bge_embeddings import BgeEmbeddingService
from app.rag.context_builder import ContextBuilder
from app.rag.embeddings import EmbeddingService
from app.rag.jina_embeddings import JinaEmbeddingService
from app.rag.ollama_embeddings import OllamaEmbeddingService
from app.rag.pipeline import RAGPipeline
from app.rag.reranker import LlmReranker
from app.rag.retriever import BaseRetriever, HybridRetriever, VectorRetriever
from app.rag.safety import SafetyChecker
from app.rag.text_processor import VietnameseTextProcessor
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.services.knowledge_base_service import KnowledgeBaseService


@lru_cache(maxsize=1)
def get_safety_checker() -> SafetyChecker:
    """Return cached safety checker."""
    return SafetyChecker()


@lru_cache(maxsize=1)
def get_context_builder() -> ContextBuilder:
    """Return cached context builder."""
    return ContextBuilder()


@lru_cache(maxsize=1)
def get_embedding_service() -> EmbeddingService:
    """Return cached embedding service singleton."""
    return EmbeddingService()


@lru_cache(maxsize=1)
def get_jina_embedding_service() -> JinaEmbeddingService:
    """Return cached Jina embedding fallback service."""
    return JinaEmbeddingService()


@lru_cache(maxsize=1)
def get_ollama_embedding_service() -> OllamaEmbeddingService:
    """Return cached local Ollama embedding service."""
    return OllamaEmbeddingService()


@lru_cache(maxsize=1)
def get_bge_embedding_service() -> BgeEmbeddingService:
    """Return cached local bge-m3 embedding service."""
    return BgeEmbeddingService()


def get_knowledge_base_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
    jina_embedding_service: Annotated[
        JinaEmbeddingService,
        Depends(get_jina_embedding_service),
    ],
    ollama_embedding_service: Annotated[
        OllamaEmbeddingService,
        Depends(get_ollama_embedding_service),
    ],
    bge_embedding_service: Annotated[
        BgeEmbeddingService,
        Depends(get_bge_embedding_service),
    ],
    redis: Annotated[Redis, Depends(get_redis)],
) -> KnowledgeBaseService:
    """Build a request-scoped knowledge base service."""
    return KnowledgeBaseService(
        KnowledgeBaseRepository(session),
        embedding_service,
        jina_embedding_service,
        VietnameseTextProcessor(),
        ollama_embedding_service,
        bge_embedding_service,
        redis_client=redis,
    )


def get_reranker(
    llm_provider: Annotated[BaseLLMProvider, Depends(get_llm_provider)],
    prompt_library: Annotated[PromptLibrary, Depends(get_prompt_library)],
) -> LlmReranker:
    """Build the offline LLM reranker (used only when RAG_RERANK_ENABLED)."""
    return LlmReranker(llm_provider, prompt_library)


def get_vector_retriever(
    kb_service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> VectorRetriever:
    """Build a vector retriever."""
    return VectorRetriever(kb_service, embedding_service)


def get_hybrid_retriever(
    kb_service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    embedding_service: Annotated[EmbeddingService, Depends(get_embedding_service)],
) -> HybridRetriever:
    """Build a hybrid retriever."""
    return HybridRetriever(kb_service, embedding_service)


def get_default_retriever(
    retriever: Annotated[HybridRetriever, Depends(get_hybrid_retriever)],
) -> BaseRetriever:
    """Return the default RAG retriever."""
    return retriever


def get_rag_pipeline(
    retriever: Annotated[BaseRetriever, Depends(get_default_retriever)],
    llm_provider: Annotated[BaseLLMProvider, Depends(get_llm_provider)],
    safety_checker: Annotated[SafetyChecker, Depends(get_safety_checker)],
    context_builder: Annotated[ContextBuilder, Depends(get_context_builder)],
    observability: Annotated[LLMObservability, Depends(get_observability)],
    prompt_library: Annotated[PromptLibrary, Depends(get_prompt_library)],
    reranker: Annotated[LlmReranker, Depends(get_reranker)],
) -> RAGPipeline:
    """Build the request-scoped RAG pipeline."""
    return RAGPipeline(
        retriever=retriever,
        llm_provider=llm_provider,
        safety_checker=safety_checker,
        context_builder=context_builder,
        observability=observability,
        prompt_library=prompt_library,
        reranker=reranker,
    )
