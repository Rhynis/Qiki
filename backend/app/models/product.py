"""Product database model."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class ProductParent(Base, UUIDMixin, TimestampMixin):
    """A parent product that groups one or more sellable variants.

    A parent carries the shared marketing metadata (name, brand, category,
    description, image) while each ``Product`` row underneath it remains the
    priced and stocked entity referenced by carts, orders and the chatbot.
    """

    __tablename__ = "product_parents"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="gas", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    variants: Mapped[list["Product"]] = relationship(
        "Product",
        back_populates="parent",
        lazy="selectin",
        order_by="Product.price",
    )


class Product(Base, UUIDMixin, TimestampMixin):
    """Gas LPG product variant available for sale.

    Each row is a concrete, priced and stocked variant (e.g. a specific colour
    or cylinder size). Variants are grouped under a :class:`ProductParent` via
    ``parent_id`` so the storefront can show one product page with selectable
    options while carts, orders and the chatbot keep referencing this exact row.
    """

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
    long_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    safety_info: Mapped[str | None] = mapped_column(Text, nullable=True)
    pricing_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("product_parents.id", ondelete="SET NULL"),
        nullable=True,
    )
    colour: Mapped[str | None] = mapped_column(String(50), nullable=True)
    variant_label: Mapped[str | None] = mapped_column(String(100), nullable=True)

    parent: Mapped["ProductParent | None"] = relationship(
        "ProductParent",
        back_populates="variants",
        lazy="select",
    )

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
