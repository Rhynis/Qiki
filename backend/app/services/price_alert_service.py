"""Gas-price-change email subscription service (double opt-in)."""

import secrets
from decimal import Decimal
from typing import Protocol
from uuid import UUID

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
            await self._send_confirm_email(normalized, existing.token)
            return PriceSubscriptionAck(message=SUBSCRIBE_ACK_MESSAGE)

        token = secrets.token_urlsafe(32)
        await self.repository.create(email=normalized, token=token, user_id=user_id)
        await self._send_confirm_email(normalized, token)
        return PriceSubscriptionAck(message=SUBSCRIBE_ACK_MESSAGE)

    async def confirm(self, token: str) -> bool:
        """Confirm a pending subscription. Returns False for unknown/inactive tokens."""
        subscription = await self.repository.get_by_token(token)
        if subscription is None or subscription.unsubscribed_at is not None:
            return False
        await self.repository.mark_confirmed(subscription)
        return True

    async def unsubscribe(self, token: str) -> bool:
        """Unsubscribe by token (idempotent). Returns False for unknown tokens."""
        subscription = await self.repository.get_by_token(token)
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
                unsubscribe_url=self._unsubscribe_url(subscription.token),
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

    async def _send_confirm_email(self, email: str, token: str) -> None:
        subject, text, html = render_price_alert_confirm(
            self._confirm_url(token),
            unsubscribe_url=self._unsubscribe_url(token),
        )
        try:
            await self.email_service.send_email(to=email, subject=subject, html=html, text=text)
        except Exception:
            logger.exception("price_alert_confirm_email_send_failed")
