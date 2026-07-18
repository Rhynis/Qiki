"""Add admin_audit_logs table for admin-in-chat catalog mutations.

Revision ID: 021_add_admin_audit_logs
Revises: 020_split_price_alert_tokens
Create Date: 2026-07-18

Records every catalog mutation an admin triggers through the chat assistant
(who/what/before/after). Each statement runs in its own ``op.execute()`` because
asyncpg cannot run multi-statement SQL in one execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "021_add_admin_audit_logs"
down_revision: str | None = "020_split_price_alert_tokens"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the admin_audit_logs table and its index."""
    op.execute(
        "CREATE TABLE admin_audit_logs ("
        "id UUID PRIMARY KEY DEFAULT uuid_generate_v4(), "
        "admin_id UUID REFERENCES users(id) ON DELETE SET NULL, "
        "action VARCHAR(50) NOT NULL, "
        "target_type VARCHAR(50) NOT NULL, "
        "target_id UUID, "
        "before JSONB NOT NULL DEFAULT '{}'::jsonb, "
        "after JSONB NOT NULL DEFAULT '{}'::jsonb, "
        "created_at TIMESTAMPTZ NOT NULL DEFAULT now(), "
        "updated_at TIMESTAMPTZ NOT NULL DEFAULT now()"
        ")"
    )
    op.execute("CREATE INDEX ix_admin_audit_logs_admin_id ON admin_audit_logs (admin_id)")
    # Match the RLS baseline of the original tables (migration 001). The backend
    # role bypasses RLS; enabling it with no policy denies anon/PostgREST direct
    # access to this backend-only audit table.
    op.execute("ALTER TABLE admin_audit_logs ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    """Drop the admin_audit_logs table (index drops with it)."""
    op.execute("DROP TABLE admin_audit_logs")
