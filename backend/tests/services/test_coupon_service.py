"""Tests for CouponService and coupon-aware order creation."""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, ValidationException
from app.db.session import AsyncSessionLocal
from app.models.coupon import Coupon, CouponRedemption
from app.models.product import Product
from app.models.user import User
from app.repositories.coupon_repository import CouponRepository, compute_discount
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.coupon import CouponCreate, CouponSearchParams, CouponUpdate
from app.schemas.order import CheckoutRequest, OrderItemCreate
from app.schemas.product import ProductCreate
from app.services.coupon_service import CouponError, CouponService
from app.services.order_service import OrderService

# asyncio_mode = "auto" (pyproject) marks async tests automatically; a module-level
# asyncio mark would wrongly apply to the sync tests in this file.


def user_model(role: str = "customer", *, phone: str = "+84901234567") -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=f"{role}-{uuid4().hex}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone=phone,
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def create_user(session: AsyncSession, role: str = "customer") -> User:
    user = user_model(role)
    session.add(user)
    await session.commit()
    return user


async def create_product(
    session: AsyncSession,
    *,
    sku: str = "GAS-12-SAIGON",
    price: Decimal = Decimal("350000"),
    stock_quantity: int = 20,
) -> Product:
    product = await ProductRepository(session).create(
        ProductCreate(
            sku=sku,
            name="Binh gas 12kg",
            brand="Saigon Petro",
            size_kg=Decimal("12"),
            category="gas",
            unit="kg",
            price=price,
            stock_quantity=stock_quantity,
            description="San pham giao tan noi",
            image_url="https://example.com/gas-12kg.jpg",
            safety_info="Dat binh noi thoang khi.",
        )
    )
    await session.commit()
    return product


def coupon_create(
    *,
    code: str = "SAVE10",
    discount_type: Literal["percent", "fixed"] = "percent",
    value: Decimal = Decimal("10"),
    min_order: Decimal = Decimal("0"),
    max_discount: Decimal | None = None,
    usage_limit: int | None = None,
    per_user_limit: int | None = None,
    active: bool = True,
    starts_at: datetime | None = None,
    ends_at: datetime | None = None,
) -> CouponCreate:
    return CouponCreate(
        code=code,
        discount_type=discount_type,
        value=value,
        min_order=min_order,
        max_discount=max_discount,
        usage_limit=usage_limit,
        per_user_limit=per_user_limit,
        active=active,
        starts_at=starts_at,
        ends_at=ends_at,
    )


async def seed_coupon(session: AsyncSession, **overrides: object) -> Coupon:
    coupon = await CouponRepository(session).create(coupon_create(**overrides))  # type: ignore[arg-type]
    await session.commit()
    return coupon


def coupon_service(session: AsyncSession) -> CouponService:
    return CouponService(CouponRepository(session))


def order_service(session: AsyncSession) -> OrderService:
    return OrderService(
        OrderRepository(session),
        ProductRepository(session),
        CouponService(CouponRepository(session)),
    )


def checkout_payload(product: Product, quantity: int = 2, **overrides: object) -> CheckoutRequest:
    data: dict[str, object] = {
        "items": [OrderItemCreate(product_id=product.id, quantity=quantity, is_exchange=False)],
        "customer_name": "Nguyen Van A",
        "customer_phone": "0901234567",
        "delivery_address": "123 Nguyen Trai",
        "delivery_ward": "Phuong Ben Thanh",
        "delivery_city": "TP. Hồ Chí Minh",
        "payment_method": "cod",
        "vat_invoice_requested": False,
    }
    data.update(overrides)
    return CheckoutRequest.model_validate(data)


# --- compute_discount -------------------------------------------------------


def test_compute_discount_percent() -> None:
    coupon = Coupon(discount_type="percent", value=Decimal("10"), min_order=Decimal("0"))
    assert compute_discount(coupon, Decimal("700000")) == Decimal("70000.00")


def test_compute_discount_fixed() -> None:
    coupon = Coupon(discount_type="fixed", value=Decimal("50000"), min_order=Decimal("0"))
    assert compute_discount(coupon, Decimal("700000")) == Decimal("50000")


def test_compute_discount_percent_capped_by_max() -> None:
    coupon = Coupon(
        discount_type="percent",
        value=Decimal("50"),
        min_order=Decimal("0"),
        max_discount=Decimal("100000"),
    )
    assert compute_discount(coupon, Decimal("700000")) == Decimal("100000")


def test_compute_discount_never_exceeds_subtotal() -> None:
    coupon = Coupon(discount_type="fixed", value=Decimal("900000"), min_order=Decimal("0"))
    assert compute_discount(coupon, Decimal("700000")) == Decimal("700000")


# --- validate_coupon --------------------------------------------------------


async def test_validate_percent_coupon(order_session: AsyncSession) -> None:
    await seed_coupon(order_session, code="SAVE10", discount_type="percent", value=Decimal("10"))
    result = await coupon_service(order_session).validate_coupon("save10", Decimal("700000"))
    assert result.discount_amount == Decimal("70000.00")
    assert result.code == "SAVE10"


