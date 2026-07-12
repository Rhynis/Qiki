"""Tests for the staff delivery endpoints (multi-delivery per order)."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_staff, get_current_user_optional
from app.main import app
from app.models.order import Order
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate

pytestmark = pytest.mark.asyncio


def staff_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="staff@example.com",
        hashed_password="hashed",
        full_name="Staff User",
        phone="+84900000000",
        role="staff",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def create_db_order(session: AsyncSession, quantity: int = 3) -> Order:
    product = await ProductRepository(session).create(
        ProductCreate(
            sku=f"GAS-{uuid4().hex[:8].upper()}",
            name="Binh gas 12kg",
            brand="Saigon Petro",
            size_kg=Decimal("12"),
            price=Decimal("350000"),
            stock_quantity=50,
        )
    )
    order = await OrderRepository(session).create_with_items(
        {
            "user_id": None,
            "customer_name": "Nguyen Van A",
            "customer_phone": "+84901234567",
            "delivery_address": "123 Nguyen Trai",
            "delivery_city": "TP. Hồ Chí Minh",
            "subtotal": Decimal("350000") * quantity,
            "shipping_fee": Decimal("0"),
            "total_amount": Decimal("350000") * quantity,
            "status": "pending",
            "payment_method": "cod",
            "payment_status": "pending",
            "source": "website",
        },
        [
            {
                "product_id": product.id,
                "product_name": product.name,
                "product_brand": product.brand,
                "product_size_kg": product.size_kg,
                "quantity": quantity,
                "unit_price": Decimal("350000"),
                "subtotal": Decimal("350000") * quantity,
            }
        ],
        session,
    )
    await session.commit()
    return order


@pytest.fixture
async def staff_client(order_session: AsyncSession) -> AsyncIterator[None]:
    user = staff_user()
    app.dependency_overrides[get_current_staff] = lambda: user
    app.dependency_overrides[get_current_user_optional] = lambda: user
    yield
    app.dependency_overrides.clear()


def order_item_id(order: Order) -> str:
    return str(order.items[0].id)


async def test_delivery_endpoints_require_staff(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    order = await create_db_order(order_session)
    response = await test_client.get(f"/api/v1/admin/orders/{order.id}/deliveries")
    assert response.status_code == 401


async def test_create_and_list_delivery(
    test_client: AsyncClient,
    order_session: AsyncSession,
    staff_client: None,
) -> None:
    order = await create_db_order(order_session, quantity=3)

    create = await test_client.post(
        f"/api/v1/admin/orders/{order.id}/deliveries",
        json={"items": [{"order_item_id": order_item_id(order), "quantity": 2}]},
    )
    assert create.status_code == 201
    body = create.json()
    assert body["status"] == "pending"
    assert body["code"].endswith("-D1")
    assert body["items"][0]["quantity"] == 2

    listing = await test_client.get(f"/api/v1/admin/orders/{order.id}/deliveries")
    assert listing.status_code == 200
    assert len(listing.json()) == 1


async def test_cannot_over_allocate_across_deliveries(
    test_client: AsyncClient,
    order_session: AsyncSession,
    staff_client: None,
) -> None:
    order = await create_db_order(order_session, quantity=3)
    item_id = order_item_id(order)

    first = await test_client.post(
        f"/api/v1/admin/orders/{order.id}/deliveries",
        json={"items": [{"order_item_id": item_id, "quantity": 2}]},
    )
    assert first.status_code == 201

    # Only 1 remains of the 3 ordered; asking for 2 more must be rejected.
    over = await test_client.post(
        f"/api/v1/admin/orders/{order.id}/deliveries",
        json={"items": [{"order_item_id": item_id, "quantity": 2}]},
    )
    assert over.status_code == 400
    assert over.json()["error_code"] == "delivery_over_allocation"


async def test_unknown_order_item_rejected(
    test_client: AsyncClient,
    order_session: AsyncSession,
    staff_client: None,
) -> None:
    order = await create_db_order(order_session)

    response = await test_client.post(
        f"/api/v1/admin/orders/{order.id}/deliveries",
        json={"items": [{"order_item_id": str(uuid4()), "quantity": 1}]},
    )
    assert response.status_code == 400
    assert response.json()["error_code"] == "delivery_item_invalid"


async def test_status_rollup_to_delivered(
    test_client: AsyncClient,
    order_session: AsyncSession,
    staff_client: None,
) -> None:
    order = await create_db_order(order_session, quantity=2)
    item_id = order_item_id(order)

    delivery = (
        await test_client.post(
            f"/api/v1/admin/orders/{order.id}/deliveries",
            json={"items": [{"order_item_id": item_id, "quantity": 2}]},
        )
    ).json()

    shipping = await test_client.patch(
        f"/api/v1/admin/orders/{order.id}/deliveries/{delivery['id']}",
        json={"status": "shipping"},
    )
    assert shipping.status_code == 200
    order_after_shipping = (await test_client.get(f"/api/v1/orders/{order.id}")).json()
    assert order_after_shipping["status"] == "shipping"

    delivered = await test_client.patch(
        f"/api/v1/admin/orders/{order.id}/deliveries/{delivery['id']}",
        json={"status": "delivered"},
    )
    assert delivered.status_code == 200
    order_after_delivered = (await test_client.get(f"/api/v1/orders/{order.id}")).json()
    assert order_after_delivered["status"] == "delivered"
    assert order_after_delivered["delivered_at"] is not None
