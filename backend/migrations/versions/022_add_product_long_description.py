"""Add a nullable long_description column to products and product_parents.

Revision ID: 022_add_product_long_description
Revises: 021_add_admin_audit_logs
Create Date: 2026-07-30

Adds a separate detailed (long) description shown on the product page, keeping the
existing ``description`` as the short listing text. Additive + nullable, so it is
safe on production with no backfill. Each statement runs in its own
``op.execute()`` because asyncpg cannot run multi-statement SQL in one execute.
RLS is unaffected (no new table).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "022_add_product_long_description"
down_revision: str | None = "021_add_admin_audit_logs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the nullable long_description column to both product tables."""
    op.execute("ALTER TABLE products ADD COLUMN long_description TEXT")
    op.execute("ALTER TABLE product_parents ADD COLUMN long_description TEXT")


def downgrade() -> None:
    """Drop the long_description column from both product tables."""
    op.execute("ALTER TABLE product_parents DROP COLUMN long_description")
    op.execute("ALTER TABLE products DROP COLUMN long_description")