async def test_validate_fixed_coupon(order_session: AsyncSession) -> None:
    await seed_coupon(order_session, code="MINUS50", discount_type="fixed", value=Decimal("50000"))
    result = await coupon_service(order_session).validate_coupon("MINUS50", Decimal("700000"))
    assert result.discount_amount == Decimal("50000")


async def test_validate_min_order_gate(order_session: AsyncSession) -> None:
    await seed_coupon(order_session, code="BIG", min_order=Decimal("1000000"))
    with pytest.raises(CouponError) as exc:
        await coupon_service(order_session).validate_coupon("BIG", Decimal("700000"))
    assert exc.value.error_code == "coupon_min_order"


async def test_validate_expired_coupon(order_session: AsyncSession) -> None:
    past = datetime.now(UTC) - timedelta(days=1)
    await seed_coupon(order_session, code="OLD", ends_at=past)
    with pytest.raises(CouponError) as exc:
        await coupon_service(order_session).validate_coupon("OLD", Decimal("700000"))
    assert exc.value.error_code == "coupon_expired"


async def test_validate_not_started_coupon(order_session: AsyncSession) -> None:
    future = datetime.now(UTC) + timedelta(days=1)
    await seed_coupon(order_session, code="SOON", starts_at=future)
    with pytest.raises(CouponError) as exc:
        await coupon_service(order_session).validate_coupon("SOON", Decimal("700000"))
    assert exc.value.error_code == "coupon_not_started"


async def test_validate_inactive_coupon(order_session: AsyncSession) -> None:
    await seed_coupon(order_session, code="OFF", active=False)
    with pytest.raises(CouponError) as exc:
        await coupon_service(order_session).validate_coupon("OFF", Decimal("700000"))
    assert exc.value.error_code == "coupon_inactive"


async def test_validate_usage_limit_exhausted(order_session: AsyncSession) -> None:
    coupon = await seed_coupon(order_session, code="LIM", usage_limit=1)
    coupon.used_count = 1
    await order_session.commit()
    with pytest.raises(CouponError) as exc:
        await coupon_service(order_session).validate_coupon("LIM", Decimal("700000"))
    assert exc.value.error_code == "coupon_usage_exhausted"


async def test_validate_unknown_coupon(order_session: AsyncSession) -> None:
    with pytest.raises(CouponError) as exc:
        await coupon_service(order_session).validate_coupon("NOPE", Decimal("700000"))
    assert exc.value.error_code == "coupon_not_found"


# --- order creation with coupons -------------------------------------------


