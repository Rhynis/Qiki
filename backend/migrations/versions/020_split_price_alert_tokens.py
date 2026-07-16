"""Split the price-subscription token into confirm + unsubscribe tokens.

Revision ID: 020_split_price_alert_tokens
Revises: 019_harden_delivery_allocation
Create Date: 2026-07-15

Replaces the single dual-purpose ``token`` with a single-purpose ``confirm_token``
(with a ``confirm_expires_at`` expiry) and ``unsubscribe_token``, so a confirm
link cannot unsubscribe and vice-versa, and confirm links expire. Each statement
runs in its own ``op.execute()`` (asyncpg). No new table, so RLS is unchanged.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "020_split_price_alert_tokens"
down_revision: str | None = "019_harden_delivery_allocation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add confirm/unsubscribe tokens + expiry; drop the dual-purpose token."""
    op.execute("ALTER TABLE price_subscriptions ADD COLUMN confirm_token VARCHAR(64)")
    op.execute("ALTER TABLE price_subscriptions ADD COLUMN unsubscribe_token VARCHAR(64)")
    op.execute("ALTER TABLE price_subscriptions ADD COLUMN confirm_expires_at TIMESTAMPTZ")
    # Backfill existing rows: reuse the old token as the confirm token, derive a
    # distinct unsubscribe token from the (unique) id, and give confirm a 7-day window.
    op.execute(
        "UPDATE price_subscriptions SET "
        "confirm_token = token, "
        "unsubscribe_token = md5(id::text || 'price-alert-unsubscribe'), "
        "confirm_expires_at = created_at + interval '7 days' "
        "WHERE confirm_token IS NULL"
    )
    op.execute("ALTER TABLE price_subscriptions ALTER COLUMN confirm_token SET NOT NULL")
    op.execute("ALTER TABLE price_subscriptions ALTER COLUMN unsubscribe_token SET NOT NULL")
    op.execute("DROP INDEX uq_price_subscriptions_token")
    op.execute("ALTER TABLE price_subscriptions DROP COLUMN token")
    op.execute(
        "CREATE UNIQUE INDEX uq_price_subscriptions_confirm_token "
        "ON price_subscriptions (confirm_token)"
    )
    op.execute(
        "CREATE UNIQUE INDEX uq_price_subscriptions_unsubscribe_token "
        "ON price_subscriptions (unsubscribe_token)"
    )


def downgrade() -> None:
    """Restore the single dual-purpose token column."""
    op.execute("ALTER TABLE price_subscriptions ADD COLUMN token VARCHAR(64)")
    op.execute("UPDATE price_subscriptions SET token = confirm_token WHERE token IS NULL")
    op.execute("ALTER TABLE price_subscriptions ALTER COLUMN token SET NOT NULL")
    op.execute("DROP INDEX uq_price_subscriptions_unsubscribe_token")
    op.execute("DROP INDEX uq_price_subscriptions_confirm_token")
    op.execute("CREATE UNIQUE INDEX uq_price_subscriptions_token ON price_subscriptions (token)")
    op.execute("ALTER TABLE price_subscriptions DROP COLUMN confirm_expires_at")
    op.execute("ALTER TABLE price_subscriptions DROP COLUMN unsubscribe_token")
    op.execute("ALTER TABLE price_subscriptions DROP COLUMN confirm_token")
