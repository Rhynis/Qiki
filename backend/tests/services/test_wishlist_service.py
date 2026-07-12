"""Unit tests for WishlistService with fake repositories."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.core.exceptions import NotFoundException
from app.models.product import Product
from app.services.wishlist_service import WishlistService

pytestmark = pytest.mark.asyncio


def make_product(*, is_active: bool = True) -> Product:
    now = datetime.now(UTC)
    return Product(
        id=uuid4(),
        sku="GAS-12-SP",
        name="Binh gas 12kg",
        brand="Saigon Petro",
        size_kg=Decimal("12"),
        category="gas",
        unit="kg",
        price=Decimal("350000"),
        stock_quantity=10,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


class FakeProductRepository:
    def __init__(self, product: Product | None) -> None:
        self.product = product

    async def get_by_id(self, product_id: UUID, *, active_only: bool = False) -> Product | None:
        if self.product is None or self.product.id != product_id:
            return None
        if active_only and not self.product.is_active:
            return None
        return self.product


class FakeWishlistRepository:
    def __init__(self, products: list[Product] | None = None) -> None:
        self.added: list[tuple[UUID, UUID]] = []
        self.removed: list[tuple[UUID, UUID]] = []
        self.products = products or []

    async def add(self, user_id: UUID, product_id: UUID) -> None:
        self.added.append((user_id, product_id))

    async def remove(self, user_id: UUID, product_id: UUID) -> None:
        self.removed.append((user_id, product_id))

    async def list_products(self, user_id: UUID) -> list[Product]:
        return self.products


async def test_add_product_saves_existing_product() -> None:
    product = make_product()
    wishlist_repo = FakeWishlistRepository()
    service = WishlistService(wishlist_repo, FakeProductRepository(product))  # type: ignore[arg-type]
    user_id = uuid4()

    await service.add_product(user_id, product.id)

    assert wishlist_repo.added == [(user_id, product.id)]


async def test_add_unknown_product_raises_not_found() -> None:
    service = WishlistService(FakeWishlistRepository(), FakeProductRepository(None))  # type: ignore[arg-type]

    with pytest.raises(NotFoundException):
        await service.add_product(uuid4(), uuid4())


async def test_add_inactive_product_raises_not_found() -> None:
    product = make_product(is_active=False)
    service = WishlistService(FakeWishlistRepository(), FakeProductRepository(product))  # type: ignore[arg-type]

    with pytest.raises(NotFoundException):
        await service.add_product(uuid4(), product.id)


async def test_list_products_returns_responses() -> None:
    product = make_product()
    service = WishlistService(FakeWishlistRepository([product]), FakeProductRepository(product))  # type: ignore[arg-type]

    items = await service.list_products(uuid4())

    assert [item.id for item in items] == [product.id]


async def test_remove_product_delegates_to_repository() -> None:
    wishlist_repo = FakeWishlistRepository()
    service = WishlistService(wishlist_repo, FakeProductRepository(None))  # type: ignore[arg-type]
    user_id, product_id = uuid4(), uuid4()

    await service.remove_product(user_id, product_id)

    assert wishlist_repo.removed == [(user_id, product_id)]
