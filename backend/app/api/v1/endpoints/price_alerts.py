"""Gas-price-change email subscription endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin, get_current_user_optional
from app.core.exceptions import NotFoundException, ValidationException
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.user import User
from app.repositories.price_subscription_repository import PriceSubscriptionRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.price_subscription import (
    PriceAlertNotifyResult,
    PriceSubscriptionAck,
    PriceSubscriptionCreate,
    PriceSubscriptionToken,
)
from app.services.price_alert_service import PriceAlertService
from app.services.product_service import ProductService

router = APIRouter()

_CONFIRMED_MESSAGE = "Đăng ký nhận thông báo giá gas đã được xác nhận. Cảm ơn bạn!"
_UNSUBSCRIBED_MESSAGE = "Bạn đã hủy nhận thông báo giá gas. Rất mong được phục vụ lại!"
_INVALID_LINK_MESSAGE = "Liên kết không hợp lệ hoặc đã hết hạn."
_EXPIRED_CONFIRM_MESSAGE = (
    "Liên kết xác nhận đã hết hạn. Vui lòng đăng ký lại để nhận email xác nhận mới."
)


def get_price_alert_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PriceAlertService:
    """Build a request-scoped price-alert service."""
    return PriceAlertService(
        PriceSubscriptionRepository(session),
        ProductService(ProductRepository(session)),
    )


@router.post(
    "/price-alerts/subscribe",
    response_model=PriceSubscriptionAck,
    summary="Subscribe to gas price-change emails",
)
@limiter.limit("5/minute")
async def subscribe_price_alerts(
    request: Request,
    payload: PriceSubscriptionCreate,
    service: Annotated[PriceAlertService, Depends(get_price_alert_service)],
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> PriceSubscriptionAck:
    """Start a double-opt-in subscription and send a confirmation email."""
    return await service.subscribe(payload.email, user_id=user.id if user else None)


@router.post(
    "/price-alerts/confirm",
    response_model=PriceSubscriptionAck,
    summary="Confirm a gas price-change subscription",
)
@limiter.limit("10/minute")
async def confirm_price_alerts(
    request: Request,
    payload: PriceSubscriptionToken,
    service: Annotated[PriceAlertService, Depends(get_price_alert_service)],
) -> PriceSubscriptionAck:
    """Confirm a pending subscription via its single-purpose confirm token."""
    result = await service.confirm(payload.token)
    if result == "expired":
        raise ValidationException(_EXPIRED_CONFIRM_MESSAGE, error_code="confirm_token_expired")
    if result == "invalid":
        raise NotFoundException(_INVALID_LINK_MESSAGE, error_code="invalid_token")
    return PriceSubscriptionAck(message=_CONFIRMED_MESSAGE)


@router.post(
    "/price-alerts/unsubscribe",
    response_model=PriceSubscriptionAck,
    summary="Unsubscribe from gas price-change emails",
)
@limiter.limit("10/minute")
async def unsubscribe_price_alerts(
    request: Request,
    payload: PriceSubscriptionToken,
    service: Annotated[PriceAlertService, Depends(get_price_alert_service)],
) -> PriceSubscriptionAck:
    """Unsubscribe via the opaque token from an email link (idempotent)."""
    if not await service.unsubscribe(payload.token):
        raise NotFoundException(_INVALID_LINK_MESSAGE, error_code="invalid_token")
    return PriceSubscriptionAck(message=_UNSUBSCRIBED_MESSAGE)


@router.post(
    "/admin/price-alerts/notify",
    response_model=PriceAlertNotifyResult,
    summary="Notify subscribers of a gas price change",
)
@limiter.limit("5/minute")
async def notify_price_change(
    request: Request,
    service: Annotated[PriceAlertService, Depends(get_price_alert_service)],
    admin: Annotated[User, Depends(get_current_admin)],
) -> PriceAlertNotifyResult:
    """Email the current gas price table to all confirmed subscribers (admin only)."""
    return await service.notify_price_change()
