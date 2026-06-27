"""Function-level tests for the Ollama match function against CI Postgres.

Builds the knowledge_base table plus match_documents_ollama (mirroring migration
007) and verifies that a nomic-space query only matches rows that carry an
embedding_ollama vector.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.knowledge_base_repository import (
    MATCH_DOCUMENTS_OLLAMA,
    KnowledgeBaseRepository,
)

pytestmark = pytest.mark.asyncio

_MATCH_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION match_documents_ollama(
    query_embedding VECTOR(768),
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
        1 - (kb.embedding_ollama <=> query_embedding) AS similarity
    FROM knowledge_base kb
    WHERE kb.is_active = TRUE
      AND kb.embedding_ollama IS NOT NULL
      AND (filter_category IS NULL OR kb.category = filter_category)
      AND 1 - (kb.embedding_ollama <=> query_embedding) > match_threshold
    ORDER BY kb.embedding_ollama <=> query_embedding
    LIMIT match_count;
END;
$$
"""


@pytest_asyncio.fixture
async def ollama_kb_session() -> AsyncGenerator[AsyncSession, None]:
    """Create the knowledge_base table + Ollama match function, then drop them."""
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
            text("DROP FUNCTION IF EXISTS match_documents_ollama(VECTOR, FLOAT, INT, TEXT)")
        )
        await conn.run_sync(
            lambda sync_conn: KnowledgeBase.__table__.drop(sync_conn, checkfirst=True)
        )
    await engine.dispose()


def _synthetic_vector(seed: float) -> list[float]:
    return [seed] + [0.0] * 767


async def test_match_documents_ollama_returns_only_ollama_embedded_rows(
    ollama_kb_session: AsyncSession,
) -> None:
    repo = KnowledgeBaseRepository(ollama_kb_session)
    query = _synthetic_vector(1.0)

    await repo.create(
        {"title": "Ollama doc", "content": "noi dung", "category": "faq"},
        embedding=None,
        embedding_ollama=query,
    )
    # A Gemini-only row (embedding_ollama IS NULL) must never match a nomic query.
    await repo.create(
        {"title": "Gemini doc", "content": "khac", "category": "faq"},
        embedding=_synthetic_vector(1.0),
        embedding_ollama=None,
    )
    await ollama_kb_session.flush()

    results = await repo.similarity_search(
        query,
        top_k=5,
        threshold=0.0,
        match_function=MATCH_DOCUMENTS_OLLAMA,
    )

    titles = [result.title for result in results]
    assert "Ollama doc" in titles
    assert "Gemini doc" not in titles
    assert results[0].similarity > 0.99
