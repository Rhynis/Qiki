"""E-invoice adapter seam: a clean interface + a Noop stub.

A real Vietnamese e-invoice provider (VNPT / Viettel-Invoice) can be plugged in
later by implementing ``EInvoiceProvider`` and wiring it into
``get_einvoice_provider``. Nothing here calls an external service.

Env required by a future real adapter (not implemented yet):
- vnpt:    VNPT_EINVOICE_URL, VNPT_EINVOICE_ACCOUNT, VNPT_EINVOICE_PASSWORD,
           VNPT_EINVOICE_PATTERN, VNPT_EINVOICE_SERIAL
- viettel: VIETTEL_EINVOICE_URL, VIETTEL_EINVOICE_TOKEN, VIETTEL_EINVOICE_TAXCODE
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID

from app.core.config import Settings, get_settings
from app.core.exceptions import NotFoundException, ValidationException
from app.models.order import Order
from app.repositories.order_repository import OrderRepository
from app.schemas.einvoice import InvoiceResult


class EInvoiceProvider(Protocol):
    """Issues a legal e-invoice for an order and returns the outcome."""

    name: str

    async def issue_invoice(self, order: Order) -> InvoiceResult: ...


class NoopEInvoiceProvider:
    """Default provider: records a local stub invoice, no external call."""

    name = "none"

    async def issue_invoice(self, order: Order) -> InvoiceResult:
        """Return a 'stub' invoice result without contacting any provider."""
        return InvoiceResult(
            provider=self.name,
            status="stub",
            invoice_no=None,
            pdf_url=None,
            payload={
                "order_number": order.order_number,
                "total_amount": str(order.total_amount),
            },
            issued_at=datetime.now(UTC),
        )


def get_einvoice_provider(settings: Settings | None = None) -> EInvoiceProvider:
    """Resolve the configured e-invoice provider (mirrors the LLM factory)."""
    resolved = settings or get_settings()
    name = resolved.EINVOICE_PROVIDER
    if name == "none":
        return NoopEInvoiceProvider()
    # Drop a real adapter in here (implementing EInvoiceProvider) to connect a
    # provider; keep the Noop as the safe default.
    raise NotImplementedError(f"E-invoice provider '{name}' is not integrated yet")


class EInvoiceService:
    """Issue an e-invoice for an order via the configured provider."""

    def __init__(self, order_repo: OrderRepository, settings: Settings | None = None) -> None:
        self.order_repo = order_repo
        self.settings = settings or get_settings()

    async def issue_for_order(self, order_id: UUID) -> InvoiceResult:
        """Issue (or stub) an invoice for a delivered order and store the result."""
        order = await self.order_repo.get_by_id(order_id)
        if order is None:
            raise NotFoundException("Order not found", error_code="order_not_found")
        if order.status != "delivered":
            raise ValidationException(
                "An invoice can only be issued for a delivered order",
                error_code="order_not_delivered",
            )
        provider = get_einvoice_provider(self.settings)
        result = await provider.issue_invoice(order)
        order.einvoice = result.model_dump(mode="json")
        await self.order_repo.session.flush()
        return result
