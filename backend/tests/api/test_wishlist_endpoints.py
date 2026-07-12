"""Tests for the customer wishlist API endpoints."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import get_current_active_user
from app.main import app
from app.models.product import Product
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate

pytestmark = pytest.mark.asyncio


async def create_db_user(session: AsyncSession) -> User:
    now = datetime.now(UTC)
    user = User(
        id=uuid4(),
        email="customer@example.com",
        hashed_password="hashed",
        full_name="Nguyen Van A",
        phone="+84901234567",
        role="customer",
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    session.add(user)
    await session.commit()
    return user


async def create_db_product(session: AsyncSession, sku_suffix: str = "") -> Product:
    product = await ProductRepository(session).create(
        ProductCreate(
            sku=f"GAS-{uuid4().hex[:8].upper()}{sku_suffix}",
            name="Binh gas 12kg",
            brand="Saigon Petro",
            size_kg=Decimal("12"),
            price=Decimal("350000"),
            stock_quantity=10,
        )
    )
    await session.commit()
    return product


@pytest.fixture
async def authed_user(order_session: AsyncSession) -> AsyncIterator[User]:
    """Persist a customer and authenticate every request as them."""
    user = await create_db_user(order_session)
    app.dependency_overrides[get_current_active_user] = lambda: user
    yield user
    app.dependency_overrides.clear()


async def test_wishlist_requires_authentication(test_client: AsyncClient) -> None:
    response = await test_client.get("/api/v1/wishlist")

    assert response.status_code == 401


async def test_add_and_list_wishlist(
    test_client: AsyncClient,
    order_session: AsyncSession,
    authed_user: User,
) -> None:
    product = await create_db_product(order_session)

    add = await test_client.post(f"/api/v1/wishlist/{product.id}")
    assert add.status_code == 204

    listing = await test_client.get("/api/v1/wishlist")
    assert listing.status_code == 200
    body = listing.json()
    assert [item["id"] for item in body] == [str(product.id)]


async def test_add_is_idempotent(
    test_client: AsyncClient,
    order_session: AsyncSession,
    authed_user: User,
) -> None:
    product = await create_db_product(order_session)

    first = await test_client.post(f"/api/v1/wishlist/{product.id}")
    second = await test_client.post(f"/api/v1/wishlist/{product.id}")

    assert first.status_code == 204
    assert second.status_code == 204
    listing = await test_client.get("/api/v1/wishlist")
    assert len(listing.json()) == 1  # deduplicated by the unique constraint


async def test_add_unknown_product_returns_404(
    test_client: AsyncClient,
    authed_user: User,
) -> None:
    response = await test_client.post(f"/api/v1/wishlist/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["error_code"] == "product_not_found"


async def test_list_excludes_deactivated_products(
    test_client: AsyncClient,
    order_session: AsyncSession,
    authed_user: User,
) -> None:
    product = await create_db_product(order_session)
    await test_client.post(f"/api/v1/wishlist/{product.id}")

    product.is_active = False
    await order_session.commit()

    listing = await test_client.get("/api/v1/wishlist")
    assert listing.status_code == 200
    assert listing.json() == []  # a discontinued product is hidden from the wishlist


async def test_remove_from_wishlist_is_idempotent(
    test_client: AsyncClient,
    order_session: AsyncSession,
    authed_user: User,
) -> None:
    product = await create_db_product(order_session)
    await test_client.post(f"/api/v1/wishlist/{product.id}")

    first = await test_client.delete(f"/api/v1/wishlist/{product.id}")
    second = await test_client.delete(f"/api/v1/wishlist/{product.id}")

    assert first.status_code == 204
    assert second.status_code == 204  # removing an absent product is a no-op
    listing = await test_client.get("/api/v1/wishlist")
    assert listing.json() == []
