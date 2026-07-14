"""Coupon service: validation, discount application, and admin CRUD."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from app.core.exceptions import ForbiddenException, NotFoundException, ValidationException
from app.core.logging import get_logger
from app.models.coupon import Coupon
from app.models.user import User
from app.repositories.coupon_repository import CouponRepository, compute_discount
from app.schemas.coupon import (
    CouponCreate,
    CouponListResponse,
    CouponResponse,
    CouponSearchParams,
    CouponUpdate,
    CouponValidateResponse,
)

logger = get_logger(__name__)


class CouponError(ValidationException):
    """Raised when a coupon is not eligible for use."""


class CouponService:
    """Business logic for coupons."""

    def __init__(self, repository: CouponRepository) -> None:
        self.repository = repository

    @staticmethod
    def _ensure_admin(user: User) -> None:
        if not user.is_admin():
            raise ForbiddenException("Admin role required", error_code="admin_required")

    def _check_eligibility(
        self,
        coupon: Coupon | None,
        subtotal: Decimal,
        now: datetime,
    ) -> Coupon:
        """Validate a coupon's active window and min-order gate.

        Usage/per-user limits are enforced separately at order creation, where the
        row is locked. This method covers checks that do not need a lock so it can
        back the public validate endpoint.
        """
        if coupon is None:
            raise CouponError("Coupon not found", error_code="coupon_not_found")
        if not coupon.active:
            raise CouponError("Coupon is not active", error_code="coupon_inactive")
        if coupon.starts_at and now < coupon.starts_at:
            raise CouponError("Coupon is not yet valid", error_code="coupon_not_started")
        if coupon.ends_at and now >= coupon.ends_at:
            raise CouponError("Coupon has expired", error_code="coupon_expired")
        if coupon.usage_limit is not None and coupon.used_count >= coupon.usage_limit:
            raise CouponError("Coupon usage limit reached", error_code="coupon_usage_exhausted")
        if subtotal < coupon.min_order:
            raise CouponError(
                "Order does not meet the minimum for this coupon",
                error_code="coupon_min_order",
            )
        return coupon

    async def validate_coupon(self, code: str, subtotal: Decimal) -> CouponValidateResponse:
        """Validate a coupon for a subtotal and return the computed discount."""
        coupon = await self.repository.get_by_code(code)
        now = datetime.now(UTC)
        coupon = self._check_eligibility(coupon, subtotal, now)
        discount = compute_discount(coupon, subtotal)
        return CouponValidateResponse(
            code=coupon.code,
            discount_type=coupon.discount_type,  # type: ignore[arg-type]
            value=coupon.value,
            discount_amount=discount,
            min_order=coupon.min_order,
        )

    async def apply_coupon(
        self,
        code: str,
        subtotal: Decimal,
        user: User | None,
    ) -> tuple[Coupon, Decimal]:
        """Lock a coupon, enforce all limits, and return it with its discount.

        Must run inside the order transaction. The row lock serializes concurrent
        checkouts so used_count and usage_limit cannot be oversold. The caller is
        responsible for recording the redemption once the order id is known.
        """
        coupon = await self.repository.get_by_code_for_update(code)
        now = datetime.now(UTC)
        coupon = self._check_eligibility(coupon, subtotal, now)
        if coupon.per_user_limit is not None:
            if user is None:
                raise CouponError(
                    "This coupon requires a signed-in account",
                    error_code="coupon_requires_account",
                )
            used = await self.repository.count_user_redemptions(coupon.id, user.id)
            if used >= coupon.per_user_limit:
                raise CouponError(
                    "You have already used this coupon",
                    error_code="coupon_per_user_exhausted",
                )
        discount = compute_discount(coupon, subtotal)
        return coupon, discount

    async def record_redemption(
        self,
        coupon: Coupon,
        user: User | None,
        order_id: UUID,
    ) -> None:
        """Increment used_count and record the redemption for a created order."""
        await self.repository.record_redemption(
            coupon,
            user.id if user else None,
            order_id,
        )

    async def create_coupon(self, payload: CouponCreate, admin: User) -> CouponResponse:
        """Create a coupon as an administrator."""
        self._ensure_admin(admin)
        coupon = await self.repository.create(payload)
        logger.info("coupon_created", code=coupon.code)
        return CouponResponse.model_validate(coupon)

    async def get_coupon(self, coupon_id: UUID, admin: User) -> CouponResponse:
        """Get one coupon by ID as an administrator."""
        self._ensure_admin(admin)
        coupon = await self.repository.get_by_id(coupon_id)
        if not coupon:
            raise NotFoundException("Coupon not found", error_code="coupon_not_found")
        return CouponResponse.model_validate(coupon)

    async def list_coupons(self, params: CouponSearchParams, admin: User) -> CouponListResponse:
        """List coupons as an administrator."""
        self._ensure_admin(admin)
        coupons, total = await self.repository.list_coupons(params)
        return CouponListResponse(
            items=[CouponResponse.model_validate(coupon) for coupon in coupons],
            total=total,
            page=(params.skip // params.limit) + 1,
            limit=params.limit,
            has_more=params.skip + len(coupons) < total,
        )

    async def update_coupon(
        self,
        coupon_id: UUID,
        payload: CouponUpdate,
        admin: User,
    ) -> CouponResponse:
        """Update a coupon as an administrator."""
        self._ensure_admin(admin)
        update_data = payload.model_dump(exclude_unset=True)
        merged = await self.repository.get_by_id(coupon_id)
        if not merged:
            raise NotFoundException("Coupon not found", error_code="coupon_not_found")
        self._validate_update(merged, update_data)
        coupon = await self.repository.update(coupon_id, update_data)
        return CouponResponse.model_validate(coupon)

    @staticmethod
    def _validate_update(coupon: Coupon, update_data: dict[str, object]) -> None:
        """Validate the merged state of a coupon update."""
        discount_type = update_data.get("discount_type", coupon.discount_type)
        raw_value = update_data.get("value", coupon.value)
        value = Decimal(str(raw_value))
        if discount_type == "percent" and value > Decimal("100"):
            raise ValidationException(
                "percent value cannot exceed 100", error_code="invalid_coupon"
            )
        starts_at = update_data.get("starts_at", coupon.starts_at)
        ends_at = update_data.get("ends_at", coupon.ends_at)
        if isinstance(starts_at, datetime) and isinstance(ends_at, datetime):
            if ends_at <= starts_at:
                raise ValidationException(
                    "ends_at must be after starts_at", error_code="invalid_coupon"
                )
