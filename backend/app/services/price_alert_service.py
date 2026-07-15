"""Gas-price-change email subscription service (double opt-in)."""

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal, Protocol
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.repositories.price_subscription_repository import PriceSubscriptionRepository
from app.schemas.price_subscription import PriceAlertNotifyResult, PriceSubscriptionAck
from app.schemas.product import ProductResponse
from app.services.email_service import (
    EmailService,
    render_price_alert_confirm,
    render_price_alert_notification,
)
from app.services.product_service import ProductService

logger = get_logger(__name__)

# Same generic acknowledgement for every subscribe outcome so the endpoint never
# reveals whether an address is already subscribed.
SUBSCRIBE_ACK_MESSAGE = (
    "Nếu địa chỉ email hợp lệ, chúng tôi đã gửi email xác nhận. "
    "Vui lòng kiểm tra hộp thư để hoàn tất đăng ký."
)

# A confirm link is single-purpose and expires; after this window the customer
# must subscribe again.
CONFIRM_TOKEN_TTL = timedelta(days=7)

# Outcome of confirming a token, so the endpoint can message each case clearly.
ConfirmResult = Literal["confirmed", "invalid", "expired"]


class EmailSender(Protocol):
    """Minimal email delivery protocol used by the price-alert service."""

    async def send_email(self, *, to: str, subject: str, html: str, text: str) -> bool: ...


class PriceAlertService:
    """Subscribe/confirm/unsubscribe flows and price-change notifications."""

    def __init__(
        self,
        repository: PriceSubscriptionRepository,
        product_service: ProductService,
        email_service: EmailSender | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.repository = repository
        self.product_service = product_service
        self.settings = settings or get_settings()
        self.email_service = email_service or EmailService(self.settings)

    def _confirm_url(self, token: str) -> str:
        base = self.settings.FRONTEND_URL.rstrip("/")
        return f"{base}/price-alerts/confirm?token={token}"

    def _unsubscribe_url(self, token: str) -> str:
        base = self.settings.FRONTEND_URL.rstrip("/")
        return f"{base}/price-alerts/unsubscribe?token={token}"

    async def subscribe(self, email: str, *, user_id: UUID | None = None) -> PriceSubscriptionAck:
        """Create or refresh a subscription and send a confirmation email.

        Returns the same generic acknowledgement in every case (new, already
        pending, already confirmed) to avoid leaking whether an email exists.
        A confirmed address is not re-emailed; a still-pending one gets its
        confirmation email resent with the existing token.
        """
        normalized = email.strip().lower()
        existing = await self.repository.get_active_by_email(normalized)
        if existing is not None:
            if existing.confirmed:
                return PriceSubscriptionAck(message=SUBSCRIBE_ACK_MESSAGE)
            await self._send_confirm_email(
                normalized, existing.confirm_token, existing.unsubscribe_token
            )
            return PriceSubscriptionAck(message=SUBSCRIBE_ACK_MESSAGE)

        confirm_token = secrets.token_urlsafe(32)
        unsubscribe_token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + CONFIRM_TOKEN_TTL
        try:
            await self.repository.create(
                email=normalized,
                confirm_token=confirm_token,
                unsubscribe_token=unsubscribe_token,
                confirm_expires_at=expires_at,
                user_id=user_id,
            )
        except IntegrityError:
            # A concurrent first-time subscribe for the same email lost the race on
            # the partial-unique active-email index. The winner already sent the
            # confirmation, so return the same generic ack instead of a 500.
            await self.repository.rollback()
            return PriceSubscriptionAck(message=SUBSCRIBE_ACK_MESSAGE)

        await self._send_confirm_email(normalized, confirm_token, unsubscribe_token)
        return PriceSubscriptionAck(message=SUBSCRIBE_ACK_MESSAGE)

    async def confirm(self, token: str) -> ConfirmResult:
        """Confirm a pending subscription via its single-purpose confirm token.

        Returns 'invalid' for an unknown/unsubscribed token (an unsubscribe token
        never matches here), 'expired' once the confirm window has passed, and
        'confirmed' on success (idempotent for an already-confirmed row).
        """
        subscription = await self.repository.get_by_confirm_token(token)
        if subscription is None or subscription.unsubscribed_at is not None:
            return "invalid"
        if subscription.confirmed:
            return "confirmed"
        if (
            subscription.confirm_expires_at is not None
            and datetime.now(UTC) >= subscription.confirm_expires_at
        ):
            return "expired"
        await self.repository.mark_confirmed(subscription)
        return "confirmed"

    async def unsubscribe(self, token: str) -> bool:
        """Unsubscribe via the single-purpose unsubscribe token (idempotent).

        Returns False for an unknown token (a confirm token never matches here).
        """
        subscription = await self.repository.get_by_unsubscribe_token(token)
        if subscription is None:
            return False
        await self.repository.mark_unsubscribed(subscription)
        return True

    async def notify_price_change(self) -> PriceAlertNotifyResult:
        """Email confirmed subscribers the current gas price table.

        Sends sequentially so a large list naturally paces itself within the
        email provider's limits. Only confirmed, not-unsubscribed addresses are
        contacted; each email carries that subscriber's own unsubscribe link.
        """
        price_rows = await self._build_gas_price_rows()
        recipients = await self.repository.list_confirmed_active()
        sent = 0
        for subscription in recipients:
            subject, text, html = render_price_alert_notification(
                price_rows,
                unsubscribe_url=self._unsubscribe_url(subscription.unsubscribe_token),
            )
            delivered = await self.email_service.send_email(
                to=subscription.email, subject=subject, html=html, text=text
            )
            if delivered:
                sent += 1
        logger.info(
            "price_alert_notification_sent",
            recipient_count=len(recipients),
            sent_count=sent,
            product_count=len(price_rows),
        )
        return PriceAlertNotifyResult(sent_count=sent, recipient_count=len(recipients))

    async def _build_gas_price_rows(self) -> list[tuple[str, str]]:
        catalog = await self.product_service.list_active_catalog(limit=100)
        rows: list[tuple[str, str]] = []
        for product in catalog:
            if product.category != "gas":
                continue
            rows.append((self._display_name(product), self._format_vnd(product.price)))
        return rows

    @staticmethod
    def _display_name(product: ProductResponse) -> str:
        size_text = f"{product.size_kg.normalize():f}".rstrip("0").rstrip(".")
        return f"{product.brand} {product.name} {size_text}{product.unit}"

    @staticmethod
    def _format_vnd(price: Decimal) -> str:
        return f"{int(price):,}".replace(",", ".") + "đ"

    async def _send_confirm_email(
        self, email: str, confirm_token: str, unsubscribe_token: str
    ) -> None:
        subject, text, html = render_price_alert_confirm(
            self._confirm_url(confirm_token),
            unsubscribe_url=self._unsubscribe_url(unsubscribe_token),
        )
        try:
            await self.email_service.send_email(to=email, subject=subject, html=html, text=text)
        except Exception:
            logger.exception("price_alert_confirm_email_send_failed")
