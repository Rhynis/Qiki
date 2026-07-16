"""Tests for the staff delivery endpoints (multi-delivery per order)."""

import asyncio
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import (
    get_current_active_user,
    get_current_staff,
    get_current_user_optional,
)
from app.core.exceptions import ValidationException
from app.db.session import AsyncSessionLocal
from app.main import app
from app.models.order import Order
from app.models.user import User
from app.repositories.delivery_repository import DeliveryRepository
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import UserRepository
from app.schemas.delivery import DeliveryCreate, DeliveryItemCreate
from app.schemas.product import ProductCreate
from app.services.delivery_service import DeliveryService

pytestmark = pytest.mark.asyncio


def build_service(session: AsyncSession) -> DeliveryService:
    return DeliveryService(
        DeliveryRepository(session),
        OrderRepository(session),
        UserRepository(session),
    )


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


def _user(role: str) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=f"{role}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone=f"+8490{uuid4().int % 10000000:07d}",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def test_driver_section_role_gating(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    app.dependency_overrides[get_current_active_user] = lambda: _user("customer")
    blocked = await test_client.get("/api/v1/driver/deliveries")
    assert blocked.status_code == 403

    app.dependency_overrides[get_current_active_user] = lambda: _user("driver")
    driver_ok = await test_client.get("/api/v1/driver/deliveries")
    assert driver_ok.status_code == 200

    app.dependency_overrides[get_current_active_user] = lambda: _user("admin")
    admin_ok = await test_client.get("/api/v1/driver/deliveries")
    assert admin_ok.status_code == 200
    app.dependency_overrides.clear()


async def test_assign_driver_then_driver_updates_status_without_location(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    driver = _user("driver")
    order_session.add(driver)
    await order_session.commit()

    staff = staff_user()
    app.dependency_overrides[get_current_staff] = lambda: staff
    app.dependency_overrides[get_current_user_optional] = lambda: staff
    order = await create_db_order(order_session)
    item_id = order_item_id(order)
    delivery = (
        await test_client.post(
            f"/api/v1/admin/orders/{order.id}/deliveries",
            json={"items": [{"order_item_id": item_id, "quantity": 3}]},
        )
    ).json()

    assigned = await test_client.patch(
        f"/api/v1/admin/deliveries/{delivery['id']}/assign",
        json={"driver_id": str(driver.id)},
    )
    assert assigned.status_code == 200
    assert assigned.json()["driver_id"] == str(driver.id)

    # Switch identity to the assigned driver.
    app.dependency_overrides[get_current_active_user] = lambda: driver
    listed = await test_client.get("/api/v1/driver/deliveries")
    assert listed.status_code == 200
    assert any(item["id"] == delivery["id"] for item in listed.json())

    # Mark delivered WITHOUT a location; it must still succeed.
    done = await test_client.patch(
        f"/api/v1/driver/deliveries/{delivery['id']}/status",
        json={"status": "delivered"},
    )
    assert done.status_code == 200
    body = done.json()
    assert body["status"] == "delivered"
    assert body["last_lat"] is None
    assert body["last_lng"] is None
    app.dependency_overrides.clear()


async def test_driver_cannot_update_unassigned_delivery(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    staff = staff_user()
    app.dependency_overrides[get_current_staff] = lambda: staff
    app.dependency_overrides[get_current_user_optional] = lambda: staff
    order = await create_db_order(order_session)
    item_id = order_item_id(order)
    delivery = (
        await test_client.post(
            f"/api/v1/admin/orders/{order.id}/deliveries",
            json={"items": [{"order_item_id": item_id, "quantity": 3}]},
        )
    ).json()

    # A different driver (never assigned) must not be able to touch it.
    other_driver = _user("driver")
    app.dependency_overrides[get_current_active_user] = lambda: other_driver
    failed = await test_client.patch(
        f"/api/v1/driver/deliveries/{delivery['id']}/status",
        json={"status": "failed", "lat": 10.8, "lng": 106.7},
    )
    assert failed.status_code == 404
    app.dependency_overrides.clear()


async def test_assign_rejects_non_driver_user(
    test_client: AsyncClient,
    order_session: AsyncSession,
) -> None:
    customer = _user("customer")
    order_session.add(customer)
    await order_session.commit()

    staff = staff_user()
    app.dependency_overrides[get_current_staff] = lambda: staff
    app.dependency_overrides[get_current_user_optional] = lambda: staff
    order = await create_db_order(order_session)
    item_id = order_item_id(order)
    delivery = (
        await test_client.post(
            f"/api/v1/admin/orders/{order.id}/deliveries",
            json={"items": [{"order_item_id": item_id, "quantity": 3}]},
        )
    ).json()

    rejected = await test_client.patch(
        f"/api/v1/admin/deliveries/{delivery['id']}/assign",
        json={"driver_id": str(customer.id)},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error_code"] == "invalid_driver"
    app.dependency_overrides.clear()


async def test_concurrent_create_delivery_does_not_over_allocate(
    order_session: AsyncSession,
) -> None:
    # One item with quantity 2; two parallel creates each ask for the full 2.
    order = await create_db_order(order_session, quantity=2)
    item_id = order.items[0].id

    async def attempt() -> bool:
        async with AsyncSessionLocal() as session:
            try:
                await build_service(session).create_delivery(
                    order.id,
                    DeliveryCreate(items=[DeliveryItemCreate(order_item_id=item_id, quantity=2)]),
                )
                await session.commit()
                return True
            except (ValidationException, IntegrityError, DBAPIError):
                await session.rollback()
                return False

    results = await asyncio.gather(*(attempt() for _ in range(2)))

    # The order-row lock serializes the two creates: exactly one wins.
    assert sum(results) == 1
    deliveries = await DeliveryRepository(order_session).list_by_order(order.id)
    total_allocated = sum(item.quantity for delivery in deliveries for item in delivery.items)
    assert total_allocated == 2


async def test_duplicate_delivery_code_rejected(order_session: AsyncSession) -> None:
    order = await create_db_order(order_session, quantity=3)
    repo = DeliveryRepository(order_session)
    item_rows = [{"order_item_id": order.items[0].id, "quantity": 1}]

    await repo.create(order.id, "DUP-CODE", "pending", None, None, item_rows)
    await order_session.commit()

    with pytest.raises((IntegrityError, DBAPIError)):
        await repo.create(order.id, "DUP-CODE", "pending", None, None, item_rows)
    await order_session.rollback()
