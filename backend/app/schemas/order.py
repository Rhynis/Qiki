"""Order schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.core.input_validation import VietnamesePhoneValidator, VietnameseTaxCodeValidator
from app.schemas.delivery import DeliveryResponse

OrderStatus = Literal["pending", "confirmed", "shipping", "delivered", "cancelled"]
PaymentMethod = Literal["cod", "bank_transfer"]
PaymentStatus = Literal["pending", "paid", "refunded"]
OrderSource = Literal["website", "chatbot"]


class OrderItemCreate(BaseModel):
    """Order item submitted during checkout."""

    product_id: UUID
    quantity: int = Field(ge=1, le=100)
    is_exchange: bool = False


class OrderItemResponse(BaseModel):
    """Order line item response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    product_id: UUID | None
    product_name: str
    product_brand: str | None
    product_size_kg: Decimal | None
    quantity: int
    unit_price: Decimal
    subtotal: Decimal
    is_exchange: bool
    created_at: datetime


class VatInfo(BaseModel):
    """VAT invoice information."""

    company_name: str = Field(min_length=2, max_length=255)
    tax_code: str
    address: str = Field(min_length=5, max_length=500)

    @field_validator("tax_code")
    @classmethod
    def validate_tax_code(cls, value: str) -> str:
        return VietnameseTaxCodeValidator.validate(value)


class CheckoutRequest(BaseModel):
    """Checkout payload for guest and authenticated orders."""

    items: list[OrderItemCreate] = Field(min_length=1)
    customer_name: str = Field(min_length=2, max_length=255)
    customer_phone: str
    customer_email: EmailStr | None = None
    delivery_address: str = Field(min_length=5, max_length=500)
    delivery_ward: str | None = Field(default=None, max_length=100)
    delivery_district: str | None = Field(default=None, max_length=100)
    delivery_city: str = Field(default="TP. Hồ Chí Minh", min_length=2, max_length=100)
    delivery_notes: str | None = Field(default=None, max_length=1000)
    different_recipient_name: str | None = Field(default=None, min_length=2, max_length=255)
    different_recipient_phone: str | None = None
    payment_method: PaymentMethod = "cod"
    vat_invoice_requested: bool = False
    vat_info: VatInfo | None = None
    customer_notes: str | None = Field(default=None, max_length=1000)
    source: OrderSource = "website"
    referral_conversation_id: UUID | None = None

    @field_validator("customer_phone", "different_recipient_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return VietnamesePhoneValidator.validate(value)

    @model_validator(mode="after")
    def validate_dependent_fields(self) -> "CheckoutRequest":
        """Validate fields that must be provided together."""
        has_recipient_name = self.different_recipient_name is not None
        has_recipient_phone = self.different_recipient_phone is not None
        if has_recipient_name != has_recipient_phone:
            raise ValueError(
                "different_recipient_name and different_recipient_phone must be set together"
            )
        if self.vat_invoice_requested and self.vat_info is None:
            raise ValueError("vat_info is required when vat_invoice_requested is true")
        if not self.vat_invoice_requested and self.vat_info is not None:
            raise ValueError("vat_info is only allowed when vat_invoice_requested is true")
        return self


class OrderResponse(BaseModel):
    """Order response with line items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    user_id: UUID | None
    customer_name: str
    customer_phone: str
    customer_email: str | None
    delivery_address: str
    delivery_ward: str | None
    delivery_district: str | None
    delivery_city: str
    delivery_notes: str | None
    different_recipient_name: str | None
    different_recipient_phone: str | None
    subtotal: Decimal
    shipping_fee: Decimal
    total_amount: Decimal
    vat_invoice_requested: bool
    vat_info: VatInfo | None
    einvoice: dict[str, Any] | None = None
    payment_method: PaymentMethod
    payment_status: PaymentStatus
    status: OrderStatus
    source: OrderSource
    referral_conversation_id: UUID | None
    customer_notes: str | None
    internal_notes: str | None
    cancelled_at: datetime | None
    cancelled_reason: str | None
    delivered_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemResponse]
    deliveries: list[DeliveryResponse] = Field(default_factory=list)


class OrderListResponse(BaseModel):
    """Paginated order response."""

    items: list[OrderResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class OrderStatusUpdate(BaseModel):
    """Admin status update payload."""

    new_status: OrderStatus
    notes: str | None = Field(default=None, max_length=1000)


class GuestOrderLookup(BaseModel):
    """Public guest lookup payload."""

    order_number: str = Field(min_length=8, max_length=20)
    phone: str

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return VietnamesePhoneValidator.validate(value)


class OrderCancelRequest(BaseModel):
    """Order cancellation payload."""

    reason: str | None = Field(default=None, max_length=1000)
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return None
        return VietnamesePhoneValidator.validate(value)


class OrderSearchParams(BaseModel):
    """Order list filters."""

    status: OrderStatus | None = None
    source: OrderSource | None = None
    search: str | None = Field(default=None, max_length=255)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)


class SkippedReorderItem(BaseModel):
    """A past-order line that could not be re-added to the cart."""

    product_id: UUID | None
    product_name: str
    reason: Literal["inactive", "out_of_stock", "not_found"]


class ReorderItem(BaseModel):
    """A cart line rebuilt from a past order at the current price."""

    product_id: UUID
    sku: str
    name: str
    brand: str
    size_kg: Decimal
    category: str
    unit: str
    price: Decimal
    quantity: int
    image_url: str | None
    stock_quantity: int


class ReorderResponse(BaseModel):
    """Result of rebuilding a cart from a past order.

    ``items`` carries the products still purchasable at their current price and
    stock; ``skipped`` explains any line that was dropped because the product is
    now inactive or out of stock, so the UI can warn the customer.
    """

    items: list[ReorderItem]
    skipped: list[SkippedReorderItem]
