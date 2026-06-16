"""Phone-first accounts: phone unique, email optional + nullable-unique.

Revision ID: 005_phone_first_auth
Revises: 004_product_category_unit
Create Date: 2026-06-16

Phone becomes the primary login identifier (unique where present) while email is
made optional. To stay safe for legacy rows we use partial unique indexes
(``WHERE ... IS NOT NULL``) instead of a NOT NULL backfill, so existing rows that
lack a phone or email never collide on NULL. Each statement is its own
``op.execute()`` because asyncpg rejects multi-statement strings.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "005_phone_first_auth"
down_revision: str | None = "004_product_category_unit"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Make email nullable-unique and add a unique-where-not-null index on phone."""
    # Email becomes optional and its uniqueness tolerates NULL.
    op.execute("ALTER TABLE users ALTER COLUMN email DROP NOT NULL")
    op.execute("ALTER TABLE users DROP CONSTRAINT IF EXISTS users_email_key")
    op.execute("DROP INDEX IF EXISTS idx_users_email")
    op.execute("CREATE UNIQUE INDEX uq_users_email ON users(email) WHERE email IS NOT NULL")
    # Phone becomes the unique login identifier (still nullable for legacy safety).
    op.execute("DROP INDEX IF EXISTS idx_users_phone")
    op.execute("CREATE UNIQUE INDEX uq_users_phone ON users(phone) WHERE phone IS NOT NULL")


def downgrade() -> None:
    """Restore the email-as-identifier schema (NOT NULL + plain unique)."""
    op.execute("DROP INDEX IF EXISTS uq_users_phone")
    op.execute("CREATE INDEX idx_users_phone ON users(phone) WHERE phone IS NOT NULL")
    op.execute("DROP INDEX IF EXISTS uq_users_email")
    op.execute("ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email)")
    op.execute("CREATE INDEX idx_users_email ON users(email)")
    op.execute("ALTER TABLE users ALTER COLUMN email SET NOT NULL")
