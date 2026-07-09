"""Conversation model for chatbot sessions."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.message import Message


class Conversation(Base, UUIDMixin, TimestampMixin):
    """A customer chat conversation."""

    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    session_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Human-friendly code (CT-YYYYMMDD-NNN), filled by a DB trigger on insert.
    code: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    escalated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    satisfaction_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)

    messages: Mapped[list[Message]] = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Message.created_at",
    )

    def is_escalated(self) -> bool:
        """Return whether the conversation is waiting for staff."""
        return self.status == "escalated"

    def is_active(self) -> bool:
        """Return whether the conversation can receive bot messages."""
        return self.status == "active"

    def turn_count(self) -> int:
        """Return the number of stored messages."""
        return len(self.messages)
