"""Add BGE (bge-m3) embedding column and search function.

Revision ID: 008_add_bge_embedding
Revises: 007_add_ollama_embedding
Create Date: 2026-06-27

Mirrors 007 (the Ollama column/index/function) for the bge-m3 vector space, which
is 1024-dimensional. A query embedded with bge-m3 must only be compared against
``embedding_bge`` via ``match_documents_bge`` -- never against the Gemini, Jina,
or Ollama columns. One statement per ``op.execute()`` (asyncpg); the function body
is dollar-quoted.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "008_add_bge_embedding"
down_revision: str | None = "007_add_ollama_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add BGE embedding storage and search function."""
    op.execute("ALTER TABLE knowledge_base ADD COLUMN embedding_bge vector(1024)")
    op.execute(
        """
        CREATE INDEX idx_kb_embedding_bge ON knowledge_base
            USING ivfflat (embedding_bge vector_cosine_ops) WITH (lists = 100)
        """
    )
    op.execute(
        """
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
    )


def downgrade() -> None:
    """Remove BGE embedding objects."""
    op.execute("DROP FUNCTION IF EXISTS match_documents_bge(VECTOR, FLOAT, INT, TEXT)")
    op.execute("DROP INDEX IF EXISTS idx_kb_embedding_bge")
    op.execute("ALTER TABLE knowledge_base DROP COLUMN IF EXISTS embedding_bge")
