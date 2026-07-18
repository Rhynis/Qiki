"""Audit-log model for admin-in-chat catalog mutations."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AdminAuditLog(Base, UUIDMixin, TimestampMixin):
    """One row per admin-chat mutation, capturing who/what/before/after.

    Every catalog change an admin triggers through the chat assistant is recorded
    here after the mutation succeeds. ``before`` and ``after`` are JSON snapshots
    of only the fields the action changed, so a reviewer can reconstruct exactly
    what a given command did.
    """

    __tablename__ = "admin_audit_logs"

    admin_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    before: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)

    __table_args__ = (Index("ix_admin_audit_logs_admin_id", "admin_id"),)

    def __repr__(self) -> str:
        return (
            f"<AdminAuditLog id={self.id} admin_id={self.admin_id} "
            f"action={self.action!r} target_id={self.target_id}>"
        )
