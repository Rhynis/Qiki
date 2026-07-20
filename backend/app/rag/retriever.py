"""Document retrievers for RAG."""

from abc import ABC, abstractmethod

from app.rag.embeddings import EmbeddingService
from app.rag.schemas import RetrievedDocument
from app.services.knowledge_base_service import KnowledgeBaseService


class BaseRetriever(ABC):
    """Abstract base for retrieval strategies."""

    @abstractmethod
    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category_filter: str | None = None,
    ) -> list[RetrievedDocument]:
        """Retrieve relevant documents for a query."""


class HybridRetriever(BaseRetriever):
    """Hybrid retrieval combining vector similarity and BM25 keyword search."""

    def __init__(
        self,
        kb_service: KnowledgeBaseService,
        embedding_service: EmbeddingService,
        semantic_weight: float = 0.7,
    ) -> None:
        self.kb_service = kb_service
        self.embedding_service = embedding_service
        self.semantic_weight = semantic_weight

    async def retrieve(
        self,
        query: str,
        top_k: int = 5,
        category_filter: str | None = None,
    ) -> list[RetrievedDocument]:
        """Retrieve documents via hybrid search."""
        results = await self.kb_service.search_documents(
            query=query,
            top_k=top_k,
            category=category_filter,
            use_hybrid=True,
        )
        return [
            RetrievedDocument(
                id=result.id,
                title=result.title,
                content=result.content,
                category=result.category,
                similarity=result.similarity,
                source_type="hybrid",
                metadata={"source": result.source} if result.source else {},
            )
            for result in results
        ]
