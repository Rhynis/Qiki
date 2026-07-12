"""Tests for reorder and best-seller order-service features."""

import itertools
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.product import Product
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.order import CheckoutRequest, OrderItemCreate
from app.schemas.product import ProductCreate
from app.services.order_service import OrderService

pytestmark = pytest.mark.asyncio


_PHONE_COUNTER = itertools.count(1)


def user_model(role: str = "customer", *, phone: str | None = None) -> User:
    now = datetime.now(UTC)
    # Each user needs a distinct phone: the column is uniquely constrained, so
    # tests that create several users must not collide on a shared default.
    unique_phone = phone or f"+8490{next(_PHONE_COUNTER):07d}"
    return User(
        id=uuid4(),
        email=f"{role}-{uuid4().hex}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone=unique_phone,
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
    name: str = "Binh gas 12kg",
    brand: str = "Saigon Petro",
    size_kg: Decimal = Decimal("12"),
    category: Literal["gas", "nuoc_uong"] = "gas",
    unit: Literal["kg", "lít"] = "kg",
    price: Decimal = Decimal("350000"),
    stock_quantity: int = 20,
    is_active: bool = True,
) -> Product:
    product = await ProductRepository(session).create(
        ProductCreate(
            sku=sku,
            name=name,
            brand=brand,
            size_kg=size_kg,
            category=category,
            unit=unit,
            price=price,
            stock_quantity=stock_quantity,
            description="San pham giao tan noi",
            image_url="https://example.com/gas-12kg.jpg",
            safety_info="Dat binh noi thoang khi.",
        )
    )
    product.is_active = is_active
    await session.commit()
    return product


def service(session: AsyncSession) -> OrderService:
    return OrderService(OrderRepository(session), ProductRepository(session))


async def place_order(
    session: AsyncSession,
    user: User | None,
    items: list[OrderItemCreate],
) -> object:
    payload = CheckoutRequest.model_validate(
        {
            "items": items,
            "customer_name": "Nguyen Van A",
            "customer_phone": "0901234567",
            "customer_email": "customer@example.com",
            "delivery_address": "123 Nguyen Trai",
            "delivery_ward": "Phuong Ben Thanh",
            "delivery_district": "Quan 1",
            "delivery_city": "TP. Hồ Chí Minh",
            "payment_method": "cod",
            "vat_invoice_requested": False,
        }
    )
    order = await service(session).create_order(payload, user, uuid4(), session)
    await session.commit()
    return order


async def test_reorder_uses_current_price(order_session: AsyncSession) -> None:
    product = await create_product(order_session, price=Decimal("350000"), stock_quantity=10)
    user = await create_user(order_session)
    order = await place_order(
        order_session, user, [OrderItemCreate(product_id=product.id, quantity=2)]
    )

    # Price changes after the order was placed; reorder must reflect the new price.
    await ProductRepository(order_session).update(product.id, {"price": Decimal("400000")})
    await order_session.commit()

    result = await service(order_session).reorder(order.id, user)

    assert len(result.items) == 1
    assert result.skipped == []
    assert result.items[0].product_id == product.id
    assert result.items[0].price == Decimal("400000")
    assert result.items[0].quantity == 2


async def test_reorder_skips_inactive_product(order_session: AsyncSession) -> None:
    active = await create_product(order_session, sku="GAS-12-A", stock_quantity=5)
    inactive = await create_product(order_session, sku="GAS-12-B", name="Binh gas cu")
    user = await create_user(order_session)
    order = await place_order(
        order_session,
        user,
        [
            OrderItemCreate(product_id=active.id, quantity=1),
            OrderItemCreate(product_id=inactive.id, quantity=1),
        ],
    )

    await ProductRepository(order_session).update(inactive.id, {"is_active": False})
    await order_session.commit()

    result = await service(order_session).reorder(order.id, user)

    assert [item.product_id for item in result.items] == [active.id]
    assert len(result.skipped) == 1
    assert result.skipped[0].product_id == inactive.id
    assert result.skipped[0].reason == "inactive"


async def test_reorder_skips_out_of_stock_product(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=5)
    user = await create_user(order_session)
    order = await place_order(
        order_session, user, [OrderItemCreate(product_id=product.id, quantity=2)]
    )

    await ProductRepository(order_session).update(product.id, {"stock_quantity": 0})
    await order_session.commit()

    result = await service(order_session).reorder(order.id, user)

    assert result.items == []
    assert len(result.skipped) == 1
    assert result.skipped[0].reason == "out_of_stock"


async def test_reorder_caps_quantity_at_available_stock(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=10)
    user = await create_user(order_session)
    order = await place_order(
        order_session, user, [OrderItemCreate(product_id=product.id, quantity=6)]
    )

    await ProductRepository(order_session).update(product.id, {"stock_quantity": 3})
    await order_session.commit()

    result = await service(order_session).reorder(order.id, user)

    assert result.items[0].quantity == 3


async def test_reorder_rejects_other_users_order(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=5)
    owner = await create_user(order_session)
    other = await create_user(order_session, role="customer")
    order = await place_order(
        order_session, owner, [OrderItemCreate(product_id=product.id, quantity=1)]
    )

    with pytest.raises(ForbiddenException):
        await service(order_session).reorder(order.id, other)


async def test_reorder_missing_order_raises(order_session: AsyncSession) -> None:
    user = await create_user(order_session)

    with pytest.raises(NotFoundException):
        await service(order_session).reorder(uuid4(), user)


async def test_best_sellers_orders_by_total_quantity(order_session: AsyncSession) -> None:
    popular = await create_product(order_session, sku="GAS-12-POP", name="Binh pho bien")
    niche = await create_product(order_session, sku="GAS-12-NICHE", name="Binh it ban")
    user = await create_user(order_session)
    await place_order(order_session, user, [OrderItemCreate(product_id=popular.id, quantity=5)])
    await place_order(order_session, user, [OrderItemCreate(product_id=niche.id, quantity=1)])

    result = await service(order_session).get_best_sellers(limit=8)

    assert [item.id for item in result] == [popular.id, niche.id]
    assert result[0].total_sold == 5
    assert result[1].total_sold == 1


async def test_best_sellers_excludes_inactive_products(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=10)
    user = await create_user(order_session)
    await place_order(order_session, user, [OrderItemCreate(product_id=product.id, quantity=3)])

    await ProductRepository(order_session).update(product.id, {"is_active": False})
    await order_session.commit()

    result = await service(order_session).get_best_sellers(limit=8)

    assert result == []


async def test_best_sellers_ignores_cancelled_orders(order_session: AsyncSession) -> None:
    product = await create_product(order_session, stock_quantity=10)
    user = await create_user(order_session)
    order = await place_order(
        order_session, user, [OrderItemCreate(product_id=product.id, quantity=4)]
    )
    await service(order_session).cancel_order(order.id, user)
    await order_session.commit()

    result = await service(order_session).get_best_sellers(limit=8)

    assert result == []


async def test_best_sellers_respects_limit(order_session: AsyncSession) -> None:
    user = await create_user(order_session)
    for index in range(3):
        product = await create_product(
            order_session,
            sku=f"GAS-12-{index}",
            name=f"Binh {index}",
            stock_quantity=10,
        )
        await place_order(
            order_session,
            user,
            [OrderItemCreate(product_id=product.id, quantity=index + 1)],
        )

    result = await service(order_session).get_best_sellers(limit=2)

    assert len(result) == 2
