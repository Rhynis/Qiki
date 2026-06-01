"""Add Jina embedding fallback column.

Revision ID: 003_add_jina_embedding
Revises: 002_add_hashed_password
Create Date: 2026-06-01
"""

from collections.abc import Sequence

from alembic import op

revision: str = "003_add_jina_embedding"
down_revision: str | None = "002_add_hashed_password"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add Jina embedding storage and search function."""
    op.execute("ALTER TABLE knowledge_base ADD COLUMN embedding_jina vector(768)")
    op.execute(
        """
        CREATE INDEX idx_kb_embedding_jina ON knowledge_base
            USING ivfflat (embedding_jina vector_cosine_ops) WITH (lists = 100)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION match_documents_jina(
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
                1 - (kb.embedding_jina <=> query_embedding) AS similarity
            FROM knowledge_base kb
            WHERE kb.is_active = TRUE
              AND kb.embedding_jina IS NOT NULL
              AND (filter_category IS NULL OR kb.category = filter_category)
              AND 1 - (kb.embedding_jina <=> query_embedding) > match_threshold
            ORDER BY kb.embedding_jina <=> query_embedding
            LIMIT match_count;
        END;
        $$
        """
    )


def downgrade() -> None:
    """Remove Jina embedding fallback objects."""
    op.execute("DROP FUNCTION IF EXISTS match_documents_jina(VECTOR, FLOAT, INT, TEXT)")
    op.execute("DROP INDEX IF EXISTS idx_kb_embedding_jina")
    op.execute("ALTER TABLE knowledge_base DROP COLUMN IF EXISTS embedding_jina")
