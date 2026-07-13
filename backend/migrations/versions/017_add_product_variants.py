"""Introduce parent products so colour/size rows become selectable variants.

Revision ID: 017_add_product_variants
Revises: 015_add_price_subscriptions
Create Date: 2026-07-13

Each existing product row is a concrete, priced and stocked entity (e.g.
"Saigon Petro 12kg (xám)"). This migration adds a ``product_parents`` grouping
table plus ``parent_id`` / ``colour`` / ``variant_label`` columns on
``products``, then backfills a parent for every distinct (brand, category) so no
existing product loses its price, stock or ``is_active`` flag. The priced row
never moves, so carts, orders and the deterministic chatbot pricing keep
resolving the exact same variant.

Each statement is a separate ``op.execute()`` because asyncpg cannot run
multi-statement SQL in a single execute. The colour backfill parses the trailing
"(...)" note in the product name; downgrade drops the added table/columns.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "017_add_product_variants"
down_revision: str | None = "015_add_price_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create product_parents, add variant columns, and backfill from products."""
    op.execute(
        """
        CREATE TABLE product_parents (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            brand VARCHAR(100) NOT NULL,
            category VARCHAR(30) NOT NULL DEFAULT 'gas',
            description TEXT,
            image_url TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_product_parents_brand_category UNIQUE (brand, category)
        )
        """
    )
    op.execute("CREATE INDEX idx_product_parents_brand ON product_parents(brand)")
    op.execute("CREATE INDEX idx_product_parents_active ON product_parents(is_active)")
    op.execute(
        "COMMENT ON TABLE product_parents IS "
        "'Parent product grouping one or more sellable variants (colour/size)'"
    )
    op.execute("ALTER TABLE product_parents ENABLE ROW LEVEL SECURITY")

    op.execute("ALTER TABLE products ADD COLUMN parent_id UUID")
    op.execute("ALTER TABLE products ADD COLUMN colour VARCHAR(50)")
    op.execute("ALTER TABLE products ADD COLUMN variant_label VARCHAR(100)")
    op.execute(
        "ALTER TABLE products "
        "ADD CONSTRAINT fk_products_parent "
        "FOREIGN KEY (parent_id) REFERENCES product_parents(id) ON DELETE SET NULL"
    )
    op.execute("CREATE INDEX idx_products_parent ON products(parent_id)")

    # Backfill one parent per distinct (brand, category). The parent name drops
    # the trailing "(...)" colour note and the size token so several coloured
    # cylinders collapse into one storefront card (e.g. "Bình gas Saigon Petro").
    op.execute(
        """
        INSERT INTO product_parents (name, brand, category, description, image_url, is_active)
        SELECT DISTINCT ON (p.brand, p.category)
            btrim(
                regexp_replace(
                    regexp_replace(p.name, '\\s*\\([^)]*\\)\\s*$', ''),
                    '\\s*\\d+([.,]\\d+)?\\s*(kg|lít|l)\\y',
                    '',
                    'gi'
                )
            ) AS name,
            p.brand,
            p.category,
            p.description,
            p.image_url,
            TRUE
        FROM products p
        ORDER BY p.brand, p.category, p.created_at
        """
    )

    # Link every existing product to its parent.
    op.execute(
        """
        UPDATE products p
        SET parent_id = pp.id
        FROM product_parents pp
        WHERE p.brand = pp.brand AND p.category = pp.category
        """
    )

    # Extract the colour note from the trailing "(...)" when present.
    op.execute(
        """
        UPDATE products
        SET colour = trim(substring(name FROM '\\(([^)]*)\\)\\s*$'))
        WHERE name ~ '\\([^)]*\\)\\s*$'
        """
    )

    # A human-friendly option label: size + colour (colour omitted when absent).
    op.execute(
        """
        UPDATE products
        SET variant_label = trim(
            btrim(
                (rtrim(to_char(size_kg, 'FM999999990.99'), '.') || ' ' || unit)
                || CASE WHEN colour IS NOT NULL AND colour <> ''
                        THEN ' (' || colour || ')' ELSE '' END
            )
        )
        """
    )


def downgrade() -> None:
    """Drop variant columns and the product_parents table."""
    op.execute("DROP INDEX IF EXISTS idx_products_parent")
    op.execute("ALTER TABLE products DROP CONSTRAINT IF EXISTS fk_products_parent")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS variant_label")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS colour")
    op.execute("ALTER TABLE products DROP COLUMN IF EXISTS parent_id")
    op.execute("DROP TABLE IF EXISTS product_parents")
