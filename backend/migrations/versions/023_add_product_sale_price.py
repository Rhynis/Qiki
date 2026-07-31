"""Add a nullable sale_price column to products.

Revision ID: 023_add_product_sale_price
Revises: 022_add_product_long_description
Create Date: 2026-07-30

A manually-entered sale price per product. When set (and a valid discount below the
list price) it is the effective price actually charged. Additive + nullable, so it
is safe on production with no backfill. Each statement runs in its own
``op.execute()`` because asyncpg cannot run multi-statement SQL in one execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "023_add_product_sale_price"
down_revision: str | None = "022_add_product_long_description"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable sale_price column."""
    op.execute("ALTER TABLE products ADD COLUMN sale_price NUMERIC(10, 2)")


def downgrade() -> None:
    """Drop the sale_price column."""
    op.execute("ALTER TABLE products DROP COLUMN sale_price")