async def test_order_applies_percent_coupon(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    await seed_coupon(order_session, code="SAVE10", discount_type="percent", value=Decimal("10"))

    order = await order_service(order_session).create_order(
        checkout_payload(product, coupon_code="SAVE10"),
        None,
        uuid4(),
        order_session,
    )

    assert order.subtotal == Decimal("700000.00")
    assert order.discount_amount == Decimal("70000.00")
    assert order.coupon_code == "SAVE10"
    assert order.total_amount == Decimal("630000.00")


async def test_order_applies_fixed_coupon_with_shipping(order_session: AsyncSession) -> None:
    water = await create_product(
        order_session,
        sku="WATER-20L",
        price=Decimal("55000"),
    )
    water.category = "nuoc_uong"
    water.unit = "lít"
    await order_session.commit()
    await seed_coupon(order_session, code="MINUS50", discount_type="fixed", value=Decimal("50000"))

    order = await order_service(order_session).create_order(
        checkout_payload(water, quantity=2, coupon_code="MINUS50"),
        None,
        uuid4(),
        order_session,
    )

    # subtotal 110000 + shipping 10000 - discount 50000 = 70000
    assert order.subtotal == Decimal("110000.00")
    assert order.shipping_fee == Decimal("10000.00")
    assert order.discount_amount == Decimal("50000")
    assert order.total_amount == Decimal("70000.00")


async def test_order_discount_never_makes_total_negative(order_session: AsyncSession) -> None:
    product = await create_product(order_session, price=Decimal("100000"))
    await seed_coupon(order_session, code="HUGE", discount_type="fixed", value=Decimal("900000"))

    order = await order_service(order_session).create_order(
        # subtotal 200000, discount capped to subtotal, total 0
        checkout_payload(product, quantity=2, coupon_code="HUGE"),
        None,
        uuid4(),
        order_session,
    )

    assert order.discount_amount == Decimal("200000.00")
    assert order.total_amount == Decimal("0.00")


async def test_order_min_order_gate_blocks(order_session: AsyncSession) -> None:
    product = await create_product(order_session, price=Decimal("100000"))
    await seed_coupon(order_session, code="BIG", min_order=Decimal("1000000"))

    with pytest.raises(CouponError):
        await order_service(order_session).create_order(
            checkout_payload(product, quantity=1, coupon_code="BIG"),
            None,
            uuid4(),
            order_session,
        )


async def test_order_records_redemption_and_increments_used_count(
    order_session: AsyncSession,
) -> None:
    product = await create_product(order_session)
    coupon = await seed_coupon(order_session, code="SAVE10", usage_limit=5)

    await order_service(order_session).create_order(
        checkout_payload(product, coupon_code="SAVE10"),
        None,
        uuid4(),
        order_session,
    )
    await order_session.commit()

    refreshed = await CouponRepository(order_session).get_by_code("SAVE10")
    assert refreshed is not None
    assert refreshed.used_count == 1
    redemptions = (
        (
            await order_session.execute(
                select(CouponRedemption).where(CouponRedemption.coupon_id == coupon.id)
            )
        )
        .scalars()
        .all()
    )
    assert len(redemptions) == 1
    assert redemptions[0].coupon_id == coupon.id


async def test_order_per_user_limit_enforced(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=10)
    user = await create_user(order_session)
    await seed_coupon(order_session, code="ONCE", per_user_limit=1)

    await order_service(order_session).create_order(
        checkout_payload(product, coupon_code="ONCE"),
        user,
        uuid4(),
        order_session,
    )
    await order_session.commit()

    with pytest.raises(CouponError) as exc:
        await order_service(order_session).create_order(
            checkout_payload(product, coupon_code="ONCE"),
            user,
            uuid4(),
            order_session,
        )
    assert exc.value.error_code == "coupon_per_user_exhausted"


async def test_per_user_limit_requires_account(order_session: AsyncSession) -> None:
    product = await create_product(order_session)
    await seed_coupon(order_session, code="ACCT", per_user_limit=1)

    with pytest.raises(CouponError) as exc:
        await order_service(order_session).create_order(
            checkout_payload(product, coupon_code="ACCT"),
            None,
            uuid4(),
            order_session,
        )
    assert exc.value.error_code == "coupon_requires_account"


async def test_order_without_coupon_has_zero_discount(order_session: AsyncSession) -> None:
    product = await create_product(order_session)

    order = await order_service(order_session).create_order(
        checkout_payload(product),
        None,
        uuid4(),
        order_session,
    )

    assert order.discount_amount == Decimal("0.00")
    assert order.coupon_code is None


async def test_concurrent_coupon_usage_respects_limit(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=20)
    await seed_coupon(order_session, code="LIMIT3", discount_type="fixed", value=Decimal("10000"))
    coupon = await CouponRepository(order_session).get_by_code("LIMIT3")
    assert coupon is not None
    coupon.usage_limit = 3
    await order_session.commit()

    async def attempt() -> bool:
        async with AsyncSessionLocal() as session:
            try:
                await order_service(session).create_order(
                    checkout_payload(
                        product,
                        quantity=1,
                        items=[OrderItemCreate(product_id=product.id, quantity=1)],
                        coupon_code="LIMIT3",
                    ),
                    None,
                    uuid4(),
                    session,
                )
                await session.commit()
                return True
            except (DBAPIError, CouponError, ValidationException):
                await session.rollback()
                return False

    results = await asyncio.gather(*(attempt() for _ in range(10)))
    successful = sum(results)

    refreshed = await CouponRepository(order_session).get_by_code("LIMIT3")
    assert refreshed is not None
    await order_session.refresh(refreshed)
    # The row lock plus SERIALIZABLE isolation prevents oversell: used_count can
    # never exceed usage_limit, and every committed order maps to one redemption.
    # Some contenders hit serialization failures and roll back rather than retry
    # (retries live in the endpoint), so the exact count is not deterministic.
    assert 0 < successful <= 3
    assert refreshed.used_count == successful


# --- admin CRUD -------------------------------------------------------------


async def test_admin_creates_and_lists_coupons(order_session: AsyncSession) -> None:
    admin = user_model("admin")
    service = coupon_service(order_session)

    created = await service.create_coupon(coupon_create(code="new10"), admin)
    await order_session.commit()
    assert created.code == "NEW10"

    listed = await service.list_coupons(CouponSearchParams(), admin)
    assert listed.total == 1


async def test_non_admin_cannot_create_coupon(order_session: AsyncSession) -> None:
    customer = user_model("customer")
    with pytest.raises(ForbiddenException):
        await coupon_service(order_session).create_coupon(coupon_create(), customer)


async def test_admin_can_disable_coupon(order_session: AsyncSession) -> None:
    admin = user_model("admin")
    coupon = await seed_coupon(order_session, code="TODISABLE")

    updated = await coupon_service(order_session).update_coupon(
        coupon.id, CouponUpdate(active=False), admin
    )
    await order_session.commit()
    assert updated.active is False


async def test_update_rejects_percent_over_100(order_session: AsyncSession) -> None:
    admin = user_model("admin")
    coupon = await seed_coupon(
        order_session, code="PCT", discount_type="percent", value=Decimal("10")
    )

    with pytest.raises(ValidationException):
        await coupon_service(order_session).update_coupon(
            coupon.id, CouponUpdate(value=Decimal("150")), admin
        )


def test_coupon_code_normalized_and_validated() -> None:
    payload = coupon_create(code="  save-20 ")
    assert payload.code == "SAVE-20"
    with pytest.raises(ValueError):
        coupon_create(code="bad code!")


def test_percent_over_100_rejected_at_schema() -> None:
    with pytest.raises(ValueError):
        coupon_create(discount_type="percent", value=Decimal("150"))
