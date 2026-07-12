"""Order database models."""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.delivery import Delivery


class Order(Base, UUIDMixin, TimestampMixin):
    """Customer order with embedded delivery and payment details."""

    __tablename__ = "orders"

    order_number: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    delivery_address: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_city: Mapped[str] = mapped_column(
        String(100),
        default="TP. Hồ Chí Minh",
        nullable=False,
    )
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    different_recipient_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    different_recipient_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    shipping_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    vat_invoice_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    vat_info: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    payment_method: Mapped[str] = mapped_column(String(20), default="cod", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    source: Mapped[str] = mapped_column(String(20), default="website", nullable=False)
    referral_conversation_id: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True), nullable=True
    )
    idempotency_key: Mapped[UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        unique=True,
        nullable=True,
    )
    customer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    internal_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    deliveries: Mapped[list["Delivery"]] = relationship(
        "Delivery",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Delivery.created_at",
    )

    if TYPE_CHECKING:
        user: Mapped[Any]

    def is_guest_order(self) -> bool:
        """Return whether this order belongs to a guest checkout."""
        return self.user_id is None

    def can_be_cancelled(self) -> bool:
        """Return whether the order status allows cancellation."""
        return self.status in {"pending", "confirmed"}

    def get_recipient_name(self) -> str:
        """Return the delivery recipient name."""
        return self.different_recipient_name or self.customer_name

    def get_recipient_phone(self) -> str:
        """Return the delivery recipient phone."""
        return self.different_recipient_phone or self.customer_phone


class OrderItem(Base, UUIDMixin):
    """Order line item with product snapshot fields."""

    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    product_brand: Mapped[str | None] = mapped_column(String(100), nullable=True)
    product_size_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    is_exchange: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    order: Mapped[Order] = relationship("Order", back_populates="items")
