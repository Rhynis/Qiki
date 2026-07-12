"""Tests for the gas-price-change subscription service."""

from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.price_subscription_repository import PriceSubscriptionRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate
from app.services.price_alert_service import PriceAlertService
from app.services.product_service import ProductService

pytestmark = pytest.mark.asyncio


class RecordingEmailService:
    """Capture outgoing emails for assertions."""

    def __init__(self) -> None:
        self.messages: list[dict[str, str]] = []

    async def send_email(self, *, to: str, subject: str, html: str, text: str) -> bool:
        self.messages.append({"to": to, "subject": subject, "html": html, "text": text})
        return True


def _service(session: AsyncSession, email_service: RecordingEmailService) -> PriceAlertService:
    return PriceAlertService(
        PriceSubscriptionRepository(session),
        ProductService(ProductRepository(session)),
        email_service=email_service,
    )


async def _seed_gas_product(session: AsyncSession) -> None:
    await ProductRepository(session).create(
        ProductCreate(
            sku="GAS-12-PETRO",
            name="Bình gas",
            brand="Petrolimex",
            size_kg=Decimal("12"),
            category="gas",
            price=Decimal("440000"),
            stock_quantity=10,
        )
    )
    await session.flush()


async def test_subscribe_creates_pending_and_sends_confirm_email(
    price_alert_session: AsyncSession,
) -> None:
    email_service = RecordingEmailService()
    service = _service(price_alert_session, email_service)

    ack = await service.subscribe("Buyer@Example.com")

    assert "xác nhận" in ack.message.lower()
    row = await PriceSubscriptionRepository(price_alert_session).get_active_by_email(
        "buyer@example.com"
    )
    assert row is not None
    assert row.confirmed is False
    assert len(email_service.messages) == 1
    assert "Xác nhận" in email_service.messages[0]["subject"]
    assert row.token in email_service.messages[0]["text"]


async def test_subscribe_twice_dedupes_and_resends_confirm(
    price_alert_session: AsyncSession,
) -> None:
    email_service = RecordingEmailService()
    service = _service(price_alert_session, email_service)

    await service.subscribe("buyer@example.com")
    await service.subscribe("buyer@example.com")

    repo = PriceSubscriptionRepository(price_alert_session)
    # Still exactly one active row (the partial unique index would also reject a dup).
    row = await repo.get_active_by_email("buyer@example.com")
    assert row is not None
    assert len(email_service.messages) == 2  # confirmation resent, same token
    assert email_service.messages[0]["text"].count(row.token)
    assert email_service.messages[1]["text"].count(row.token)


async def test_confirm_marks_confirmed(price_alert_session: AsyncSession) -> None:
    email_service = RecordingEmailService()
    service = _service(price_alert_session, email_service)
    await service.subscribe("buyer@example.com")
    repo = PriceSubscriptionRepository(price_alert_session)
    token = (await repo.get_active_by_email("buyer@example.com")).token  # type: ignore[union-attr]

    assert await service.confirm(token) is True

    row = await repo.get_active_by_email("buyer@example.com")
    assert row is not None
    assert row.confirmed is True
    assert row.confirmed_at is not None


async def test_confirm_unknown_token_returns_false(
    price_alert_session: AsyncSession,
) -> None:
    service = _service(price_alert_session, RecordingEmailService())
    assert await service.confirm("does-not-exist") is False


async def test_notify_only_emails_confirmed_active_subscribers(
    price_alert_session: AsyncSession,
) -> None:
    await _seed_gas_product(price_alert_session)
    email_service = RecordingEmailService()
    service = _service(price_alert_session, email_service)
    repo = PriceSubscriptionRepository(price_alert_session)

    # Confirmed subscriber -> should receive.
    await service.subscribe("confirmed@example.com")
    confirmed = await repo.get_active_by_email("confirmed@example.com")
    assert confirmed is not None
    await service.confirm(confirmed.token)
    # Unconfirmed subscriber -> must NOT receive.
    await service.subscribe("pending@example.com")
    # Confirmed then unsubscribed -> must NOT receive.
    await service.subscribe("gone@example.com")
    gone = await repo.get_active_by_email("gone@example.com")
    assert gone is not None
    await service.confirm(gone.token)
    await service.unsubscribe(gone.token)

    email_service.messages.clear()
    result = await service.notify_price_change()

    assert result.recipient_count == 1
    assert result.sent_count == 1
    recipients = {msg["to"] for msg in email_service.messages}
    assert recipients == {"confirmed@example.com"}
    body = email_service.messages[0]
    assert "440.000đ" in body["text"]
    assert "Petrolimex" in body["text"]
    assert confirmed.token in body["text"]  # per-recipient unsubscribe link


async def test_unsubscribe_stops_notifications(
    price_alert_session: AsyncSession,
) -> None:
    await _seed_gas_product(price_alert_session)
    email_service = RecordingEmailService()
    service = _service(price_alert_session, email_service)
    repo = PriceSubscriptionRepository(price_alert_session)

    await service.subscribe("buyer@example.com")
    row = await repo.get_active_by_email("buyer@example.com")
    assert row is not None
    await service.confirm(row.token)
    assert await service.unsubscribe(row.token) is True

    email_service.messages.clear()
    result = await service.notify_price_change()

    assert result.recipient_count == 0
    assert result.sent_count == 0
    assert email_service.messages == []


async def test_unsubscribe_unknown_token_returns_false(
    price_alert_session: AsyncSession,
) -> None:
    service = _service(price_alert_session, RecordingEmailService())
    assert await service.unsubscribe("nope") is False
