"""Add a driver role and driver assignment + last location to deliveries.

Revision ID: 016_add_driver_role
Revises: 015_add_price_subscriptions
Create Date: 2026-07-13

Adds the 'driver' user role, a nullable ``driver_id`` on deliveries (who is
carrying the trip), a 'failed' delivery status, and an optional browser-reported
last location. Each statement runs in its own ``op.execute()`` (asyncpg cannot
run multi-statement SQL).
"""

from collections.abc import Sequence

from alembic import op

revision: str = "016_add_driver_role"
down_revision: str | None = "015_add_price_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the driver role, driver assignment, failed status, and last location."""
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_role")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('customer', 'staff', 'admin', 'driver'))"
    )
    op.execute(
        "ALTER TABLE deliveries ADD COLUMN driver_id UUID "
        "REFERENCES users(id) ON DELETE SET NULL"
    )
    op.execute("ALTER TABLE deliveries ADD COLUMN last_lat DOUBLE PRECISION")
    op.execute("ALTER TABLE deliveries ADD COLUMN last_lng DOUBLE PRECISION")
    op.execute("CREATE INDEX ix_deliveries_driver_id ON deliveries (driver_id)")
    op.execute("ALTER TABLE deliveries DROP CONSTRAINT ck_deliveries_status")
    op.execute(
        "ALTER TABLE deliveries ADD CONSTRAINT ck_deliveries_status "
        "CHECK (status IN ('pending', 'shipping', 'delivered', 'failed', 'cancelled'))"
    )


def downgrade() -> None:
    """Reverse the driver-role additions (fails if driver/failed rows exist)."""
    op.execute("ALTER TABLE deliveries DROP CONSTRAINT ck_deliveries_status")
    op.execute(
        "ALTER TABLE deliveries ADD CONSTRAINT ck_deliveries_status "
        "CHECK (status IN ('pending', 'shipping', 'delivered', 'cancelled'))"
    )
    op.execute("DROP INDEX ix_deliveries_driver_id")
    op.execute("ALTER TABLE deliveries DROP COLUMN last_lng")
    op.execute("ALTER TABLE deliveries DROP COLUMN last_lat")
    op.execute("ALTER TABLE deliveries DROP COLUMN driver_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_role")
    op.execute(
        "ALTER TABLE users ADD CONSTRAINT ck_users_role "
        "CHECK (role IN ('customer', 'staff', 'admin'))"
    )
