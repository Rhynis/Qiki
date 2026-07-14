"""Coupon and redemption database models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Coupon(Base, UUIDMixin, TimestampMixin):
    """Discount code managed by admins and applied server-side at checkout."""

    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    discount_type: Mapped[str] = mapped_column(String(10), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    min_order: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    max_discount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    usage_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    per_user_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    redemptions: Mapped[list["CouponRedemption"]] = relationship(
        "CouponRedemption",
        back_populates="coupon",
        cascade="all, delete-orphan",
    )


class CouponRedemption(Base, UUIDMixin):
    """One recorded use of a coupon, linked to a user and/or order."""

    __tablename__ = "coupon_redemptions"
    __table_args__ = (UniqueConstraint("order_id", name="uq_coupon_redemptions_order_id"),)

    coupon_id: Mapped[UUID] = mapped_column(
        ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    order_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    coupon: Mapped[Coupon] = relationship("Coupon", back_populates="redemptions")
