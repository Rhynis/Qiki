"""Add coupons, coupon_redemptions, and order discount columns.

Revision ID: 016_add_coupons
Revises: 015_add_price_subscriptions
Create Date: 2026-07-12

Adds admin-managed discount codes applied server-side at checkout. Coupons carry
percent/fixed values with min-order gates, usage caps, and an active window;
coupon_redemptions records each use. Orders gain a discount amount plus the applied
coupon reference. Each statement runs in its own ``op.execute()`` because asyncpg
cannot run multi-statement SQL in one execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "016_add_coupons"
down_revision: str | None = "015_add_price_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create coupon tables and add discount columns to orders."""
    op.execute(
        """
        CREATE TABLE coupons (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            code VARCHAR(50) UNIQUE NOT NULL,
            discount_type VARCHAR(10) NOT NULL
                CONSTRAINT ck_coupons_discount_type CHECK (discount_type IN ('percent', 'fixed')),
            value NUMERIC(10,2) NOT NULL CONSTRAINT ck_coupons_value CHECK (value > 0),
            min_order NUMERIC(10,2) NOT NULL DEFAULT 0
                CONSTRAINT ck_coupons_min_order CHECK (min_order >= 0),
            max_discount NUMERIC(10,2)
                CONSTRAINT ck_coupons_max_discount CHECK (max_discount IS NULL OR max_discount > 0),
            usage_limit INTEGER
                CONSTRAINT ck_coupons_usage_limit CHECK (usage_limit IS NULL OR usage_limit >= 1),
            used_count INTEGER NOT NULL DEFAULT 0
                CONSTRAINT ck_coupons_used_count CHECK (used_count >= 0),
            per_user_limit INTEGER
                CONSTRAINT ck_coupons_per_user_limit CHECK (per_user_limit IS NULL OR per_user_limit >= 1),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            starts_at TIMESTAMPTZ,
            ends_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX idx_coupons_code ON coupons(code)")
    op.execute("CREATE INDEX idx_coupons_active ON coupons(active)")
    op.execute("COMMENT ON TABLE coupons IS 'Admin-managed discount codes applied at checkout'")

    op.execute(
        """
        CREATE TABLE coupon_redemptions (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            coupon_id UUID NOT NULL REFERENCES coupons(id) ON DELETE CASCADE,
            user_id UUID REFERENCES users(id),
            order_id UUID REFERENCES orders(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_coupon_redemptions_order_id UNIQUE (order_id)
        )
        """
    )
    op.execute("CREATE INDEX idx_coupon_redemptions_coupon_id ON coupon_redemptions(coupon_id)")
    op.execute(
        "CREATE INDEX idx_coupon_redemptions_user_id ON coupon_redemptions(user_id) "
        "WHERE user_id IS NOT NULL"
    )
    op.execute("COMMENT ON TABLE coupon_redemptions IS 'One recorded use of a coupon per order'")

    op.execute(
        "ALTER TABLE orders ADD COLUMN discount_amount NUMERIC(10,2) NOT NULL DEFAULT 0 "
        "CONSTRAINT ck_orders_discount_amount CHECK (discount_amount >= 0)"
    )
    op.execute("ALTER TABLE orders ADD COLUMN coupon_id UUID REFERENCES coupons(id)")
    op.execute("ALTER TABLE orders ADD COLUMN coupon_code VARCHAR(50)")


def downgrade() -> None:
    """Drop discount columns and coupon tables."""
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS coupon_code")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS coupon_id")
    op.execute("ALTER TABLE orders DROP COLUMN IF EXISTS discount_amount")
    op.execute("DROP TABLE IF EXISTS coupon_redemptions")
    op.execute("DROP TABLE IF EXISTS coupons")
