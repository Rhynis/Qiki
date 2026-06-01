"""Knowledge base service layer."""

import csv
import json
from io import StringIO
from typing import Any, cast
from uuid import UUID

import sentry_sdk
from fastapi import UploadFile

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.llm.exceptions import LLMQuotaExceededError, LLMRateLimitError
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.rag.embeddings import EmbeddingService
from app.rag.jina_embeddings import JinaEmbeddingService
from app.rag.text_processor import VietnameseTextProcessor
from app.repositories.knowledge_base_repository import KnowledgeBaseRepository
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseImportResponse,
    KnowledgeBaseListResponse,
    KnowledgeBaseResponse,
    KnowledgeBaseSearchResult,
    KnowledgeBaseStatistics,
    KnowledgeBaseUpdate,
    KnowledgeCategory,
)


class KnowledgeBaseService:
    """Business logic for knowledge base CRUD and retrieval."""

    def __init__(
        self,
        repository: KnowledgeBaseRepository,
        embedding_service: EmbeddingService | None = None,
        jina_embedding_service: JinaEmbeddingService | None = None,
        text_processor: VietnameseTextProcessor | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_service = embedding_service or EmbeddingService()
        self.jina_embedding_service = jina_embedding_service or JinaEmbeddingService()
        self.text_processor = text_processor or VietnameseTextProcessor()
        self.logger = get_logger(__name__)

    async def create_document(
        self,
        data: KnowledgeBaseCreate,
        current_user: User,
    ) -> KnowledgeBaseResponse:
        """Create a document and generate its embedding."""
        self._ensure_staff(current_user)
        normalized = self._normalize_payload(data.model_dump())
        embedding, embedding_jina = await self._embed_document(
            str(normalized["title"]),
            str(normalized["content"]),
        )
        document = await self.repository.create(normalized, embedding, embedding_jina)
        return self._response(document)

    async def update_document(
        self,
        kb_id: UUID,
        data: KnowledgeBaseUpdate,
        current_user: User,
    ) -> KnowledgeBaseResponse:
        """Update a document and re-embed when content changes."""
        self._ensure_staff(current_user)
        existing = await self.repository.get_by_id(kb_id)
        if not existing:
            raise NotFoundException("Knowledge base document not found", error_code="kb_not_found")

        update_data = data.model_dump(exclude_unset=True)
        normalized = self._normalize_payload(update_data)
        embedding = None
        embedding_jina = None
        if "content" in normalized or "title" in normalized:
            title = str(normalized.get("title", existing.title))
            content = str(normalized.get("content", existing.content))
            embedding, embedding_jina = await self._embed_document(
                title,
                content,
            )
        document = await self.repository.update(kb_id, normalized, embedding, embedding_jina)
        return self._response(document)

    async def delete_document(self, kb_id: UUID, current_user: User) -> None:
        """Soft-delete a document."""
        self._ensure_staff(current_user)
        deleted = await self.repository.soft_delete(kb_id)
        if not deleted:
            raise NotFoundException("Knowledge base document not found", error_code="kb_not_found")

    async def get_document(self, kb_id: UUID, current_user: User) -> KnowledgeBaseResponse:
        """Return one document for admin/staff use."""
        self._ensure_staff(current_user)
        document = await self.repository.get_by_id(kb_id)
        if not document:
            raise NotFoundException("Knowledge base document not found", error_code="kb_not_found")
        return self._response(document)

    async def list_documents(
        self,
        current_user: User,
        *,
        skip: int = 0,
        limit: int = 20,
        category: str | None = None,
        active_only: bool = True,
    ) -> KnowledgeBaseListResponse:
        """List documents for the admin UI."""
        self._ensure_staff(current_user)
        documents, total = await self.repository.list_documents(
            skip=skip,
            limit=limit,
            category_filter=category,
            active_only=active_only,
        )
        return KnowledgeBaseListResponse(
            items=[self._response(document) for document in documents],
            total=total,
            page=(skip // limit) + 1,
            limit=limit,
            has_more=skip + len(documents) < total,
        )

    async def search_documents(
        self,
        query: str,
        *,
        top_k: int = 5,
        category: str | None = None,
        use_hybrid: bool = True,
    ) -> list[KnowledgeBaseSearchResult]:
        """Search documents for RAG retrieval testing."""
        normalized_query = self.text_processor.normalize(query)
        if not normalized_query:
            return []
        embedding, use_fallback = await self._embed_query(normalized_query)
        if use_hybrid:
            return await self.repository.hybrid_search(
                normalized_query,
                embedding,
                top_k=top_k,
                category_filter=category,
                use_fallback=use_fallback,
            )
        return await self.repository.similarity_search(
            embedding,
            top_k=top_k,
            threshold=0.0,
            category_filter=category,
            use_fallback=use_fallback,
        )

    async def bulk_import_from_file(
        self,
        file: UploadFile,
        category: str | None,
        current_user: User,
    ) -> KnowledgeBaseImportResponse:
        """Import documents from CSV, JSON, TXT, or Markdown upload."""
        self._ensure_staff(current_user)
        raw = (await file.read()).decode("utf-8")
        documents = self._parse_import(raw, file.filename or "upload.txt", category)
        if not documents:
            raise ValidationException(
                "No documents found in import file",
                error_code="kb_empty_import",
            )

        texts = [
            self._embedding_text(str(item["title"]), str(item["content"])) for item in documents
        ]
        embeddings = await self.embedding_service.embed_batch(texts, batch_size=32)
        embeddings_jina = await self.jina_embedding_service.embed_batch(
            texts,
            task="retrieval.passage",
            batch_size=32,
        )
        created = await self.repository.create_batch(
            list(zip(documents, embeddings, embeddings_jina, strict=True))
        )
        return KnowledgeBaseImportResponse(count=len(created), errors=[])

    async def get_statistics(self, current_user: User) -> KnowledgeBaseStatistics:
        """Return knowledge base statistics."""
        self._ensure_staff(current_user)
        total, active, recent, by_category = await self.repository.statistics()
        return KnowledgeBaseStatistics(
            total=total,
            active=active,
            by_category=by_category,
            recent_additions=recent,
        )

    def _normalize_payload(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        if "title" in normalized and normalized["title"] is not None:
            normalized["title"] = self.text_processor.normalize(str(normalized["title"]))
        if "content" in normalized and normalized["content"] is not None:
            normalized["content"] = self.text_processor.normalize(str(normalized["content"]))
        if "metadata" in normalized:
            normalized["metadata_"] = normalized.pop("metadata") or {}
        return normalized

    def _parse_import(
        self,
        raw: str,
        filename: str,
        category_override: str | None,
    ) -> list[dict[str, Any]]:
        suffix = filename.rsplit(".", 1)[-1].lower()
        if suffix == "json":
            loaded = json.loads(raw)
            records = loaded if isinstance(loaded, list) else [loaded]
            return [self._normalize_import_record(record, category_override) for record in records]
        if suffix == "csv":
            rows = csv.DictReader(StringIO(raw))
            return [self._normalize_import_record(dict(row), category_override) for row in rows]
        metadata, body = parse_front_matter(raw)
        record = {
            "title": metadata.get("title", filename.rsplit(".", 1)[0]),
            "content": body,
            "category": category_override or metadata.get("category", "faq"),
            "source": metadata.get("source", "upload"),
            "metadata": metadata,
        }
        return [self._normalize_payload(record)]

    def _normalize_import_record(
        self,
        record: dict[str, Any],
        category_override: str | None,
    ) -> dict[str, Any]:
        return self._normalize_payload(
            {
                "title": record.get("title", "Untitled"),
                "content": record.get("content", ""),
                "category": category_override or record.get("category", "faq"),
                "source": record.get("source", "upload"),
                "metadata": record.get("metadata", {}),
            }
        )

    @staticmethod
    def _embedding_text(title: str, content: str) -> str:
        return f"{title}\n\n{content}"

    async def _embed_query(self, query: str) -> tuple[list[float], bool]:
        try:
            return await self.embedding_service.embed_text(query), False
        except (LLMQuotaExceededError, LLMRateLimitError):
            sentry_sdk.capture_message(
                "Gemini embed quota exceeded, falling back to Jina",
                level="warning",
            )
            embedding = await self.jina_embedding_service.embed_text(
                query,
                task="retrieval.query",
            )
            return embedding, True

    async def _embed_document(
        self, title: str, content: str
    ) -> tuple[list[float] | None, list[float]]:
        text = self._embedding_text(title, content)
        embedding: list[float] | None
        try:
            embedding = await self.embedding_service.embed_text(text)
        except (LLMQuotaExceededError, LLMRateLimitError) as exc:
            embedding = None
            self.logger.warning("gemini_document_embedding_unavailable", error=str(exc))
        embedding_jina = await self.jina_embedding_service.embed_text(
            text,
            task="retrieval.passage",
        )
        return embedding, embedding_jina

    @staticmethod
    def _ensure_staff(user: User) -> None:
        if not user.is_staff():
            raise ForbiddenException("Staff role required", error_code="staff_required")

    @staticmethod
    def _response(document: KnowledgeBase) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id=document.id,
            title=document.title,
            content=document.content,
            category=KnowledgeBaseService._category(document.category),
            source=document.source,
            metadata=document.metadata_ or {},
            is_active=document.is_active,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )

    @staticmethod
    def _category(value: str) -> KnowledgeCategory:
        return cast(KnowledgeCategory, value)


def parse_front_matter(content: str) -> tuple[dict[str, str], str]:
    """Parse simple YAML-style front matter."""
    if not content.startswith("---"):
        return {}, content.strip()
    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content.strip()
    metadata: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            metadata[key.strip()] = value.strip()
    return metadata, parts[2].strip()
