"""Add an einvoice JSONB column to orders (e-invoice adapter stub).

Revision ID: 014_add_order_einvoice
Revises: 013_add_deliveries
Create Date: 2026-07-12

Stores the result of issuing a legal e-invoice for an order (invoice number,
provider, status, pdf url / payload, issued_at). The default provider is a local
Noop stub, so this only records what would be issued until a real provider is
connected.

Each statement is a separate ``op.execute()`` (asyncpg cannot run multi-statement
SQL in one execute).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "014_add_order_einvoice"
down_revision: str | None = "013_add_deliveries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the einvoice column."""
    op.execute("ALTER TABLE orders ADD COLUMN einvoice JSONB")
    op.execute(
        "COMMENT ON COLUMN orders.einvoice IS 'Issued e-invoice result (see EInvoiceService)'"
    )


def downgrade() -> None:
    """Drop the einvoice column."""
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS einvoice")
