"""Tests for ProductRepository."""

import asyncio
from decimal import Decimal
from typing import Literal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, InsufficientStockException, NotFoundException
from app.db.session import AsyncSessionLocal
from app.models.product import Product
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate, ProductSearchParams

pytestmark = pytest.mark.asyncio


def product_data(
    sku: str = "GAS-12-SAIGON",
    name: str = "Binh gas 12kg",
    brand: str = "Saigon Petro",
    size_kg: Decimal = Decimal("12"),
    category: Literal["gas", "nuoc_uong"] = "gas",
    unit: Literal["kg", "lít"] = "kg",
    price: Decimal = Decimal("350000"),
    stock_quantity: int = 20,
    pricing_note: str | None = None,
) -> ProductCreate:
    """Return valid product creation data."""
    return ProductCreate(
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
        pricing_note=pricing_note,
    )


async def create_product(
    session: AsyncSession,
    **overrides: object,
) -> Product:
    """Create and commit a product for repository tests."""
    data = product_data(**overrides)
    product = await ProductRepository(session).create(data)
    await session.commit()
    return product


async def test_create_product_with_valid_data(product_session: AsyncSession) -> None:
    product = await ProductRepository(product_session).create(product_data())

    assert product.sku == "GAS-12-SAIGON"
    assert product.category == "gas"
    assert product.unit == "kg"
    assert product.is_in_stock()


async def test_create_water_product_allows_20_liters(product_session: AsyncSession) -> None:
    product = await ProductRepository(product_session).create(
        product_data(
            sku="VIHAWA-20L",
            name="Nuoc Vihawa 20 lit",
            brand="Vihawa",
            size_kg=Decimal("20"),
            category="nuoc_uong",
            unit="lít",
            price=Decimal("50000"),
            pricing_note="Gia tai cua hang; giao them phi.",
        )
    )

    assert product.category == "nuoc_uong"
    assert product.unit == "lít"
    assert product.size_kg == Decimal("20")


async def test_create_gas_product_rejects_unsupported_size() -> None:
    with pytest.raises(ValueError, match="size_kg must be one of 6, 12, or 45"):
        product_data(size_kg=Decimal("20"))


async def test_create_product_duplicate_sku_raises(product_session: AsyncSession) -> None:
    repository = ProductRepository(product_session)
    await repository.create(product_data())

    with pytest.raises(ConflictException):
        await repository.create(product_data())


async def test_get_by_id_returns_product(product_session: AsyncSession) -> None:
    product = await create_product(product_session)

    found = await ProductRepository(product_session).get_by_id(product.id)

    assert found is not None
    assert found.sku == product.sku


async def test_list_products_with_search(product_session: AsyncSession) -> None:
    await create_product(product_session, name="Binh gas gia dinh")
    await create_product(product_session, sku="SHELL-45", name="Binh cong nghiep", brand="Shell")

    products, total = await ProductRepository(product_session).list_products(
        ProductSearchParams(search="gia dinh")
    )

    assert total >= 1
    assert any(product.name == "Binh gas gia dinh" for product in products)


async def test_list_products_with_brand_filter(product_session: AsyncSession) -> None:
    await create_product(product_session, brand="Saigon Petro")
    await create_product(product_session, sku="SHELL-12", brand="Shell")

    products, total = await ProductRepository(product_session).list_products(
        ProductSearchParams(brand="Shell")
    )

    assert total == 1
    assert products[0].brand == "Shell"


async def test_list_products_with_category_filter(product_session: AsyncSession) -> None:
    await create_product(product_session, sku="GAS-12", category="gas", unit="kg")
    await create_product(
        product_session,
        sku="VIHAWA-20L",
        name="Nuoc Vihawa 20 lit",
        brand="Vihawa",
        size_kg=Decimal("20"),
        category="nuoc_uong",
        unit="lít",
        price=Decimal("50000"),
    )

    products, total = await ProductRepository(product_session).list_products(
        ProductSearchParams(category="nuoc_uong")
    )

    assert total == 1
    assert products[0].sku == "VIHAWA-20L"


async def test_list_products_with_price_range(product_session: AsyncSession) -> None:
    await create_product(product_session, price=Decimal("350000"))
    await create_product(product_session, sku="GAS-45", price=Decimal("1200000"))

    products, total = await ProductRepository(product_session).list_products(
        ProductSearchParams(min_price=Decimal("300000"), max_price=Decimal("400000"))
    )

    assert total == 1
    assert products[0].price == Decimal("350000")


