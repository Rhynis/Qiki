"""Price-alert email subscription model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PriceSubscription(Base, UUIDMixin, TimestampMixin):
    """A double-opt-in subscription to gas-price-change email alerts.

    Supports both logged-in users (``user_id`` set) and guest emails. ``token``
    is an opaque secret used for both the confirm and unsubscribe links.
    ``confirmed`` gates whether the address may receive notifications, and a
    non-null ``unsubscribed_at`` permanently opts the row out (a later
    resubscribe creates a fresh row).
    """

    __tablename__ = "price_subscriptions"

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    token: Mapped[str] = mapped_column(String(64), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    unsubscribed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_price_subscriptions_token", "token", unique=True),
        Index(
            "uq_price_subscriptions_active_email",
            "email",
            unique=True,
            postgresql_where=text("unsubscribed_at IS NULL"),
        ),
        Index(
            "ix_price_subscriptions_confirmed",
            "confirmed",
            postgresql_where=text("unsubscribed_at IS NULL"),
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PriceSubscription id={self.id} email={self.email!r} " f"confirmed={self.confirmed}>"
        )
