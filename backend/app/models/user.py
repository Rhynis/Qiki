"""User database model."""

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class User(Base, UUIDMixin, TimestampMixin):
    """User account: customer, staff, or admin.

    Phone-first: ``phone`` is the primary login identifier (required at the API
    layer, unique where present). ``email`` is optional (nullable, unique where
    present). Both uniqueness rules are partial indexes so legacy rows without a
    phone/email do not collide on NULL.
    """

    __tablename__ = "users"

    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_ward: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(
        String(100), nullable=True, server_default="TP. Hồ Chí Minh"
    )
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index(
            "uq_users_email",
            "email",
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
        Index(
            "uq_users_phone",
            "phone",
            unique=True,
            postgresql_where=text("phone IS NOT NULL"),
        ),
    )

    if TYPE_CHECKING:
        orders: Mapped[list[Any]]
        conversations: Mapped[list[Any]]

    def __repr__(self) -> str:
        return f"<User {self.email} ({self.role})>"

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_staff(self) -> bool:
        return self.role in ("staff", "admin")

    def is_customer(self) -> bool:
        return self.role == "customer"

    def is_driver(self) -> bool:
        return self.role in ("driver", "admin")
