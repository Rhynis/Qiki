"""Product database model."""

from decimal import Decimal

from sqlalchemy import Boolean, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class Product(Base, UUIDMixin, TimestampMixin):
    """Gas LPG product available for sale."""

    __tablename__ = "products"

    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    size_kg: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="gas", nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="kg", nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    def is_in_stock(self) -> bool:
        """Return whether product has available stock."""
        return self.stock_quantity > 0

    def is_low_stock(self, threshold: int = 10) -> bool:
        """Return whether product stock is low but still available."""
        return 0 < self.stock_quantity <= threshold

    def get_display_name(self) -> str:
        """Return a customer-friendly display name."""
        size_text = f"{self.size_kg.normalize():f}".rstrip("0").rstrip(".")
        return f"{self.brand} {self.name} {size_text} {self.unit}"