async def test_list_products_pagination(product_session: AsyncSession) -> None:
    await create_product(product_session, sku="GAS-1", name="Product 1")
    await create_product(product_session, sku="GAS-2", name="Product 2")

    products, total = await ProductRepository(product_session).list_products(
        ProductSearchParams(skip=0, limit=1, sort_by="name", sort_order="asc")
    )

    assert total == 2
    assert len(products) == 1


async def test_get_by_sku_active_only_filters_inactive(product_session: AsyncSession) -> None:
    product = await create_product(product_session)
    product.is_active = False
    await product_session.commit()

    found = await ProductRepository(product_session).get_by_sku(product.sku, active_only=True)

    assert found is None


async def test_update_product_changes_fields(product_session: AsyncSession) -> None:
    product = await create_product(product_session)

    updated = await ProductRepository(product_session).update(
        product.id,
        {"name": "Binh gas moi", "price": Decimal("360000")},
    )

    assert updated.name == "Binh gas moi"
    assert updated.price == Decimal("360000")


async def test_update_product_not_found_raises(product_session: AsyncSession) -> None:
    with pytest.raises(NotFoundException):
        await ProductRepository(product_session).update(
            uuid4(),
            {"name": "Missing"},
        )


async def test_soft_delete_marks_inactive(product_session: AsyncSession) -> None:
    product = await create_product(product_session)

    deleted = await ProductRepository(product_session).soft_delete(product.id)

    assert deleted is True
    assert product.is_active is False


async def test_soft_delete_returns_false_for_missing(product_session: AsyncSession) -> None:
    assert await ProductRepository(product_session).soft_delete(uuid4()) is False


async def test_list_products_with_size_and_stock_filter(product_session: AsyncSession) -> None:
    await create_product(product_session, stock_quantity=5)
    await create_product(product_session, sku="OUT-12", stock_quantity=0)

    products, total = await ProductRepository(product_session).list_products(
        ProductSearchParams(size_kg=Decimal("12"), in_stock_only=True)
    )

    assert total == 1
    assert products[0].stock_quantity == 5


async def test_get_many_for_update_returns_products(product_session: AsyncSession) -> None:
    product = await create_product(product_session)

    async with product_session.begin():
        products = await ProductRepository(product_session).get_many_for_update([product.id])

    assert products[product.id].sku == product.sku


async def test_decrement_stock_decreases_quantity(product_session: AsyncSession) -> None:
    product = await create_product(product_session, stock_quantity=5)

    async with product_session.begin():
        updated = await ProductRepository(product_session).decrement_stock(product.id, 2)

    assert updated.stock_quantity == 3


async def test_decrement_stock_raises_if_insufficient(product_session: AsyncSession) -> None:
    product = await create_product(product_session, stock_quantity=1)

    with pytest.raises(InsufficientStockException):
        async with product_session.begin():
            await ProductRepository(product_session).decrement_stock(product.id, 2)


async def test_decrement_stock_not_found_raises(product_session: AsyncSession) -> None:
    with pytest.raises(NotFoundException):
        async with product_session.begin():
            await ProductRepository(product_session).decrement_stock(uuid4(), 1)


async def test_increment_stock_increases_quantity(product_session: AsyncSession) -> None:
    product = await create_product(product_session, stock_quantity=1)

    async with product_session.begin():
        updated = await ProductRepository(product_session).increment_stock(product.id, 3)

    assert updated.stock_quantity == 4


async def test_increment_stock_not_found_raises(product_session: AsyncSession) -> None:
    with pytest.raises(NotFoundException):
        async with product_session.begin():
            await ProductRepository(product_session).increment_stock(uuid4(), 1)


async def test_concurrent_decrement_no_oversell(product_session: AsyncSession) -> None:
    """10 concurrent decrements against stock 5 should produce 5 successes only."""
    product = await create_product(product_session, stock_quantity=5)

    async def attempt_decrement() -> bool:
        async with AsyncSessionLocal() as session:
            try:
                async with session.begin():
                    await ProductRepository(session).decrement_stock(product.id, 1)
                return True
            except InsufficientStockException:
                return False

    results = await asyncio.gather(*(attempt_decrement() for _ in range(10)))

    assert results.count(True) == 5
    assert results.count(False) == 5

    async with AsyncSessionLocal() as session:
        found = await ProductRepository(session).get_by_id(product.id)
        assert found is not None
        assert found.stock_quantity == 0


async def test_get_low_stock_returns_correct_products(product_session: AsyncSession) -> None:
    await create_product(product_session, sku="LOW-1", stock_quantity=5)
    await create_product(product_session, sku="ENOUGH-1", stock_quantity=20)

    products = await ProductRepository(product_session).get_low_stock_products(threshold=10)

    assert [product.sku for product in products] == ["LOW-1"]
