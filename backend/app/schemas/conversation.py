"""Schemas for conversation management APIs."""

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.message import MessageResponse

ConversationStatus = Literal["active", "escalated", "resolved", "abandoned"]


class ConversationCreateRequest(BaseModel):
    """Request to start a conversation."""

    session_id: str | None = Field(default=None, max_length=100)
    initial_message: str | None = Field(default=None, min_length=1, max_length=2000)


class SendMessageRequest(BaseModel):
    """Customer message payload."""

    content: str = Field(min_length=1, max_length=2000)
    session_id: str | None = Field(default=None, max_length=100)


class StaffMessageRequest(BaseModel):
    """Staff message payload."""

    content: str = Field(min_length=1, max_length=2000)


class FeedbackRequest(BaseModel):
    """Feedback for an assistant message."""

    score: Literal[-1, 0, 1]


class EscalateRequest(BaseModel):
    """Manual escalation payload."""

    reason: str = Field(min_length=1, max_length=500)
    staff_id: UUID | None = None


class TransferRequest(BaseModel):
    """Staff transfer payload."""

    staff_id: UUID


class ResolveRequest(BaseModel):
    """Resolve conversation payload."""

    satisfaction_rating: int | None = Field(default=None, ge=1, le=5)


class ConversationResponse(BaseModel):
    """Conversation returned by API responses."""

    id: UUID
    user_id: UUID | None = None
    session_id: str
    status: ConversationStatus
    assigned_to: UUID | None = None
    escalated_at: datetime | None = None
    escalation_reason: str | None = None
    resolved_at: datetime | None = None
    satisfaction_rating: int | None = None
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ConversationListResponse(BaseModel):
    """Paginated conversation list."""

    items: list[ConversationResponse]
    total: int
    skip: int
    limit: int


class ProductCardResponse(BaseModel):
    """Structured product card data returned with chat responses."""

    id: UUID
    name: str
    brand: str
    size_kg: Decimal
    unit: str = "kg"
    price: Decimal
    image_url: str | None = None
    sku: str
    stock_quantity: int


class SendMessageResponse(BaseModel):
    """Response after sending a customer message."""

    user_message: MessageResponse
    assistant_message: MessageResponse | None = None
    conversation: ConversationResponse
    products: list[ProductCardResponse] = Field(default_factory=list)
