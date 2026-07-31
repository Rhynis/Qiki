"""Tests for ProductService."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.exceptions import ForbiddenException, InsufficientStockException, NotFoundException
from app.models.product import Product
from app.models.user import User
from app.schemas.product import (
    ProductCreate,
    ProductResponse,
    ProductSearchParams,
    ProductUpdate,
)
from app.services.product_query import ProductQuery
from app.services.product_service import ProductService

pytestmark = pytest.mark.asyncio


def make_user(role: str = "admin") -> User:
    """Create an in-memory user model."""
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email=f"{role}@example.com",
        hashed_password="hashed",
        full_name=f"{role.title()} User",
        phone="0900000000",
        role=role,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def make_product(
    *,
    sku: str = "GAS-12-SAIGON",
    stock_quantity: int = 20,
    is_active: bool = True,
) -> Product:
    """Create an in-memory product model."""
    now = datetime.now(UTC)
    return Product(
        id=uuid4(),
        sku=sku,
        name="Binh gas 12kg",
        brand="Saigon Petro",
        size_kg=Decimal("12"),
        category="gas",
        unit="kg",
        price=Decimal("350000"),
        stock_quantity=stock_quantity,
        description="Binh gas gia dinh",
        image_url="https://example.com/gas-12kg.jpg",
        safety_info="Dat binh noi thoang khi.",
        pricing_note=None,
        is_active=is_active,
        created_at=now,
        updated_at=now,
    )


def create_payload(sku: str = "GAS-12-SAIGON") -> ProductCreate:
    return ProductCreate(
        sku=sku,
        name="Binh gas 12kg",
        brand="Saigon Petro",
        size_kg=Decimal("12"),
        price=Decimal("350000"),
        stock_quantity=20,
    )


class FakeProductRepository:
    """Small fake repository for service tests."""

    def __init__(self) -> None:
        self.products: dict[object, Product] = {}
        self.created_payload: ProductCreate | None = None

    async def create(self, data: ProductCreate) -> Product:
        self.created_payload = data
        product = make_product(sku=data.sku, stock_quantity=data.stock_quantity)
        self.products[product.id] = product
        return product

    async def get_by_id(self, product_id: object, *, active_only: bool = False) -> Product | None:
        product = self.products.get(product_id)
        if product and active_only and not product.is_active:
            return None
        return product

    async def get_by_sku(self, sku: str, *, active_only: bool = False) -> Product | None:
        for product in self.products.values():
            if product.sku == sku.upper().strip():
                if active_only and not product.is_active:
                    return None
                return product
        return None

    async def list_products(
        self,
        params: ProductSearchParams,
        *,
        active_only: bool = True,
    ) -> tuple[list[Product], int]:
        products = [
            product for product in self.products.values() if not active_only or product.is_active
        ][params.skip : params.skip + params.limit]
        return products, len(products)

    async def update(self, product_id: object, data: dict[str, object]) -> Product:
        product = self.products[product_id]
        for key, value in data.items():
            setattr(product, key, value)
        return product

    async def soft_delete(self, product_id: object) -> bool:
        product = self.products.get(product_id)
        if not product:
            return False
        product.is_active = False
        return True

    async def get_low_stock_products(self, threshold: int = 10) -> list[Product]:
        return [
            product
            for product in self.products.values()
            if product.is_active and product.stock_quantity <= threshold
        ]

    async def decrement_stock(self, product_id: object, quantity: int) -> Product:
        product = self.products[product_id]
        if product.stock_quantity < quantity:
            raise InsufficientStockException("Insufficient stock")
        product.stock_quantity -= quantity
        return product


async def test_create_product_requires_admin() -> None:
    service = ProductService(FakeProductRepository())  # type: ignore[arg-type]

    with pytest.raises(ForbiddenException):
        await service.create_product(create_payload(), make_user("customer"))


async def test_create_product_returns_response() -> None:
    service = ProductService(FakeProductRepository())  # type: ignore[arg-type]

    product = await service.create_product(create_payload(), make_user())

    assert product.sku == "GAS-12-SAIGON"
    assert product.stock_quantity == 20


async def test_get_product_not_found() -> None:
    service = ProductService(FakeProductRepository())  # type: ignore[arg-type]

    with pytest.raises(NotFoundException):
        await service.get_product(uuid4())


async def test_get_product_returns_response() -> None:
    repository = FakeProductRepository()
    product = make_product()
    repository.products[product.id] = product
    service = ProductService(repository)  # type: ignore[arg-type]

    found = await service.get_product(product.id)

    assert found.id == product.id


async def test_get_product_by_sku_returns_response() -> None:
    repository = FakeProductRepository()
    product = make_product()
    repository.products[product.id] = product
    service = ProductService(repository)  # type: ignore[arg-type]

    found = await service.get_product_by_sku(product.sku.lower())

    assert found.sku == product.sku


async def test_get_product_by_sku_not_found() -> None:
    service = ProductService(FakeProductRepository())  # type: ignore[arg-type]

    with pytest.raises(NotFoundException):
        await service.get_product_by_sku("missing")


async def test_search_products_returns_pagination_metadata() -> None:
    repository = FakeProductRepository()
    active = make_product()
    inactive = make_product(sku="INACTIVE-12", is_active=False)
    repository.products[active.id] = active
    repository.products[inactive.id] = inactive
    service = ProductService(repository)  # type: ignore[arg-type]

    result = await service.search_products(ProductSearchParams(limit=10))

    assert result.total == 1
    assert result.page == 1
    assert result.has_more is False
    assert result.items[0].sku == active.sku


async def test_update_product_uses_unset_only() -> None:
    repository = FakeProductRepository()
    product = make_product()
    repository.products[product.id] = product
    service = ProductService(repository)  # type: ignore[arg-type]

    updated = await service.update_product(
        product.id,
        ProductUpdate(price=Decimal("360000")),
        make_user(),
    )

    assert updated.price == Decimal("360000")
    assert updated.name == "Binh gas 12kg"


async def test_delete_product_not_found() -> None:
    service = ProductService(FakeProductRepository())  # type: ignore[arg-type]

    with pytest.raises(NotFoundException):
        await service.delete_product(uuid4(), make_user())


async def test_get_low_stock_products_requires_admin() -> None:
    service = ProductService(FakeProductRepository())  # type: ignore[arg-type]

    with pytest.raises(ForbiddenException):
        await service.get_low_stock_products(make_user("customer"))


async def test_check_availability_and_reserve_stock() -> None:
    repository = FakeProductRepository()
    product = make_product(stock_quantity=3)
    repository.products[product.id] = product
    service = ProductService(repository)  # type: ignore[arg-type]

    assert await service.check_availability(product.id, 2) is True
    updated = await service.reserve_stock(product.id, 2)

    assert updated.stock_quantity == 1


def _catalog_product(
    *,
    sku: str,
    name: str,
    brand: str,
    size_kg: str,
    price: str,
    category: str = "gas",
) -> Product:
    """Build an in-memory catalog product for find_products tests."""
    now = datetime.now(UTC)
    return Product(
        id=uuid4(),
        sku=sku,
        name=name,
        brand=brand,
        size_kg=Decimal(size_kg),
        category=category,
        unit="kg" if category == "gas" else "lít",
        price=Decimal(price),
        stock_quantity=10,
        description=None,
        image_url="https://example.com/product.jpg",
        safety_info=None,
        pricing_note=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _find_service() -> ProductService:
    repository = FakeProductRepository()
    for product in (
        _catalog_product(
            sku="GAS-12-PLX-DO",
            name="Binh gas Petrolimex 12kg (do)",
            brand="Petrolimex",
            size_kg="12",
            price="440000",
        ),
        _catalog_product(
            sku="GAS-12-PLX-BIEN",
            name="Binh gas Petrolimex 12kg (bien)",
            brand="Petrolimex",
            size_kg="12",
            price="675000",
        ),
        _catalog_product(
            sku="GAS-12-MT",
            name="Binh gas MT Gas 12kg",
            brand="MT Gas",
            size_kg="12",
            price="420000",
        ),
        _catalog_product(
            sku="GAS-12-SHELL",
            name="Binh gas Shell 12kg",
            brand="Shell Gas",
            size_kg="12",
            price="450000",
        ),
    ):
        repository.products[product.id] = product
    return ProductService(repository)  # type: ignore[arg-type]


async def test_find_products_by_brand_and_size_sorted_by_price() -> None:
    service = _find_service()

    matched = await service.find_products(ProductQuery(brand="Petrolimex", size_kg=Decimal("12")))

    assert [product.price for product in matched] == [Decimal("440000"), Decimal("675000")]


async def test_find_products_by_colour() -> None:
    service = _find_service()

    matched = await service.find_products(
        ProductQuery(brand="Petrolimex", size_kg=Decimal("12"), colour="bien")
    )

    assert len(matched) == 1
    assert matched[0].price == Decimal("675000")


async def test_find_products_cheapest_first() -> None:
    service = _find_service()

    matched = await service.find_products(ProductQuery(size_kg=Decimal("12")))

    assert matched[0].brand == "MT Gas"
    assert matched[0].price == Decimal("420000")


async def test_find_products_around_range() -> None:
    service = _find_service()

    matched = await service.find_products(
        ProductQuery(size_kg=Decimal("12"), price_kind="around", price_value=Decimal("450000"))
    )
    prices = {product.price for product in matched}

    assert Decimal("450000") in prices
    assert Decimal("440000") in prices
    assert Decimal("675000") not in prices
    assert Decimal("420000") not in prices


async def test_find_products_nonstandard_gas_size_does_not_raise() -> None:
    # ProductSearchParams rejects gas sizes outside {6, 12, 45}; find_products
    # must drop the SQL size filter and return no in-memory match instead of 500.
    service = _find_service()

    matched = await service.find_products(
        ProductQuery(size_kg=Decimal("20"), category="gas", price_kind="cheapest")
    )

    assert matched == []


async def test_product_schema_accepts_long_description() -> None:
    # A detailed (long) description is optional on create, defaults to None, and is
    # accepted on update, distinct from the short listing `description`.
    payload = create_payload()
    assert payload.long_description is None

    detailed = ProductCreate(
        sku="GAS-12-DETAIL",
        name="Binh gas 12kg",
        brand="Saigon Petro",
        size_kg=Decimal("12"),
        price=Decimal("350000"),
        stock_quantity=20,
        description="Short listing text",
        long_description="Line one\n\nLine two with detail",
    )
    assert detailed.description == "Short listing text"
    assert detailed.long_description == "Line one\n\nLine two with detail"

    assert ProductUpdate(long_description="Updated detail").long_description == "Updated detail"


async def test_product_response_exposes_long_description() -> None:
    product = make_product()
    product.long_description = "Detailed multi-paragraph text"

    response = ProductResponse.model_validate(product)

    assert response.long_description == "Detailed multi-paragraph text"
