"""Widen the conversation status check constraint to allow flagged/closed.

Revision ID: 011_widen_conversation_status
Revises: 010_add_conversation_code
Create Date: 2026-07-09

Migration 001 created ``ck_conversations_status`` allowing only
('active', 'escalated', 'resolved', 'abandoned'). The staff status control and
the auto-close sweep added in the admin-chat work set 'flagged' and 'closed',
which the old constraint rejects. Widen it. Each statement runs in its own
``op.execute()`` because asyncpg cannot run multi-statement SQL in one execute.
"""

from collections.abc import Sequence

from alembic import op

revision: str = "011_widen_conversation_status"
down_revision: str | None = "010_add_conversation_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Allow the 'flagged' and 'closed' conversation statuses."""
    op.execute("ALTER TABLE conversations DROP CONSTRAINT ck_conversations_status")
    op.execute(
        "ALTER TABLE conversations ADD CONSTRAINT ck_conversations_status "
        "CHECK (status IN ('active', 'escalated', 'flagged', 'resolved', 'closed', 'abandoned'))"
    )


def downgrade() -> None:
    """Restore the original status set (fails if flagged/closed rows exist)."""
    op.execute("ALTER TABLE conversations DROP CONSTRAINT ck_conversations_status")
    op.execute(
        "ALTER TABLE conversations ADD CONSTRAINT ck_conversations_status "
        "CHECK (status IN ('active', 'escalated', 'resolved', 'abandoned'))"
    )
