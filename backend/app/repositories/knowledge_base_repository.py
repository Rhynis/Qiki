"""Knowledge base repository."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from rank_bm25 import BM25Okapi
from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.knowledge_base import KnowledgeBase
from app.schemas.knowledge_base import KnowledgeBaseSearchResult


class KnowledgeBaseRepository:
    """Data access layer for knowledge base documents."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        data: dict[str, Any],
        embedding: list[float] | None,
        embedding_jina: list[float] | None = None,
    ) -> KnowledgeBase:
        """Create one knowledge base document."""
        document = KnowledgeBase(**data, embedding=embedding, embedding_jina=embedding_jina)
        self.session.add(document)
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def create_batch(
        self,
        items_with_embeddings: Sequence[
            tuple[dict[str, Any], list[float] | None, list[float] | None]
        ],
    ) -> list[KnowledgeBase]:
        """Create many knowledge base documents."""
        documents = [
            KnowledgeBase(**item_data, embedding=embedding, embedding_jina=embedding_jina)
            for item_data, embedding, embedding_jina in items_with_embeddings
        ]
        self.session.add_all(documents)
        await self.session.flush()
        for document in documents:
            await self.session.refresh(document)
        return documents

    async def get_by_id(self, kb_id: UUID) -> KnowledgeBase | None:
        """Find document by ID."""
        return await self.session.get(KnowledgeBase, kb_id)

    async def update(
        self,
        kb_id: UUID,
        data: dict[str, Any],
        embedding: list[float] | None = None,
        embedding_jina: list[float] | None = None,
    ) -> KnowledgeBase:
        """Update document fields and optionally embedding."""
        document = await self.get_by_id(kb_id)
        if not document:
            raise NotFoundException("Knowledge base document not found", error_code="kb_not_found")
        for key, value in data.items():
            if key == "metadata":
                document.metadata_ = value
            elif hasattr(document, key):
                setattr(document, key, value)
        if embedding is not None:
            document.embedding = embedding
        if embedding_jina is not None:
            document.embedding_jina = embedding_jina
        await self.session.flush()
        await self.session.refresh(document)
        return document

    async def soft_delete(self, kb_id: UUID) -> bool:
        """Mark a document inactive."""
        document = await self.get_by_id(kb_id)
        if not document:
            return False
        document.is_active = False
        await self.session.flush()
        return True

    async def list_documents(
        self,
        *,
        skip: int = 0,
        limit: int = 20,
        category_filter: str | None = None,
        active_only: bool = True,
    ) -> tuple[list[KnowledgeBase], int]:
        """List documents with filters and pagination."""
        query = select(KnowledgeBase)
        query = self._apply_filters(query, category_filter, active_only)
        count_query = select(func.count()).select_from(query.order_by(None).subquery())
        total = int((await self.session.execute(count_query)).scalar_one())
        result = await self.session.execute(
            query.order_by(KnowledgeBase.created_at.desc()).offset(skip).limit(limit)
        )
        return list(result.scalars().all()), total

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.5,
        category_filter: str | None = None,
        use_fallback: bool = False,
    ) -> list[KnowledgeBaseSearchResult]:
        """Search via pgvector similarity using the migration's match_documents function."""
        sql = (
            """
            SELECT id, title, content, category, similarity
            FROM match_documents_jina(
                CAST(:query_embedding AS vector),
                :threshold,
                :top_k,
                :category_filter
            )
            """
            if use_fallback
            else """
            SELECT id, title, content, category, similarity
            FROM match_documents(
                CAST(:query_embedding AS vector),
                :threshold,
                :top_k,
                :category_filter
            )
            """
        )
        result = await self.session.execute(
            text(sql),
            {
                "query_embedding": self._vector_literal(query_embedding),
                "threshold": threshold,
                "top_k": top_k,
                "category_filter": category_filter,
            },
        )
        return [
            KnowledgeBaseSearchResult(
                id=row.id,
                title=row.title,
                content=row.content,
                category=row.category,
                similarity=float(row.similarity),
                source=None,
            )
            for row in result
        ]

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        top_k: int = 5,
        semantic_weight: float = 0.7,
        category_filter: str | None = None,
        use_fallback: bool = False,
    ) -> list[KnowledgeBaseSearchResult]:
        """Blend vector similarity with PostgreSQL keyword ranking."""
        semantic = await self.similarity_search(
            query_embedding,
            top_k=max(top_k * 3, top_k),
            threshold=0.0,
            category_filter=category_filter,
            use_fallback=use_fallback,
        )
        keyword = await self.bm25_search(
            query_text,
            top_k=max(top_k * 5, 20),
            category_filter=category_filter,
        )
        semantic_by_id = {item.id: item for item in semantic}
        keyword_by_id = {item.id: item for item in keyword}
        keyword_scores = {item.id: item.similarity for item in keyword}
        all_ids = set(semantic_by_id) | set(keyword_scores)

        blended: list[KnowledgeBaseSearchResult] = []
        for document_id in all_ids:
            semantic_item = semantic_by_id.get(document_id)
            keyword_score = keyword_scores.get(document_id, 0.0)
            if semantic_item is None:
                semantic_score = 0.0
                item = keyword_by_id[document_id]
            else:
                semantic_score = semantic_item.similarity
                item = semantic_item
            item.similarity = (
                semantic_weight * semantic_score + (1 - semantic_weight) * keyword_score
            )
            blended.append(item)

        return sorted(blended, key=lambda item: item.similarity, reverse=True)[:top_k]

    async def bm25_search(
        self,
        query_text: str,
        top_k: int = 5,
        category_filter: str | None = None,
    ) -> list[KnowledgeBaseSearchResult]:
        """Search active documents using BM25."""
        documents, _ = await self.list_documents(
            skip=0,
            limit=1000,
            category_filter=category_filter,
            active_only=True,
        )
        if not documents:
            return []
        tokenized_corpus = [self._tokenize(f"{doc.title} {doc.content}") for doc in documents]
        scores = BM25Okapi(tokenized_corpus).get_scores(self._tokenize(query_text))
        max_score = float(max(scores)) if len(scores) else 0.0
        ranked = sorted(
            zip(documents, scores, strict=True),
            key=lambda item: item[1],
            reverse=True,
        )
        return [
            self._search_result(document, float(score) / max_score if max_score else 0.0)
            for document, score in ranked[:top_k]
        ]

    async def count_by_category(self) -> dict[str, int]:
        """Count active documents by category."""
        result = await self.session.execute(
            select(KnowledgeBase.category, func.count())
            .where(KnowledgeBase.is_active.is_(True))
            .group_by(KnowledgeBase.category)
        )
        return {str(category): int(count) for category, count in result.all()}

    async def statistics(self) -> tuple[int, int, int, dict[str, int]]:
        """Return aggregate document counts."""
        total = int(
            (
                await self.session.execute(select(func.count()).select_from(KnowledgeBase))
            ).scalar_one()
        )
        active = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(KnowledgeBase)
                    .where(KnowledgeBase.is_active.is_(True))
                )
            ).scalar_one()
        )
        since = datetime.now(UTC) - timedelta(days=7)
        recent = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(KnowledgeBase)
                    .where(KnowledgeBase.created_at >= since)
                )
            ).scalar_one()
        )
        return total, active, recent, await self.count_by_category()

    @staticmethod
    def _apply_filters(
        query: Select[tuple[KnowledgeBase]],
        category_filter: str | None,
        active_only: bool,
    ) -> Select[tuple[KnowledgeBase]]:
        if category_filter:
            query = query.where(KnowledgeBase.category == category_filter)
        if active_only:
            query = query.where(KnowledgeBase.is_active.is_(True))
        return query

    @staticmethod
    def _tokenize(text_value: str) -> list[str]:
        return [token for token in text_value.lower().split() if token]

    @staticmethod
    def _vector_literal(embedding: list[float]) -> str:
        return "[" + ",".join(str(float(value)) for value in embedding) + "]"

    @staticmethod
    def _search_result(document: KnowledgeBase, similarity: float) -> KnowledgeBaseSearchResult:
        return KnowledgeBaseSearchResult(
            id=document.id,
            title=document.title,
            content=document.content,
            category=document.category,
            similarity=similarity,
            source=document.source,
        )
