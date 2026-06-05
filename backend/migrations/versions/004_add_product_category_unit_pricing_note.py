"""Add product category, unit, and pricing note fields.

Revision ID: 004_product_category_unit
Revises: 003_add_jina_embedding
Create Date: 2026-06-05
"""

from collections.abc import Sequence

from alembic import op

revision: str = "004_product_category_unit"
down_revision: str | None = "003_add_jina_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add category/unit support for products and backfill existing rows."""
    op.execute("ALTER TABLE products ADD COLUMN category VARCHAR(30)")
    op.execute("ALTER TABLE products ADD COLUMN unit VARCHAR(20)")
    op.execute("ALTER TABLE products ADD COLUMN pricing_note TEXT")
    op.execute("UPDATE products SET category = 'gas' WHERE category IS NULL")
    op.execute("UPDATE products SET unit = 'kg' WHERE unit IS NULL")
    op.execute("ALTER TABLE products ALTER COLUMN category SET DEFAULT 'gas'")
    op.execute("ALTER TABLE products ALTER COLUMN unit SET DEFAULT 'kg'")
    op.execute("ALTER TABLE products ALTER COLUMN category SET NOT NULL")
    op.execute("ALTER TABLE products ALTER COLUMN unit SET NOT NULL")
    op.execute("CREATE INDEX idx_products_category ON products(category)")
    op.execute("COMMENT ON COLUMN products.category IS 'Product category: gas or nuoc_uong'")
    op.execute(
        "COMMENT ON COLUMN products.unit IS 'Display unit for product size, such as kg or lít'"
    )
    op.execute(
        "COMMENT ON COLUMN products.pricing_note IS 'Additional pricing and delivery notes for water products'"
    )


def downgrade() -> None:
    """Remove product category/unit fields."""
    op.execute("DROP INDEX IF EXISTS idx_products_category")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS pricing_note")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS unit")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS category")
