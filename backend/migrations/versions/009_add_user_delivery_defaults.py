"""Add default delivery fields to users.

Revision ID: 009_add_user_delivery_defaults
Revises: 008_add_bge_embedding
Create Date: 2026-07-05

Lets a logged-in customer save default delivery info (ward, city, notes) once so
checkout and the Qiki chat can prefill it. ``users.address`` already stores the
street line. Each column is added with its own statement so asyncpg (which cannot
run multi-statement SQL in one execute) accepts the migration.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "009_add_user_delivery_defaults"
down_revision: str | None = "008_add_bge_embedding"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the default-delivery columns."""
    op.execute("ALTER TABLE users ADD COLUMN delivery_ward VARCHAR(100)")
    op.execute("ALTER TABLE users ADD COLUMN delivery_city VARCHAR(100) DEFAULT 'TP. Hồ Chí Minh'")
    op.execute("ALTER TABLE users ADD COLUMN delivery_notes TEXT")
    op.execute("COMMENT ON COLUMN users.delivery_ward IS 'Default delivery ward/commune'")
    op.execute("COMMENT ON COLUMN users.delivery_city IS 'Default delivery city'")
    op.execute("COMMENT ON COLUMN users.delivery_notes IS 'Default delivery notes'")


def downgrade() -> None:
    """Drop the default-delivery columns."""
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS delivery_notes")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS delivery_city")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS delivery_ward")
