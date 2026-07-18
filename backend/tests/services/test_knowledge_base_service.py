"""Tests for knowledge base service."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from redis.exceptions import RedisError

from app.core.exceptions import ForbiddenException, NotFoundException
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


class FakeOllamaEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.3] * 768

    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        del batch_size
        self.calls.extend(texts)
        return [[0.3] * 768 for _ in texts]


class FakeBgeEmbeddingService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def embed_text(self, text: str) -> list[float]:
        self.calls.append(text)
        return [0.4] * 1024

    async def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        del batch_size
        self.calls.extend(texts)
        return [[0.4] * 1024 for _ in texts]


class FakeRepository:
    def __init__(self) -> None:
        self.documents: dict[UUID, KnowledgeBase] = {}
        self.created_embeddings: list[list[float] | None] = []
        self.created_jina_embeddings: list[list[float] | None] = []
        self.created_ollama_embeddings: list[list[float] | None] = []
        self.created_bge_embeddings: list[list[float] | None] = []
        self.last_update_embedding: list[float] | None = None
        self.last_update_jina_embedding: list[float] | None = None
        self.last_update_ollama_embedding: list[float] | None = None
        self.last_update_bge_embedding: list[float] | None = None
        self.last_match_function: str | None = None
        self.last_threshold: float | None = None

    async def create(
        self,
        data: dict[str, object],
        embedding: list[float] | None,
        embedding_jina: list[float] | None = None,
        embedding_ollama: list[float] | None = None,
        embedding_bge: list[float] | None = None,
    ) -> KnowledgeBase:
        document = document_from_data(data)
        document.embedding = embedding
        document.embedding_jina = embedding_jina
        document.embedding_ollama = embedding_ollama
        document.embedding_bge = embedding_bge
        self.documents[document.id] = document
        self.created_embeddings.append(embedding)
        self.created_jina_embeddings.append(embedding_jina)
        self.created_ollama_embeddings.append(embedding_ollama)
        self.created_bge_embeddings.append(embedding_bge)
        return document

    async def create_batch(
        self,
        items_with_embeddings: list[
            tuple[
                dict[str, object],
                list[float] | None,
                list[float] | None,
                list[float] | None,
                list[float] | None,
            ]
        ],
    ) -> list[KnowledgeBase]:
        created: list[KnowledgeBase] = []
        for (
            data,
            embedding,
            embedding_jina,
            embedding_ollama,
            embedding_bge,
        ) in items_with_embeddings:
            created.append(
                await self.create(data, embedding, embedding_jina, embedding_ollama, embedding_bge)
            )
        return created

    async def get_by_id(self, kb_id: UUID) -> KnowledgeBase | None:
        return self.documents.get(kb_id)

    async def update(
        self,
        kb_id: UUID,
        data: dict[str, object],
        embedding: list[float] | None = None,
        embedding_jina: list[float] | None = None,
        embedding_ollama: list[float] | None = None,
        embedding_bge: list[float] | None = None,
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
        if embedding_ollama is not None:
            document.embedding_ollama = embedding_ollama
        if embedding_bge is not None:
            document.embedding_bge = embedding_bge
        self.last_update_embedding = embedding
        self.last_update_jina_embedding = embedding_jina
        self.last_update_ollama_embedding = embedding_ollama
        self.last_update_bge_embedding = embedding_bge
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
        match_function: str = "match_documents",
        threshold: float = 0.0,
    ) -> list[KnowledgeBaseSearchResult]:
        del query_embedding, semantic_weight, category_filter
        self.last_match_function = match_function
        self.last_threshold = threshold
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
        match_function: str = "match_documents",
    ) -> list[KnowledgeBaseSearchResult]:
        del query_embedding, category_filter
        self.last_match_function = match_function
        self.last_threshold = threshold
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


async def test_get_and_list_and_delete_and_statistics() -> None:
    svc, repo, _, _ = service()
    document = await repo.create(
        {"title": "FAQ", "content": "Noi dung", "category": "faq", "metadata_": {}},
        [0.0] * 768,
    )

    fetched = await svc.get_document(document.id, admin_user())
    assert fetched.id == document.id

    listing = await svc.list_documents(admin_user(), skip=0, limit=20)
    assert listing.total == 1

    stats = await svc.get_statistics(admin_user())
    assert stats.total == 1

    await svc.delete_document(document.id, admin_user())
    assert repo.documents[document.id].is_active is False


async def test_get_missing_document_raises() -> None:
    svc, _, _, _ = service()

    with pytest.raises(NotFoundException):
        await svc.get_document(uuid4(), admin_user())


async def test_delete_missing_document_raises() -> None:
    svc, _, _, _ = service()

    with pytest.raises(NotFoundException):
        await svc.delete_document(uuid4(), admin_user())


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

    assert repo.last_match_function == "match_documents_jina"
    assert jina_embeddings.calls == [("rò rỉ gas", "retrieval.query")]
    assert captured == [("Gemini embed quota exceeded, falling back to Jina", "warning")]


async def test_search_uses_gemini_without_jina_when_primary_ok() -> None:
    svc, repo, _, jina_embeddings = service()

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_match_function == "match_documents"
    assert jina_embeddings.calls == []


async def test_search_uses_ollama_match_function_when_provider_ollama() -> None:
    svc, repo, embeddings, jina_embeddings = service()
    ollama = FakeOllamaEmbeddingService()
    svc.ollama_embedding_service = ollama  # type: ignore[assignment]
    svc.embedding_provider = "ollama"

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_match_function == "match_documents_ollama"
    assert ollama.calls == ["rò rỉ gas"]
    # The Gemini/Jina paths must not be touched in the ollama provider.
    assert embeddings.calls == []
    assert jina_embeddings.calls == []


async def test_create_document_writes_only_ollama_embedding_when_provider_ollama() -> None:
    svc, repo, embeddings, jina_embeddings = service()
    ollama = FakeOllamaEmbeddingService()
    svc.ollama_embedding_service = ollama  # type: ignore[assignment]
    svc.embedding_provider = "ollama"
    payload = KnowledgeBaseCreate(
        title="An toàn gas",
        content="Khóa van khi ngửi thấy mùi gas.",
        category="safety",
    )

    await svc.create_document(payload, admin_user())

    assert repo.created_embeddings == [None]
    assert repo.created_jina_embeddings == [None]
    assert len(repo.created_ollama_embeddings[0] or []) == 768
    assert ollama.calls
    assert embeddings.calls == []
    assert jina_embeddings.calls == []


async def test_bulk_import_writes_ollama_embeddings_when_provider_ollama() -> None:
    svc, repo, embeddings, jina_embeddings = service()
    ollama = FakeOllamaEmbeddingService()
    svc.ollama_embedding_service = ollama  # type: ignore[assignment]
    svc.embedding_provider = "ollama"

    result = await svc.bulk_import_from_file(FakeUploadFile(), None, admin_user())  # type: ignore[arg-type]

    assert result.count == 1
    assert len(repo.created_ollama_embeddings[0] or []) == 768
    assert repo.created_embeddings == [None]
    assert repo.created_jina_embeddings == [None]
    assert embeddings.calls == []
    assert jina_embeddings.calls == []


def _bge_service() -> tuple[KnowledgeBaseService, FakeRepository, FakeBgeEmbeddingService]:
    svc, repo, _, _ = service()
    bge = FakeBgeEmbeddingService()
    svc.bge_embedding_service = bge  # type: ignore[assignment]
    svc.embedding_provider = "bge"
    return svc, repo, bge


async def test_search_uses_bge_match_function_and_threshold_when_provider_bge() -> None:
    svc, repo, bge = _bge_service()

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_match_function == "match_documents_bge"
    assert repo.last_threshold == svc.settings.RAG_THRESHOLD_BGE
    assert bge.calls == ["rò rỉ gas"]


async def test_create_document_writes_only_bge_embedding_when_provider_bge() -> None:
    svc, repo, bge = _bge_service()
    payload = KnowledgeBaseCreate(
        title="An toàn gas",
        content="Khóa van khi ngửi thấy mùi gas.",
        category="safety",
    )

    await svc.create_document(payload, admin_user())

    assert repo.created_embeddings == [None]
    assert repo.created_jina_embeddings == [None]
    assert repo.created_ollama_embeddings == [None]
    assert len(repo.created_bge_embeddings[0] or []) == 1024
    assert bge.calls


async def test_bulk_import_writes_bge_embeddings_when_provider_bge() -> None:
    svc, repo, bge = _bge_service()

    result = await svc.bulk_import_from_file(FakeUploadFile(), None, admin_user())  # type: ignore[arg-type]

    assert result.count == 1
    assert len(repo.created_bge_embeddings[0] or []) == 1024
    assert repo.created_embeddings == [None]


async def test_gemini_threshold_stays_zero_so_prod_is_unchanged() -> None:
    svc, repo, _, _ = service()

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_threshold == 0.0


async def test_ollama_threshold_applied() -> None:
    svc, repo, _, _ = service()
    svc.ollama_embedding_service = FakeOllamaEmbeddingService()  # type: ignore[assignment]
    svc.embedding_provider = "ollama"

    await svc.search_documents("rò rỉ gas", top_k=5)

    assert repo.last_threshold == svc.settings.RAG_THRESHOLD_OLLAMA


class DictRedis:
    """Dict-backed async Redis stub (get/setex) for query-cache tests."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.get_calls = 0
        self.setex_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        return self.store.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.setex_calls += 1
        self.store[key] = value


