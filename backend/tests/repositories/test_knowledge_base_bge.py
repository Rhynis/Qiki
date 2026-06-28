"""Function-level tests for the BGE match function against CI Postgres.

Builds the knowledge_base table plus match_documents_bge (mirroring migration
008) and verifies that a bge-space (1024-d) query only matches rows that carry an
embedding_bge vector -- never a Gemini/Jina/Ollama-only row.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.knowledge_base_repository import (
    MATCH_DOCUMENTS_BGE,
    KnowledgeBaseRepository,
)

pytestmark = pytest.mark.asyncio

_MATCH_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION match_documents_bge(
    query_embedding VECTOR(1024),
    match_threshold FLOAT,
    match_count INT,
    filter_category TEXT DEFAULT NULL
)
RETURNS TABLE (
    id UUID,
    title VARCHAR,
    content TEXT,
    category VARCHAR,
    similarity FLOAT
)
LANGUAGE plpgsql STABLE AS $$
BEGIN
    RETURN QUERY
    SELECT
        kb.id,
        kb.title,
        kb.content,
        kb.category,
        1 - (kb.embedding_bge <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE kb.is_active = TRUE
      AND kb.embedding_bge IS NOT NULL
      AND (filter_category IS NULL OR kb.category = filter_category)
      AND 1 - (kb.embedding_bge <=> query_embedding) > match_threshold
    ORDER BY kb.embedding_bge <=> query_embedding
    LIMIT match_count;
END;
$$
"""


@pytest_asyncio.fixture
async def bge_kb_session() -> AsyncGenerator[AsyncSession, None]:
    """Create the knowledge_base table + BGE match function, then drop them."""
    from app.db.session import AsyncSessionLocal, engine
    from app.models.knowledge_base import KnowledgeBase

    await engine.dispose()
    async with engine.begin() as conn:
        await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(
            lambda sync_conn: KnowledgeBase.__table__.create(sync_conn, checkfirst=True)
        )
        await conn.execute(text(_MATCH_FUNCTION_SQL))

    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()

    async with engine.begin() as conn:
        await conn.execute(
            text("DROP FUNCTION IF EXISTS match_documents_bge(VECTOR, FLOAT, INT, TEXT)")
        )
        await conn.run_sync(
            lambda sync_conn: KnowledgeBase.__table__.drop(sync_conn, checkfirst=True)
        )
    await engine.dispose()


def _bge_vector(seed: float) -> list[float]:
    return [seed] + [0.0] * 1023


async def test_match_documents_bge_returns_only_bge_embedded_rows(
    bge_kb_session: AsyncSession,
) -> None:
    repo = KnowledgeBaseRepository(bge_kb_session)
    query = _bge_vector(1.0)

    await repo.create(
        {"title": "BGE doc", "content": "noi dung", "category": "faq"},
        embedding=None,
        embedding_bge=query,
    )
    # A Gemini-only row (768-d embedding, NULL embedding_bge) must never match a
    # bge query -- this is the vector-space isolation invariant.
    await repo.create(
        {"title": "Gemini doc", "content": "khac", "category": "faq"},
        embedding=[0.0] * 768,
        embedding_bge=None,
    )
    await bge_kb_session.flush()

    results = await repo.similarity_search(
        query,
        top_k=5,
        threshold=0.0,
        match_function=MATCH_DOCUMENTS_BGE,
    )

    titles = [result.title for result in results]
    assert "BGE doc" in titles
    assert "Gemini doc" not in titles
    assert results[0].similarity > 0.99
