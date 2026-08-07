"""Tests for parent/variant product grouping.

These cover the storefront grouping (parent card with a price range), variant
price/stock resolution on the parent detail, and a regression guard that the
deterministic chatbot pricing still resolves the exact variant price after the
priced rows are grouped under a parent.
"""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundException
from app.models.product import Product, ProductParent
from app.models.user import User
from app.repositories.product_repository import ProductRepository
from app.schemas.product import ProductCreate
from app.services.product_query import parse_product_query
from app.services.product_service import ProductService

pytestmark = pytest.mark.asyncio


def _admin() -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid4(),
        email="admin@example.com",
        hashed_password="hashed",
        full_name="Admin",
        phone="0900000000",
        role="admin",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


async def _seed_saigon_petro(session: AsyncSession) -> ProductParent:
    """Create a parent with three real Saigon Petro variants at distinct prices."""
    parent = ProductParent(name="Bình gas Saigon Petro", brand="Saigon Petro", category="gas")
    session.add(parent)
    await session.flush()

    variants = [
        ("SP-12KG-XAM", "Bình gas Saigon Petro 12kg (xám)", Decimal("12"), Decimal("605000"), 50),
        ("SP-12KG-XANH", "Bình gas Saigon Petro 12kg (xanh)", Decimal("12"), Decimal("665000"), 0),
        ("SP-45KG-BO", "Bình gas Saigon Petro 45kg (bò)", Decimal("45"), Decimal("2250000"), 20),
    ]
    for sku, name, size, price, stock in variants:
        session.add(
            Product(
                sku=sku,
                name=name,
                brand="Saigon Petro",
                size_kg=size,
                category="gas",
                unit="kg",
                price=price,
                stock_quantity=stock,
                is_active=True,
                parent_id=parent.id,
            )
        )
    await session.flush()
    return parent


async def _seed_vihawa(session: AsyncSession) -> ProductParent:
    """Create a water parent with two same-size, different-form variants."""
    parent = ProductParent(name="Nước Vihawa", brand="Vihawa", category="nuoc_uong")
    session.add(parent)
    await session.flush()

    variants = [
        ("VIHAWA-20L", "Nước Vihawa 20 lít", Decimal("55000"), 50, "Bình thường"),
        (
            "VIHAWA-20L-NL",
            "Nước Vihawa 20 lít (bình nóng lạnh)",
            Decimal("55000"),
            30,
            "Bình nóng lạnh",
        ),
    ]
    for sku, name, price, stock, label in variants:
        session.add(
            Product(
                sku=sku,
                name=name,
                brand="Vihawa",
                size_kg=Decimal("20"),
                category="nuoc_uong",
                unit="lít",
                price=price,
                stock_quantity=stock,
                is_active=True,
                parent_id=parent.id,
                variant_label=label,
            )
        )
    await session.flush()
    return parent


async def test_grouped_catalog_reports_price_range(product_session: AsyncSession) -> None:
    """Water variants (same size, different bottle form) stay grouped under a parent."""
    parent = await _seed_vihawa(product_session)
    service = ProductService(ProductRepository(product_session))

    result = await service.list_grouped_catalog(category="nuoc_uong", limit=20)

    assert result.total == 1
    card = result.items[0]
    assert card.id == parent.id
    assert card.name == "Nước Vihawa"
    assert card.variant_count == 2
    # "from {min price}" is driven by min_price; max_price bounds the range.
    assert card.min_price == Decimal("55000")
    assert card.max_price == Decimal("55000")
    assert card.in_stock is True


async def test_grouped_catalog_returns_gas_individually(product_session: AsyncSession) -> None:
    """Gas variants (different sizes) are never aggregated into a parent card.

    Grouping gas kept the detail page's title fixed to the originally loaded
    product while the variant selector switched the shown size, so the title/
    SKU/price could drift apart (#342) — each active gas SKU is its own card.
    """
    await _seed_saigon_petro(product_session)
    service = ProductService(ProductRepository(product_session))

    result = await service.list_grouped_catalog(category="gas", limit=20)

    assert result.total == 3
    skus_by_price = {card.min_price: card for card in result.items}
    assert skus_by_price[Decimal("605000")].variant_count == 1
    assert skus_by_price[Decimal("605000")].max_price == Decimal("605000")
    assert skus_by_price[Decimal("605000")].name == "Bình gas Saigon Petro 12kg (xám)"
    assert {card.variant_count for card in result.items} == {1}


