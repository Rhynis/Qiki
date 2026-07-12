"""Add deliveries and delivery_items tables (multi-delivery per order).

Revision ID: 013_add_deliveries
Revises: 012_add_wishlists
Create Date: 2026-07-12

An order can be fulfilled in several trips. A ``delivery`` groups part (or all) of
an order's items with its own status and schedule; ``delivery_items`` link a
delivery to the order items it carries, with a quantity. Deliveries are created
lazily (existing single-delivery orders keep working with no delivery rows until
staff create one), so no data backfill is needed here.

Each statement is a separate ``op.execute()`` because asyncpg cannot run
multi-statement SQL in a single execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "013_add_deliveries"
down_revision: str | None = "012_add_wishlists"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the deliveries and delivery_items tables."""
    op.execute(
        """
        CREATE TABLE deliveries (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
            code VARCHAR(30) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            scheduled_at TIMESTAMPTZ,
            delivered_at TIMESTAMPTZ,
            notes TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_deliveries_status CHECK (
                status IN ('pending', 'shipping', 'delivered', 'cancelled')
            )
        )
        """
    )
    op.execute("CREATE INDEX idx_deliveries_order ON deliveries(order_id)")
    op.execute(
        """
        CREATE TABLE delivery_items (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            delivery_id UUID NOT NULL REFERENCES deliveries(id) ON DELETE CASCADE,
            order_item_id UUID NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
            quantity INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_delivery_items_quantity CHECK (quantity > 0),
            CONSTRAINT uq_delivery_items_delivery_order_item UNIQUE (delivery_id, order_item_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_delivery_items_delivery ON delivery_items(delivery_id)")
    op.execute("COMMENT ON TABLE deliveries IS 'One fulfilment trip for part or all of an order'")
    # Match the RLS baseline of the original tables (migration 001). The backend
    # role bypasses RLS; enabling it with no policy denies anon/PostgREST direct
    # access to these backend-only tables.
    op.execute("ALTER TABLE deliveries ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE delivery_items ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Drop the delivery tables."""
    op.execute("DROP TABLE IF EXISTS delivery_items")
    op.execute("DROP TABLE IF EXISTS deliveries")
