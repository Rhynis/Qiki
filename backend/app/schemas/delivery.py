"""Delivery schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DeliveryStatus = Literal["pending", "shipping", "delivered", "cancelled"]


class DeliveryItemCreate(BaseModel):
    """One order item (and quantity) to include in a delivery."""

    order_item_id: UUID
    quantity: int = Field(ge=1)


class DeliveryCreate(BaseModel):
    """Payload to create/split a delivery for an order."""

    items: list[DeliveryItemCreate] = Field(min_length=1)
    scheduled_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)


class DeliveryStatusUpdate(BaseModel):
    """Payload to update a delivery's status."""

    status: DeliveryStatus
    notes: str | None = Field(default=None, max_length=1000)


class DeliveryItemResponse(BaseModel):
    """A delivery line: quantity of one order item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_id: UUID
    order_item_id: UUID
    quantity: int
    created_at: datetime


class DeliveryResponse(BaseModel):
    """A delivery with its items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    code: str
    status: DeliveryStatus
    scheduled_at: datetime | None
    delivered_at: datetime | None
    notes: str | None
    items: list[DeliveryItemResponse]
    created_at: datetime
