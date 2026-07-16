"""Tests for the e-invoice adapter seam + Noop stub."""

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import (
    NotFoundException,
    NotImplementedException,
    ValidationException,
)
from app.models.order import Order
from app.services.einvoice import (
    EInvoiceService,
    NoopEInvoiceProvider,
    get_einvoice_provider,
)


def make_order(status: str = "delivered") -> Order:
    now = datetime.now(UTC)
    return Order(
        id=uuid4(),
        order_number="GB-20260712-001",
        customer_name="Nguyen Van A",
        customer_phone="+84901234567",
        delivery_address="123 Nguyen Trai",
        delivery_city="TP. Hồ Chí Minh",
        subtotal=Decimal("700000"),
        shipping_fee=Decimal("0"),
        total_amount=Decimal("700000"),
        status=status,
        payment_method="cod",
        payment_status="pending",
        source="website",
        created_at=now,
        updated_at=now,
    )


class FakeSession:
    def __init__(self) -> None:
        self.flushed = 0

    async def flush(self) -> None:
        self.flushed += 1


class FakeOrderRepository:
    def __init__(self, order: Order | None) -> None:
        self.order = order
        self.session = FakeSession()

    async def get_by_id(self, order_id: UUID) -> Order | None:
        if self.order is None or self.order.id != order_id:
            return None
        return self.order


def test_factory_returns_noop_by_default() -> None:
    provider = get_einvoice_provider(SimpleNamespace(EINVOICE_PROVIDER="none"))
    assert isinstance(provider, NoopEInvoiceProvider)
    assert provider.name == "none"


def test_factory_raises_handled_error_for_unintegrated_provider() -> None:
    with pytest.raises(NotImplementedException) as excinfo:
        get_einvoice_provider(SimpleNamespace(EINVOICE_PROVIDER="vnpt"))
    # A handled application error (maps to 501), not a bare NotImplementedError.
    assert excinfo.value.status_code == 501
    assert excinfo.value.error_code == "einvoice_provider_not_configured"


async def test_noop_records_a_stub_invoice() -> None:
    result = await NoopEInvoiceProvider().issue_invoice(make_order())
    assert result.provider == "none"
    assert result.status == "stub"
    assert result.invoice_no is None
    assert result.issued_at is not None


async def test_issue_for_delivered_order_stores_stub() -> None:
    order = make_order(status="delivered")
    repo = FakeOrderRepository(order)
    service = EInvoiceService(repo, SimpleNamespace(EINVOICE_PROVIDER="none"))  # type: ignore[arg-type]

    result = await service.issue_for_order(order.id)

    assert result.status == "stub"
    assert order.einvoice is not None
    assert order.einvoice["status"] == "stub"
    assert repo.session.flushed == 1


async def test_issue_requires_delivered_order() -> None:
    order = make_order(status="pending")
    service = EInvoiceService(FakeOrderRepository(order), SimpleNamespace(EINVOICE_PROVIDER="none"))  # type: ignore[arg-type]

    with pytest.raises(ValidationException):
        await service.issue_for_order(order.id)


async def test_issue_missing_order_raises_not_found() -> None:
    service = EInvoiceService(FakeOrderRepository(None), SimpleNamespace(EINVOICE_PROVIDER="none"))  # type: ignore[arg-type]

    with pytest.raises(NotFoundException):
        await service.issue_for_order(uuid4())


async def test_issue_with_unintegrated_provider_raises_handled_error() -> None:
    # EINVOICE_PROVIDER=vnpt on a delivered order must surface a handled 501
    # (NotImplementedException), never a bare NotImplementedError / opaque 500.
    order = make_order(status="delivered")
    service = EInvoiceService(
        FakeOrderRepository(order),
        SimpleNamespace(EINVOICE_PROVIDER="vnpt"),  # type: ignore[arg-type]
    )

    with pytest.raises(NotImplementedException) as excinfo:
        await service.issue_for_order(order.id)
    assert excinfo.value.status_code == 501
    assert excinfo.value.error_code == "einvoice_provider_not_configured"
    # The order was not marked with a bogus invoice.
    assert order.einvoice is None
