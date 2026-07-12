"""Add the wishlists table (customer saved products).

Revision ID: 012_add_wishlists
Revises: 011_widen_conversation_status
Create Date: 2026-07-11

A logged-in customer can save products to a wishlist. One row per (user, product);
the unique constraint keeps adds idempotent. Rows cascade-delete with their user
or product.

Each statement is a separate ``op.execute()`` because asyncpg cannot run
multi-statement SQL in a single execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "012_add_wishlists"
down_revision: str | None = "011_widen_conversation_status"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the wishlists table with a unique (user_id, product_id) constraint."""
    op.execute(
        """
        CREATE TABLE wishlists (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_wishlists_user_product UNIQUE (user_id, product_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_wishlists_user ON wishlists(user_id)")
    op.execute("COMMENT ON TABLE wishlists IS 'Products a customer saved to their wishlist'")


def downgrade() -> None:
    """Drop the wishlists table."""
    op.execute("DROP TABLE IF EXISTS wishlists")
