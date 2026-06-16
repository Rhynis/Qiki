"""Add email_verified flag to users.

Revision ID: 006_add_email_verified
Revises: 005_phone_first_auth
Create Date: 2026-06-16

Tracks whether a customer's optional email has been confirmed via an emailed
OTP. Defaults to FALSE so existing rows are unverified; the column is NOT NULL
with a server default, which is a safe single-statement add for asyncpg.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "006_add_email_verified"
down_revision: str | None = "005_phone_first_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add the email_verified column (default FALSE)."""
    op.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute(
        "COMMENT ON COLUMN users.email_verified IS "
        "'Whether the optional email was confirmed via an emailed OTP'"
    )


def downgrade() -> None:
    """Drop the email_verified column."""
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verified")
