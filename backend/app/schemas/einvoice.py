"""E-invoice schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class InvoiceResult(BaseModel):
    """Outcome of issuing (or stubbing) a legal e-invoice for an order."""

    provider: str
    status: str
    invoice_no: str | None = None
    pdf_url: str | None = None
    payload: dict[str, Any] | None = None
    issued_at: datetime | None = None
