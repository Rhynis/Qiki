"""Add price_subscriptions table for gas-price-change email alerts.

Revision ID: 015_add_price_subscriptions
Revises: 014_add_order_einvoice
Create Date: 2026-07-12

Stores double-opt-in subscriptions (logged-in users and guest emails) for the
monthly gas-price-change notification. Each statement runs in its own
``op.execute()`` because asyncpg cannot run multi-statement SQL in one execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "015_add_price_subscriptions"
down_revision: str | None = "014_add_order_einvoice"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the price_subscriptions table and its indexes."""
    op.execute(
        "CREATE TABLE price_subscriptions ("
        "id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), "
        "email VARCHAR(255) NOT NULL, "
        "user_id UUID REFERENCES users(id) ON DELETE SET NULL, "
        "confirmed BOOLEAN NOT NULL DEFAULT false, "
        "token VARCHAR(64) NOT NULL, "
        "confirmed_at TIMESTAMPTZ, "
        "unsubscribed_at TIMESTAMPTZ, "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    op.execute("CREATE UNIQUE INDEX uq_price_subscriptions_token " "ON price_subscriptions (token)")
    # One active subscription per email; a resubscribe after unsubscribe is allowed
    # because unsubscribed rows fall out of this partial unique index.
    op.execute(
        "CREATE UNIQUE INDEX uq_price_subscriptions_active_email "
        "ON price_subscriptions (email) WHERE unsubscribed_at IS NULL"
    )
    op.execute(
        "CREATE INDEX ix_price_subscriptions_confirmed "
        "ON price_subscriptions (confirmed) WHERE unsubscribed_at IS NULL"
    )
    # Match the RLS baseline of the original tables (migration 001). The backend
    # role bypasses RLS; enabling it with no policy denies anon/PostgREST direct
    # access to this backend-only table (which also holds guest emails).
    op.execute("ALTER TABLE price_subscriptions ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Drop the price_subscriptions table (indexes drop with it)."""
    op.execute("DROP TABLE price_subscriptions")
