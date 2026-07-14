"""Coupon schemas."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DiscountType = Literal["percent", "fixed"]

CODE_PATTERN = re.compile(r"^[A-Z0-9-]{3,50}$")


def _normalize_code(value: str) -> str:
    """Uppercase, strip, and validate a coupon code format."""
    normalized = value.upper().strip()
    if not CODE_PATTERN.fullmatch(normalized):
        raise ValueError("code must be 3-50 chars of A-Z, 0-9, or '-'")
    return normalized


class CouponBase(BaseModel):
    """Shared coupon fields with cross-field validation."""

    discount_type: DiscountType
    value: Decimal = Field(gt=0)
    min_order: Decimal = Field(default=Decimal("0"), ge=0)
    max_discount: Decimal | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
    active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_coupon_rules(self) -> "CouponBase":
        """Enforce percent bounds and a valid active window."""
        if self.discount_type == "percent" and self.value > Decimal("100"):
            raise ValueError("percent value cannot exceed 100")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class CouponCreate(CouponBase):
    """Payload for creating a coupon."""

    code: str = Field(min_length=3, max_length=50)

    @field_validator("code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        return _normalize_code(value)


class CouponUpdate(BaseModel):
    """Partial update payload for a coupon (code is immutable)."""

    discount_type: DiscountType | None = None
    value: Decimal | None = Field(default=None, gt=0)
    min_order: Decimal | None = Field(default=None, ge=0)
    max_discount: Decimal | None = Field(default=None, gt=0)
    usage_limit: int | None = Field(default=None, ge=1)
    per_user_limit: int | None = Field(default=None, ge=1)
    active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class CouponResponse(BaseModel):
    """Coupon response for admin management."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    discount_type: DiscountType
    value: Decimal
    min_order: Decimal
    max_discount: Decimal | None
    usage_limit: int | None
    used_count: int
    per_user_limit: int | None
    active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CouponListResponse(BaseModel):
    """Paginated coupon response."""

    items: list[CouponResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class CouponValidateRequest(BaseModel):
    """Public request to validate a coupon against a cart subtotal."""

    code: str = Field(min_length=1, max_length=50)
    subtotal: Decimal = Field(ge=0)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.upper().strip()


class CouponValidateResponse(BaseModel):
    """Public response describing a coupon's discount for a subtotal."""

    code: str
    discount_type: DiscountType
    value: Decimal
    discount_amount: Decimal
    min_order: Decimal


class CouponSearchParams(BaseModel):
    """Admin coupon list filters."""

    active: bool | None = None
    search: str | None = Field(default=None, max_length=50)
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=20, ge=1, le=100)
