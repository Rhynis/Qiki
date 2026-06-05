"""Tests for product API endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_admin
from app.core.exceptions import ForbiddenException
from app.main import app
from app.models.product import Product
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate

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


def product_payload(sku: str = "GAS-12-SAIGON") -> dict[str, object]:
    return {
        "sku": sku,
        "name": "Binh gas 12kg",
        "brand": "Saigon Petro",
        "size_kg": "12",
        "category": "gas",
        "unit": "kg",
        "price": "350000",
        "stock_quantity": 20,
        "description": "Binh gas gia dinh",
        "image_url": "https://example.com/gas-12kg.jpg",
        "safety_info": "Dat binh noi thoang khi.",
    }


async def create_db_product(
    session: AsyncSession,
    *,
    sku: str = "GAS-12-SAIGON",
    brand: str = "Saigon Petro",
    name: str = "Binh gas 12kg",
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
            description="Binh gas gia dinh",
            image_url="https://example.com/gas-12kg.jpg",
            safety_info="Dat binh noi thoang khi.",
        )
    )
    product.is_active = is_active
    await session.commit()
    return product


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


async def test_list_products_returns_active_products(
    test_client: AsyncClient,
    product_session: AsyncSession,
) -> None:
    await create_db_product(product_session, sku="ACTIVE-12")
    await create_db_product(product_session, sku="INACTIVE-12", is_active=False)

    response = await test_client.get("/api/v1/products")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku"] == "ACTIVE-12"


async def test_list_products_filters_by_brand(
    test_client: AsyncClient,
    product_session: AsyncSession,
) -> None:
    await create_db_product(product_session, sku="SAIGON-12", brand="Saigon Petro")
    await create_db_product(product_session, sku="SHELL-12", brand="Shell")

    response = await test_client.get("/api/v1/products", params={"brand": "Shell"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["brand"] == "Shell"


async def test_list_products_filters_by_category(
    test_client: AsyncClient,
    product_session: AsyncSession,
) -> None:
    await create_db_product(product_session, sku="GAS-12", category="gas", unit="kg")
    await create_db_product(
        product_session,
        sku="VIHAWA-20L",
        name="Nuoc Vihawa 20 lit",
        brand="Vihawa",
        size_kg=Decimal("20"),
        category="nuoc_uong",
        unit="lít",
        price=Decimal("50000"),
    )

    response = await test_client.get("/api/v1/products", params={"category": "nuoc_uong"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["items"][0]["sku"] == "VIHAWA-20L"
    assert data["items"][0]["unit"] == "lít"


async def test_get_product_by_id(
    test_client: AsyncClient,
    product_session: AsyncSession,
) -> None:
    product = await create_db_product(product_session)

    response = await test_client.get(f"/api/v1/products/{product.id}")

    assert response.status_code == 200
    assert response.json()["sku"] == "GAS-12-SAIGON"


async def test_get_product_by_sku(
    test_client: AsyncClient,
    product_session: AsyncSession,
) -> None:
    await create_db_product(product_session, sku="GAS-45-SAIGON")

    response = await test_client.get("/api/v1/products/sku/GAS-45-SAIGON")

    assert response.status_code == 200
    assert response.json()["sku"] == "GAS-45-SAIGON"


async def test_create_product_requires_admin(
    test_client: AsyncClient,
    override_forbidden_admin: object,
) -> None:
    response = await test_client.post("/api/v1/products", json=product_payload())

    assert response.status_code == 403


async def test_create_product_as_admin(
    test_client: AsyncClient,
    product_session: AsyncSession,
    override_admin: object,
) -> None:
    response = await test_client.post("/api/v1/products", json=product_payload())

    assert response.status_code == 201
    assert response.json()["sku"] == "GAS-12-SAIGON"
    assert response.json()["category"] == "gas"
    assert await ProductRepository(product_session).get_by_sku("GAS-12-SAIGON") is not None


async def test_patch_product_as_admin(
    test_client: AsyncClient,
    product_session: AsyncSession,
    override_admin: object,
) -> None:
    product = await create_db_product(product_session)

    response = await test_client.patch(
        f"/api/v1/products/{product.id}",
        json={"price": "360000", "stock_quantity": 7},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["price"] == "360000.00"
    assert data["stock_quantity"] == 7


async def test_delete_product_soft_deletes(
    test_client: AsyncClient,
    product_session: AsyncSession,
    override_admin: object,
) -> None:
    product = await create_db_product(product_session)

    response = await test_client.delete(f"/api/v1/products/{product.id}")

    assert response.status_code == 204
    assert await ProductRepository(product_session).get_by_id(product.id, active_only=True) is None


async def test_low_stock_endpoint_requires_admin(
    test_client: AsyncClient,
    override_forbidden_admin: object,
) -> None:
    response = await test_client.get("/api/v1/admin/products/low-stock")

    assert response.status_code == 403


async def test_low_stock_endpoint(
    test_client: AsyncClient,
    product_session: AsyncSession,
    override_admin: object,
) -> None:
    await create_db_product(product_session, sku="LOW-12", stock_quantity=3)
    await create_db_product(product_session, sku="ENOUGH-12", stock_quantity=20)

    response = await test_client.get("/api/v1/admin/products/low-stock")

    assert response.status_code == 200
    assert [item["sku"] for item in response.json()] == ["LOW-12"]
