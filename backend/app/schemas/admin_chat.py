"""Schemas for the admin-in-chat catalog management assistant."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

AdminChatStatus = Literal[
    "confirm_required",
    "executed",
    "not_found",
    "ambiguous",
    "invalid",
    "unrecognized",
    "expired",
]

AdminChatAction = Literal["update_price", "update_stock", "set_active"]


class AdminChatRequest(BaseModel):
    """An admin instruction to Qiki, or a confirmation of a pending action.

    ``message`` may be empty on a confirmation request (which carries only
    ``confirm`` + ``pending_token``); a planning request needs a real message.
    """

    message: str = Field(default="", max_length=500)
    confirm: bool = False
    pending_token: str | None = Field(default=None, max_length=64)


class AdminActionPreview(BaseModel):
    """The parsed, resolved action shown to the admin for confirmation."""

    action: AdminChatAction
    product_id: UUID
    product_name: str
    sku: str
    field: str
    current_value: str
    new_value: str


class AdminChatResponse(BaseModel):
    """Qiki's reply to an admin instruction.

    ``status`` drives the client: ``confirm_required`` carries a ``pending_token``
    plus the ``action`` preview to echo back with ``confirm=true``; ``executed``
    means the mutation was applied and audit-logged.
    """

    status: AdminChatStatus
    reply: str
    pending_token: str | None = None
    action: AdminActionPreview | None = None