async def test_grouped_catalog_combines_gas_individual_and_water_grouped(
    product_session: AsyncSession,
) -> None:
    """With no category filter, gas stays individual and water stays grouped."""
    await _seed_saigon_petro(product_session)
    await _seed_vihawa(product_session)
    service = ProductService(ProductRepository(product_session))

    result = await service.list_grouped_catalog(limit=20)

    assert result.total == 4  # 3 individual gas cards + 1 grouped water card
    water_card = next(card for card in result.items if card.name == "Nước Vihawa")
    assert water_card.variant_count == 2
    gas_cards = [card for card in result.items if card.brand == "Saigon Petro"]
    assert len(gas_cards) == 3
    assert {card.variant_count for card in gas_cards} == {1}


async def test_parent_detail_returns_variants_price_ascending(
    product_session: AsyncSession,
) -> None:
    parent = await _seed_saigon_petro(product_session)
    service = ProductService(ProductRepository(product_session))

    detail = await service.get_parent(parent.id)

    assert [variant.sku for variant in detail.variants] == [
        "SP-12KG-XAM",
        "SP-12KG-XANH",
        "SP-45KG-BO",
    ]
    # Each variant keeps its own exact price and stock for the selector.
    prices = {variant.sku: variant.price for variant in detail.variants}
    stock = {variant.sku: variant.stock_quantity for variant in detail.variants}
    assert prices["SP-12KG-XAM"] == Decimal("605000")
    assert prices["SP-12KG-XANH"] == Decimal("665000")
    assert stock["SP-12KG-XANH"] == 0
    assert stock["SP-45KG-BO"] == 20


async def test_parent_detail_excludes_inactive_variants(product_session: AsyncSession) -> None:
    parent = await _seed_saigon_petro(product_session)
    repo = ProductRepository(product_session)
    xam = await repo.get_by_sku("SP-12KG-XAM")
    assert xam is not None
    await repo.update(xam.id, {"is_active": False})
    service = ProductService(repo)

    detail = await service.get_parent(parent.id)

    assert "SP-12KG-XAM" not in {variant.sku for variant in detail.variants}


async def test_get_parent_unknown_id_raises(product_session: AsyncSession) -> None:
    service = ProductService(ProductRepository(product_session))
    with pytest.raises(NotFoundException):
        await service.get_parent(uuid4())


async def test_delete_parent_soft_deletes_variants(product_session: AsyncSession) -> None:
    parent = await _seed_saigon_petro(product_session)
    service = ProductService(ProductRepository(product_session))

    await service.delete_parent(parent.id, _admin())

    with pytest.raises(NotFoundException):
        await service.get_parent(parent.id)
    # Variants are deactivated so the storefront and grouping hide them.
    grouped = await service.list_grouped_catalog(limit=20)
    assert grouped.total == 0


async def test_chatbot_find_products_resolves_exact_variant_price(
    product_session: AsyncSession,
) -> None:
    """Regression guard for #239: variant rows stay exactly priced and findable.

    ``find_products`` powers the deterministic chatbot pricing. Grouping the rows
    under a parent must not move the price off the sellable row, so a "cheapest
    Saigon Petro" query still resolves the exact 605.000đ variant.
    """
    await _seed_saigon_petro(product_session)
    service = ProductService(ProductRepository(product_session))

    query = parse_product_query("gas Saigon Petro rẻ nhất giá bao nhiêu", ["Saigon Petro"])
    matches = await service.find_products(query)

    assert [match.price for match in matches] == [
        Decimal("605000"),
        Decimal("665000"),
        Decimal("2250000"),
    ]
    cheapest = matches[0]
    assert cheapest.sku == "SP-12KG-XAM"
    assert cheapest.price == Decimal("605000")


async def test_create_variant_under_parent_references_specific_row(
    product_session: AsyncSession,
) -> None:
    parent = await _seed_saigon_petro(product_session)
    repo = ProductRepository(product_session)

    created = await repo.create(
        ProductCreate(
            sku="SP-12KG-VANG",
            name="Bình gas Saigon Petro 12kg (vàng)",
            brand="Saigon Petro",
            size_kg=Decimal("12"),
            category="gas",
            unit="kg",
            price=Decimal("665000"),
            stock_quantity=10,
            parent_id=parent.id,
            colour="vàng",
            variant_label="12 kg (vàng)",
        )
    )

    assert created.parent_id == parent.id
    assert created.colour == "vàng"
    detail = await ProductService(repo).get_parent(parent.id)
    assert "SP-12KG-VANG" in {variant.sku for variant in detail.variants}
