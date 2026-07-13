"""Delivery schemas."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DeliveryStatus = Literal["pending", "shipping", "delivered", "failed", "cancelled"]
DriverOutcome = Literal["delivered", "failed"]


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


class DriverAssignRequest(BaseModel):
    """Assign (or clear) the driver carrying a delivery."""

    driver_id: UUID | None = None


class DriverStatusUpdate(BaseModel):
    """A driver's delivered/failed update, with an optional last location.

    Location is never required; a driver can complete a delivery without sharing it.
    """

    status: DriverOutcome
    notes: str | None = Field(default=None, max_length=1000)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)


class DeliveryItemResponse(BaseModel):
    """A delivery line: quantity of one order item."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    delivery_id: UUID
    order_item_id: UUID
    quantity: int
    created_at: datetime


class DriverDeliveryLine(BaseModel):
    """A product line a driver is carrying."""

    product_name: str
    quantity: int


class DriverDeliveryResponse(BaseModel):
    """A delivery enriched with the order's contact + address for the driver view."""

    id: UUID
    code: str
    status: DeliveryStatus
    customer_name: str
    customer_phone: str
    delivery_address: str
    notes: str | None
    scheduled_at: datetime | None
    delivered_at: datetime | None
    last_lat: float | None
    last_lng: float | None
    items: list[DriverDeliveryLine]
    created_at: datetime


class DeliveryResponse(BaseModel):
    """A delivery with its items."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    code: str
    status: DeliveryStatus
    driver_id: UUID | None
    scheduled_at: datetime | None
    delivered_at: datetime | None
    notes: str | None
    last_lat: float | None
    last_lng: float | None
    items: list[DeliveryItemResponse]
    created_at: datetime