class BrokenRedis:
    """Async Redis stub whose commands always raise, to test degradation."""

    def __init__(self) -> None:
        self.get_calls = 0
        self.setex_calls = 0

    async def get(self, key: str) -> str | None:
        self.get_calls += 1
        raise RedisError("redis down")

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.setex_calls += 1
        raise RedisError("redis down")


async def test_query_cache_miss_then_hit_calls_provider_once() -> None:
    svc, _repo, embeddings, _jina = service()
    redis = DictRedis()
    svc.redis_client = redis  # type: ignore[assignment]

    first = await svc._embed_query("rò rỉ gas")
    second = await svc._embed_query("rò rỉ gas")

    assert first == second
    assert first == ([0.1] * 768, "match_documents")
    # The provider is hit exactly once; the second call is served from cache.
    assert len(embeddings.calls) == 1
    assert redis.setex_calls == 1
    assert redis.get_calls == 2


async def test_query_cache_degrades_gracefully_on_redis_error() -> None:
    svc, _repo, embeddings, _jina = service()
    svc.redis_client = BrokenRedis()  # type: ignore[assignment]

    embedding, match_function = await svc._embed_query("rò rỉ gas")

    assert embedding == [0.1] * 768
    assert match_function == "match_documents"
    assert len(embeddings.calls) == 1  # provider used; the Redis error was swallowed

    # A second call still works (no cache); nothing is ever raised.
    await svc._embed_query("rò rỉ gas")
    assert len(embeddings.calls) == 2


