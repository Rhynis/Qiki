"""Product schemas."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

ALLOWED_SIZES = {Decimal("6"), Decimal("12"), Decimal("45")}
SKU_PATTERN = re.compile(r"^[A-Z0-9-]+$")
ProductCategory = Literal["gas", "nuoc_uong"]
ProductUnit = Literal["kg", "lít"]


def validate_gas_size(value: Decimal | None, category: str | None) -> Decimal | None:
    """Validate supported LPG cylinder sizes for gas products."""
    if category == "gas" and value is not None and value not in ALLOWED_SIZES:
        raise ValueError("size_kg must be one of 6, 12, or 45")
    return value


def validate_sale_price(sale_price: Decimal | None, price: Decimal | None) -> None:
    """A sale price, when set, must be a positive discount below the list price."""
    if sale_price is None:
        return
    if sale_price <= 0:
        raise ValueError("sale_price must be greater than 0")
    if price is not None and sale_price >= price:
        raise ValueError("sale_price must be less than the list price")


class ProductBase(BaseModel):
    """Shared product fields."""

    name: str = Field(min_length=1, max_length=255)
    brand: str = Field(min_length=1, max_length=100)
    size_kg: Decimal
    category: ProductCategory = "gas"
    unit: ProductUnit = "kg"
    price: Decimal = Field(gt=0)
    sale_price: Decimal | None = None
    description: str | None = None
    long_description: str | None = None
    image_url: HttpUrl | None = None
    safety_info: str | None = None
    pricing_note: str | None = None
    parent_id: UUID | None = None
    colour: str | None = Field(default=None, max_length=50)
    variant_label: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_product_category(self) -> "ProductBase":
        """Validate category-dependent product fields."""
        validate_gas_size(self.size_kg, self.category)
        if self.category == "gas" and self.pricing_note:
            raise ValueError("pricing_note is only supported for nuoc_uong products")
        validate_sale_price(self.sale_price, self.price)
        return self


class ProductCreate(ProductBase):
    """Product creation payload."""

    sku: str = Field(min_length=1, max_length=50)
    stock_quantity: int = Field(ge=0)

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str) -> str:
        normalized = value.upper().strip()
        if not SKU_PATTERN.match(normalized):
            raise ValueError("sku must contain only uppercase letters, numbers, and dashes")
        return normalized


class ProductUpdate(BaseModel):
    """Product update payload."""

    sku: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    size_kg: Decimal | None = None
    category: ProductCategory | None = None
    unit: ProductUnit | None = None
    price: Decimal | None = Field(default=None, gt=0)
    sale_price: Decimal | None = None
    description: str | None = None
    long_description: str | None = None
    image_url: HttpUrl | None = None
    safety_info: str | None = None
    pricing_note: str | None = None
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    parent_id: UUID | None = None
    colour: str | None = Field(default=None, max_length=50)
    variant_label: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def validate_product_category(self) -> "ProductUpdate":
        """Validate category-dependent product fields."""
        category = self.category or "gas"
        validate_gas_size(self.size_kg, category)
        if category == "gas" and self.pricing_note:
            raise ValueError("pricing_note is only supported for nuoc_uong products")
        validate_sale_price(self.sale_price, self.price)
        return self

    @field_validator("sku")
    @classmethod
    def normalize_sku(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.upper().strip()
        if not SKU_PATTERN.match(normalized):
            raise ValueError("sku must contain only uppercase letters, numbers, and dashes")
        return normalized


class ProductResponse(ProductCreate):
    """Product API response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ProductListResponse(BaseModel):
    """Paginated product list response."""

    items: list[ProductResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class BestSellerProduct(ProductResponse):
    """An active product annotated with its total ordered quantity."""

    total_sold: int


class RecommendedProduct(ProductResponse):
    """An active product annotated with its recommendation score and reason."""

    score: float
    reason: str


class ProductParentBase(BaseModel):
    """Shared parent product fields."""

    name: str = Field(min_length=1, max_length=255)
    brand: str = Field(min_length=1, max_length=100)
    category: ProductCategory = "gas"
    description: str | None = None
    long_description: str | None = None
    image_url: HttpUrl | None = None


class ProductParentCreate(ProductParentBase):
    """Parent product creation payload."""


class ProductParentUpdate(BaseModel):
    """Parent product update payload."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    brand: str | None = Field(default=None, min_length=1, max_length=100)
    category: ProductCategory | None = None
    description: str | None = None
    long_description: str | None = None
    image_url: HttpUrl | None = None
    is_active: bool | None = None


class ProductParentResponse(ProductParentBase):
    """Parent product response with its variants."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    variants: list[ProductResponse] = Field(default_factory=list)


class ProductParentSummary(BaseModel):
    """Grouped catalog card: one parent with an aggregated price range."""

    id: UUID
    name: str
    brand: str
    category: ProductCategory
    description: str | None
    image_url: str | None
    min_price: Decimal
    max_price: Decimal
    variant_count: int
    in_stock: bool


class ProductParentListResponse(BaseModel):
    """Paginated grouped catalog response."""

    items: list[ProductParentSummary]
    total: int
    page: int
    limit: int
    has_more: bool


class ProductSearchParams(BaseModel):
    """Product search and filter parameters."""

    search: str | None = Field(default=None, max_length=255)
    brand: str | None = None
    category: ProductCategory | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    size_kg: Decimal | None = None
    in_stock_only: bool = False
    sort_by: Literal["created_at", "price", "name"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)

    @model_validator(mode="after")
    def validate_search_params(self) -> "ProductSearchParams":
        """Validate search filters."""
        validate_gas_size(self.size_kg, self.category or "gas")
        if (
            self.min_price is not None
            and self.max_price is not None
            and self.min_price > self.max_price
        ):
            raise ValueError("min_price must be less than or equal to max_price")
        return self
