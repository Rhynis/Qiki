"""Add Ollama (nomic-embed-text) embedding column and search function.

Revision ID: 007_add_ollama_embedding
Revises: 006_add_email_verified
Create Date: 2026-06-18

Mirrors 003 (the Jina column/index/function). A query embedded with nomic must
only be compared against ``embedding_ollama`` via ``match_documents_ollama`` —
never against the Gemini (``embedding``) or Jina (``embedding_jina``) columns.
One statement per ``op.execute()`` (asyncpg); the function body is dollar-quoted.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "007_add_ollama_embedding"
down_revision: str | None = "006_add_email_verified"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Ollama embedding storage and search function."""
    op.execute("ALTER TABLE knowledge_base ADD COLUMN embedding_ollama vector(768)")
    op.execute(
        """
        CREATE INDEX idx_kb_embedding_ollama ON knowledge_base
            USING ivfflat (embedding_ollama vector_cosine_ops) WITH (lists = 100)
        """
    )
    op.execute(
        """
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
    )


def downgrade() -> None:
    """Remove Ollama embedding objects."""
    op.execute("DROP FUNCTION IF EXISTS match_documents_ollama(VECTOR, FLOAT, INT, TEXT)")
    op.execute("DROP INDEX IF EXISTS idx_kb_embedding_ollama")
    op.execute("ALTER TABLE knowledge_base DROP COLUMN IF EXISTS embedding_ollama")
