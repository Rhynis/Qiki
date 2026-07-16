"""Add a unique index on (order_id, code) for deliveries.

Revision ID: 019_harden_delivery_allocation
Revises: 018_add_product_variants
Create Date: 2026-07-15

Backstops the delivery-code generation: even if two concurrent create_delivery
calls raced, the database now rejects a duplicate code within one order. The
service also locks the order row (SELECT ... FOR UPDATE) so codes are generated
safely under the lock. Index only (existing table), so no RLS change is needed.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "019_harden_delivery_allocation"
down_revision: str | None = "018_add_product_variants"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the unique (order_id, code) index on deliveries."""
    op.execute("CREATE UNIQUE INDEX uq_deliveries_order_id_code ON deliveries (order_id, code)")


def downgrade() -> None:
    """Drop the unique (order_id, code) index."""
    op.execute("DROP INDEX uq_deliveries_order_id_code")
