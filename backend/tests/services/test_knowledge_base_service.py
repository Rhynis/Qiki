"""Tests for knowledge base service."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import ForbiddenException
from app.llm.exceptions import LLMQuotaExceededError
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.schemas.knowledge_base import (
    KnowledgeBaseCreate,
    KnowledgeBaseSearchResult,
    KnowledgeBaseUpdate,
)
from app.services.knowledge_base_service import KnowledgeBaseService

pytestmark = pytest.mark.asyncio


class FakeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.1] * 768

    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        del batch_size
        self.calls.extend(texts)
        return [[0.1] * 768 for _ in texts]


class QuotaEmbeddingService(FakeEmbeddingService):
    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        raise LLMQuotaExceededError("quota exhausted")


class FakeJinaEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def embed_text(self, text: str, *, task: str) -> list[float]:
        self.calls.append((text, task))
        return [0.2] * 768

    async def embed_batch(
        self,
        texts: list[str],
        *,
        task: str,
        batch_size: int = 32,
    ) -> list[list[float]]:
        del batch_size
        self.calls.extend((text, task) for text in texts)
        return [[0.2] * 768 for _ in texts]


class FakeRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, KnowledgeBase] = {}
        self.created_embeddings: list[list[float] | None] = []
        self.created_jina_embeddings: list[list[float] | None] = []
        self.last_update_embedding: list[float] | None = None
        self.last_update_jina_embedding: list[float] | None = None
        self.last_use_fallback: bool | None = None

    async def create(
        self,
        data: dict[str, object],
        embedding: list[float] | None,
        embedding_jina: list[float] | None = None,
    ) -> KnowledgeBase:
        document = document_from_data(data)
        document.embedding = embedding
        document.embedding_jina = embedding_jina
        self.documents[document.id] = document
        self.created_embeddings.append(embedding)
        self.created_jina_embeddings.append(embedding_jina)
        return document

    async def create_batch(
        self,
        items_with_embeddings: list[
            tuple[dict[str, object], list[float] | None, list[float] | None]
        ],
    ) -> list[KnowledgeBase]:
        created: list[KnowledgeBase] = []
        for data, embedding, embedding_jina in items_with_embeddings:
            created.append(await self.create(data, embedding, embedding_jina))
        return created

    async def get_by_id(self, kb_id: UUID) -> KnowledgeBase | None:
        return self.documents.get(kb_id)

    async def update(
        self,
        kb_id: UUID,
        data: dict[str, object],
        embedding: list[float] | None = None,
        embedding_jina: list[float] | None = None,
    ) -> KnowledgeBase:
        document = self.documents[kb_id]
        for key, value in data.items():
            if key == "metadata_":
                document.metadata_ = value  # type: ignore[assignment]
            else:
                setattr(document, key, value)
        if embedding is not None:
            document.embedding = embedding
        if embedding_jina is not None:
            document.embedding_jina = embedding_jina
        self.last_update_embedding = embedding
        self.last_update_jina_embedding = embedding_jina
        return document

    async def soft_delete(self, kb_id: UUID) -> bool:
        document = self.documents.get(kb_id)
        if not document:
            return False
        document.is_active = False
        return True

    async def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        top_k: int = 5,
        semantic_weight: float = 0.7,
        category_filter: str | None = None,
        use_fallback: bool = False,
    ) -> list[KnowledgeBaseSearchResult]:
        del query_embedding, semantic_weight, category_filter
        self.last_use_fallback = use_fallback
        return [
            KnowledgeBaseSearchResult(
                id=uuid4(),
                title="An toàn gas",
                content=query_text,
                category="safety",
                similarity=0.92,
            )
        ][:top_k]

    async def similarity_search(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        threshold: float = 0.0,
        category_filter: str | None = None,
        use_fallback: bool = False,
    ) -> list[KnowledgeBaseSearchResult]:
        del query_embedding, threshold, category_filter
        self.last_use_fallback = use_fallback
        return [
            KnowledgeBaseSearchResult(
                id=uuid4(),
                title="Vector",
                content="content",
                category="faq",
                similarity=0.5,
            )
        ][:top_k]

    async def list_documents(self, **kwargs: object) -> tuple[list[KnowledgeBase], int]:
        del kwargs
        docs = list(self.documents.values())
        return docs, len(docs)

    async def statistics(self) -> tuple[int, int, int, dict[str, int]]:
        return len(self.documents), len(self.documents), len(self.documents), {"safety": 1}


class FakeUploadFile:
    filename = "kb.csv"

    async def read(self) -> bytes:
        return b"title,content,category\nAn toan,Khoa van gas,safety\n"


def admin_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        full_name="Admin",
        phone="0900000000",
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def customer_user() -> User:
    user = admin_user()
    user.role = "customer"
    return user


def document_from_data(data: dict[str, object]) -> KnowledgeBase:
    now = datetime.now(UTC)
    return KnowledgeBase(
        id=uuid4(),
        title=str(data["title"]),
        content=str(data["content"]),
        category=str(data["category"]),
        source=data.get("source") if isinstance(data.get("source"), str) else None,
        metadata_=data.get("metadata_", {}),
        is_active=True,
        embedding=[0.1] * 768,
        created_at=now,
        updated_at=now,
    )


def service() -> (
    tuple[
        KnowledgeBaseService,
        FakeRepository,
        FakeEmbeddingService,
        FakeJinaEmbeddingService,
    ]
):
    repo = FakeRepository()
    embeddings = FakeEmbeddingService()
    jina_embeddings = FakeJinaEmbeddingService()
    return (
        KnowledgeBaseService(repo, embeddings, jina_embeddings),
        repo,
        embeddings,
        jina_embeddings,
    )


async def test_create_document_generates_embedding() -> None:
    svc, repo, embeddings, jina_embeddings = service()
    payload = KnowledgeBaseCreate(
        title="An toàn gas",
        content="Khóa van khi ngửi thấy mùi gas.",
        category="safety",
    )

    response = await svc.create_document(payload, admin_user())

    assert response.title == "An toàn gas"
    assert len(repo.created_embeddings[0]) == 768
    assert len(repo.created_jina_embeddings[0] or []) == 768
    assert embeddings.calls
    assert jina_embeddings.calls[0][1] == "retrieval.passage"


async def test_create_document_saves_jina_when_gemini_quota_fails() -> None:
    repo = FakeRepository()
    embeddings = QuotaEmbeddingService()
    jina_embeddings = FakeJinaEmbeddingService()
    svc = KnowledgeBaseService(repo, embeddings, jina_embeddings)
    payload = KnowledgeBaseCreate(
        title="An toàn gas",
        content="Khóa van khi ngửi thấy mùi gas.",
        category="safety",
    )

    await svc.create_document(payload, admin_user())

    assert repo.created_embeddings == [None]
    assert len(repo.created_jina_embeddings[0] or []) == 768
    assert jina_embeddings.calls[0][1] == "retrieval.passage"


async def test_update_regenerates_embedding_if_content_changed() -> None:
    svc, repo, embeddings, _ = service()
    document = await repo.create(
        {"title": "Cũ", "content": "Nội dung cũ", "category": "faq", "metadata_": {}},
        [0.0] * 768,
    )

    await svc.update_document(
        document.id,
        KnowledgeBaseUpdate(content="Nội dung mới"),
        admin_user(),
    )

    assert repo.last_update_embedding is not None
    assert embeddings.calls[-1].endswith("Nội dung mới")


async def test_update_keeps_embedding_if_search_text_unchanged() -> None:
    svc, repo, embeddings, _ = service()
    document = await repo.create(
        {"title": "Cũ", "content": "Nội dung cũ", "category": "faq", "metadata_": {}},
        [0.0] * 768,
    )

    await svc.update_document(document.id, KnowledgeBaseUpdate(source="seed_data"), admin_user())

    assert repo.last_update_embedding is None
    assert embeddings.calls == []


async def test_search_returns_relevant_results() -> None:
    svc, _, _, _ = service()

    results = await svc.search_documents("rò rỉ gas", top_k=5)

    assert results[0].title == "An toàn gas"
    assert results[0].similarity > 0.9


async def test_hybrid_search_blends_scores_correctly() -> None:
    svc, _, _, _ = service()

    hybrid = await svc.search_documents("rò rỉ gas", use_hybrid=True)
    vector = await svc.search_documents("rò rỉ gas", use_hybrid=False)

    assert hybrid[0].similarity > vector[0].similarity


async def test_bulk_import_from_csv() -> None:
    svc, _, embeddings, jina_embeddings = service()

    result = await svc.bulk_import_from_file(FakeUploadFile(), None, admin_user())  # type: ignore[arg-type]

    assert result.count == 1
    assert embeddings.calls
    assert jina_embeddings.calls


async def test_only_admin_can_create() -> None:
    svc, _, _, _ = service()
    payload = KnowledgeBaseCreate(title="FAQ", content="Noi dung", category="faq")

    with pytest.raises(ForbiddenException):
        await svc.create_document(payload, customer_user())


async def test_search_falls_back_to_jina_on_gemini_quota(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = FakeRepository()
    embeddings = QuotaEmbeddingService()
    jina_embeddings = FakeJinaEmbeddingService()
    captured: list[tuple[str, str]] = []
    monkeypatch.setattr(
        "app.services.knowledge_base_service.sentry_sdk.capture_message",
        lambda message, level: captured.append((message, level)),
    )
    svc = KnowledgeBaseService(repo, embeddings, jina_embeddings)

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_use_fallback is True
    assert jina_embeddings.calls == [("rò rỉ gas", "retrieval.query")]
    assert captured == [("Gemini embed quota exceeded, falling back to Jina", "warning")]


async def test_search_uses_gemini_without_jina_when_primary_ok() -> None:
    svc, repo, _, jina_embeddings = service()

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_use_fallback is False
    assert jina_embeddings.calls == []
