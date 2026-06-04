"""Tests for admin dashboard endpoints."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.exceptions import ForbiddenException
from app.main import app
from app.models.order import Order
from app.models.product import Product
from app.models.user import User

pytestmark = pytest.mark.asyncio


def admin_user() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        full_name="Admin User",
        phone="0900000000",
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def db_user(email: str, *, created_at: datetime | None = None) -> User:
    now = created_at or datetime.now(UTC)
    return User(
        id=uuid4(),
        email=email,
        hashed_password="hashed",
        full_name="Customer User",
        phone="0900000001",
        role="customer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def db_product(
    sku: str,
    *,
    stock_quantity: int,
    is_active: bool = True,
) -> Product:
    now = datetime.now(UTC)
    return Product(
        id=uuid4(),
        sku=sku,
        name=f"Product {sku}",
        brand="Saigon Petro",
        size_kg=Decimal("12"),
        category="gas",
        unit="kg",
        price=Decimal("350000"),
        stock_quantity=stock_quantity,
        description="Binh gas gia dinh",
        image_url="https://example.com/gas.jpg",
        safety_info="Dat binh noi thoang khi.",
        pricing_note=None,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def db_order(
    order_number: str,
    *,
    status: str = "pending",
    total_amount: Decimal = Decimal("350000"),
    created_at: datetime | None = None,
) -> Order:
    now = created_at or datetime.now(UTC)
    return Order(
        id=uuid4(),
        order_number=order_number,
        customer_name="Nguyen Van A",
        customer_phone="0901234567",
        customer_email="customer@example.com",
        delivery_address="123 Nguyen Trai",
        delivery_city="TP. Hồ Chí Minh",
        subtotal=total_amount,
        shipping_fee=Decimal("0"),
        total_amount=total_amount,
        vat_invoice_requested=False,
        payment_method="cod",
        payment_status="pending",
        status=status,
        source="website",
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def override_admin() -> object:
    app.dependency_overrides[get_current_admin] = admin_user
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def override_forbidden_admin() -> object:
    def forbidden_admin() -> User:
        raise ForbiddenException("Admin role required", error_code="admin_required")

    app.dependency_overrides[get_current_admin] = forbidden_admin
    yield
    app.dependency_overrides.clear()


async def test_dashboard_requires_admin(
    test_client: AsyncClient,
    override_forbidden_admin: object,
) -> None:
    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 403


async def test_dashboard_returns_zero_metrics_when_empty(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    assert response.json() == {
        "orders_today": 0,
        "orders_pending": 0,
        "revenue_today": 0,
        "low_stock_count": 0,
        "users_total": 0,
        "users_new_today": 0,
    }


async def test_dashboard_counts_today_orders_and_pending_orders(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    order_session.add_all(
        [
            db_order("ORD-TODAY-1", status="pending"),
            db_order("ORD-TODAY-2", status="confirmed"),
            db_order("ORD-OLD-1", status="delivered", created_at=yesterday),
        ]
    )
    await order_session.commit()

    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["orders_today"] == 2
    assert data["orders_pending"] == 1


async def test_dashboard_excludes_cancelled_orders_from_revenue(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    order_session.add_all(
        [
            db_order("ORD-PAID-1", status="confirmed", total_amount=Decimal("400000")),
            db_order("ORD-CAN-1", status="cancelled", total_amount=Decimal("200000")),
        ]
    )
    await order_session.commit()

    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    assert response.json()["revenue_today"] == 400000


async def test_dashboard_counts_low_stock_active_products(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    order_session.add_all(
        [
            db_product("LOW-1", stock_quantity=2),
            db_product("LOW-2", stock_quantity=10),
            db_product("ENOUGH-1", stock_quantity=20),
            db_product("INACTIVE-LOW", stock_quantity=1, is_active=False),
        ]
    )
    await order_session.commit()

    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    assert response.json()["low_stock_count"] == 2


async def test_dashboard_counts_total_and_new_users(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    yesterday = datetime.now(UTC) - timedelta(days=1)
    order_session.add_all(
        [
            db_user("new-a@example.com"),
            db_user("new-b@example.com"),
            db_user("old@example.com", created_at=yesterday),
        ]
    )
    await order_session.commit()

    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    data = response.json()
    assert data["users_total"] == 3
    assert data["users_new_today"] == 2


async def test_dashboard_returns_all_expected_metric_keys(
    test_client: AsyncClient,
    order_session: AsyncSession,
    override_admin: object,
) -> None:
    response = await test_client.get("/api/v1/admin/dashboard")

    assert response.status_code == 200
    assert set(response.json()) == {
        "orders_today",
        "orders_pending",
        "revenue_today",
        "low_stock_count",
        "users_total",
        "users_new_today",
    }