async def test_query_cache_disabled_when_no_redis_client() -> None:
    svc, _repo, embeddings, _jina = service()  # redis_client defaults to None

    await svc._embed_query("rò rỉ gas")
    await svc._embed_query("rò rỉ gas")

    assert len(embeddings.calls) == 2


async def test_query_cache_disabled_when_ttl_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    svc, _repo, embeddings, _jina = service()
    redis = DictRedis()
    svc.redis_client = redis  # type: ignore[assignment]
    monkeypatch.setattr(svc.settings, "EMBEDDING_QUERY_CACHE_TTL", 0)

    await svc._embed_query("rò rỉ gas")
    await svc._embed_query("rò rỉ gas")

    assert len(embeddings.calls) == 2
    assert redis.get_calls == 0
    assert redis.setex_calls == 0


async def test_query_cache_key_namespaced_by_provider() -> None:
    svc, _repo, _embeddings, _jina = service()
    redis = DictRedis()
    svc.redis_client = redis  # type: ignore[assignment]
    ollama = FakeOllamaEmbeddingService()
    svc.ollama_embedding_service = ollama  # type: ignore[assignment]

    svc.embedding_provider = "gemini"
    gemini_embedding, gemini_match = await svc._embed_query("rò rỉ gas")

    svc.embedding_provider = "ollama"
    ollama_embedding, ollama_match = await svc._embed_query("rò rỉ gas")

    # A different provider uses a different key -> no cross-provider cache hit.
    assert len(redis.store) == 2
    assert ollama.calls == ["rò rỉ gas"]
    assert gemini_match == "match_documents"
    assert ollama_match == "match_documents_ollama"
    assert gemini_embedding != ollama_embedding
