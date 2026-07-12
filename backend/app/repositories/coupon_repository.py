"""Coupon repository."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, NotFoundException
from app.models.coupon import Coupon, CouponRedemption
from app.schemas.coupon import CouponCreate, CouponSearchParams


class CouponRepository:
    """Data access layer for coupons and redemptions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, data: CouponCreate) -> Coupon:
        """Create a coupon."""
        coupon = Coupon(**data.model_dump())
        self.session.add(coupon)
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ConflictException(
                "Coupon code already exists", error_code="duplicate_coupon_code"
            ) from exc
        await self.session.refresh(coupon)
        return coupon

    async def get_by_id(self, coupon_id: UUID) -> Coupon | None:
        """Find a coupon by ID."""
        result = await self.session.execute(select(Coupon).where(Coupon.id == coupon_id))
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Coupon | None:
        """Find a coupon by its normalized code."""
        result = await self.session.execute(
            select(Coupon).where(Coupon.code == code.upper().strip())
        )
        return result.scalar_one_or_none()

    async def get_by_code_for_update(self, code: str) -> Coupon | None:
        """Find a coupon by code with a row lock to guard used_count."""
        result = await self.session.execute(
            select(Coupon).where(Coupon.code == code.upper().strip()).with_for_update()
        )
        return result.scalar_one_or_none()

    async def count_user_redemptions(self, coupon_id: UUID, user_id: UUID) -> int:
        """Count how many times a user has redeemed a coupon."""
        result = await self.session.execute(
            select(func.count())
            .select_from(CouponRedemption)
            .where(
                CouponRedemption.coupon_id == coupon_id,
                CouponRedemption.user_id == user_id,
            )
        )
        return int(result.scalar_one())

    async def record_redemption(
        self,
        coupon: Coupon,
        user_id: UUID | None,
        order_id: UUID | None,
    ) -> CouponRedemption:
        """Increment used_count and insert a redemption row."""
        coupon.used_count += 1
        redemption = CouponRedemption(
            coupon_id=coupon.id,
            user_id=user_id,
            order_id=order_id,
            created_at=datetime.now(UTC),
        )
        self.session.add(redemption)
        await self.session.flush()
        return redemption

    async def update(self, coupon_id: UUID, data: dict[str, object]) -> Coupon:
        """Update a coupon."""
        coupon = await self.get_by_id(coupon_id)
        if not coupon:
            raise NotFoundException("Coupon not found", error_code="coupon_not_found")
        for key, value in data.items():
            if hasattr(coupon, key):
                setattr(coupon, key, value)
        await self.session.flush()
        await self.session.refresh(coupon)
        return coupon

    async def list_coupons(self, params: CouponSearchParams) -> tuple[list[Coupon], int]:
        """List coupons with filters and pagination."""
        query = select(Coupon)
        count_query = select(func.count()).select_from(Coupon)

        conditions: list[ColumnElement[bool]] = []
        if params.active is not None:
            conditions.append(Coupon.active.is_(params.active))
        if params.search:
            conditions.append(Coupon.code.ilike(f"%{params.search.strip().upper()}%"))

        for condition in conditions:
            query = query.where(condition)
            count_query = count_query.where(condition)

        query = query.order_by(Coupon.created_at.desc()).offset(params.skip).limit(params.limit)
        total = int((await self.session.execute(count_query)).scalar_one())
        coupons = list((await self.session.execute(query)).scalars().all())
        return coupons, total


def compute_discount(coupon: Coupon, subtotal: Decimal) -> Decimal:
    """Return the server-authoritative discount for a subtotal (never negative)."""
    if coupon.discount_type == "percent":
        discount = (subtotal * coupon.value / Decimal("100")).quantize(Decimal("0.01"))
    else:
        discount = coupon.value
    if coupon.max_discount is not None and discount > coupon.max_discount:
        discount = coupon.max_discount
    if discount > subtotal:
        discount = subtotal
    if discount < Decimal("0"):
        discount = Decimal("0")
    return discount
