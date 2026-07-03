"""Tests for the product/price query parser and in-memory filter."""

from dataclasses import dataclass
from decimal import Decimal

from app.services.product_query import (
    ProductQuery,
    filter_products,
    parse_price_value,
    parse_product_query,
)

_BRANDS = ["Petrolimex", "MT Gas", "Total Gas", "Shell Gas", "Hoàn Hảo"]


@dataclass
class _Product:
    brand: str
    size_kg: Decimal
    category: str
    name: str
    price: Decimal


def _catalog() -> list[_Product]:
    return [
        _Product(
            "Petrolimex", Decimal("12"), "gas", "Bình gas Petrolimex 12kg (đỏ)", Decimal("440000")
        ),
        _Product(
            "Petrolimex", Decimal("12"), "gas", "Bình gas Petrolimex 12kg (biển)", Decimal("675000")
        ),
        _Product("MT Gas", Decimal("12"), "gas", "Bình gas MT Gas 12kg", Decimal("420000")),
        _Product("Shell Gas", Decimal("12"), "gas", "Bình gas Shell 12kg", Decimal("450000")),
        _Product("Hoàn Hảo", Decimal("20"), "nuoc_uong", "Nước Hoàn Hảo 20 lít", Decimal("15000")),
    ]


def test_parse_price_value_variants() -> None:
    assert parse_price_value("tầm 450k") == Decimal("450000")
    assert parse_price_value("khoảng 450.000") == Decimal("450000")
    assert parse_price_value("450000 đồng") == Decimal("450000")
    assert parse_price_value("1 triệu") == Decimal("1000000")
    assert parse_price_value("2.250.000") == Decimal("2250000")
    assert parse_price_value("không có số") is None


def test_parse_query_specific_variant() -> None:
    query = parse_product_query("Petrolimex 12kg màu đỏ giá bao nhiêu", _BRANDS)

    assert query.brand == "Petrolimex"
    assert query.size_kg == Decimal("12")
    assert query.category == "gas"
    assert query.colour == "do"
    assert query.price_kind is None


def test_parse_query_superlative_and_range() -> None:
    cheapest = parse_product_query("gas 12kg loại nào rẻ nhất", _BRANDS)
    assert cheapest.price_kind == "cheapest"
    assert cheapest.size_kg == Decimal("12")

    around = parse_product_query("gas 12kg tầm 450k", _BRANDS)
    assert around.price_kind == "around"
    assert around.price_value == Decimal("450000")

    under = parse_product_query("bình gas dưới 500k", _BRANDS)
    assert under.price_kind == "under"
    assert under.price_value == Decimal("500000")


def test_parse_query_water_uses_litre_size() -> None:
    query = parse_product_query("nước 20 lít giá", _BRANDS)

    assert query.category == "nuoc_uong"
    assert query.size_kg == Decimal("20")


def test_under_wins_over_stray_around_word() -> None:
    # "tầm"/"tâm" strip to the same token; an explicit "dưới X" must still win.
    query = parse_product_query("tôi quan tâm gas 12kg dưới 500k", _BRANDS)

    assert query.price_kind == "under"
    assert query.price_value == Decimal("500000")


def test_over_word_not_matched_inside_khong() -> None:
    # "không" strips to "khong" which contains "hon"; must not classify as over.
    query = parse_product_query("gas 12kg loại nào tốt không", _BRANDS)

    assert query.price_kind is None


def test_category_alone_is_not_specific() -> None:
    query = parse_product_query("cửa hàng có gas và nước gì", _BRANDS)

    assert query.is_specific() is False


def test_colour_alone_does_not_filter() -> None:
    # A stray "do"/"bò" with no brand or size must not narrow the catalog.
    matched = filter_products(_catalog(), ProductQuery(colour="do"))

    assert len(matched) == len(_catalog())


def test_filter_products_by_brand_and_size_sorted_by_price() -> None:
    matched = filter_products(_catalog(), ProductQuery(brand="Petrolimex", size_kg=Decimal("12")))

    assert [product.price for product in matched] == [Decimal("440000"), Decimal("675000")]


def test_filter_products_by_colour() -> None:
    matched = filter_products(
        _catalog(), ProductQuery(brand="Petrolimex", size_kg=Decimal("12"), colour="bien")
    )

    assert len(matched) == 1
    assert matched[0].price == Decimal("675000")


def test_filter_products_cheapest_first() -> None:
    matched = filter_products(_catalog(), ProductQuery(size_kg=Decimal("12")))

    assert matched[0].price == Decimal("420000")


def test_filter_products_around_range() -> None:
    matched = filter_products(
        _catalog(),
        ProductQuery(size_kg=Decimal("12"), price_kind="around", price_value=Decimal("450000")),
    )
    prices = {product.price for product in matched}

    assert Decimal("445000") not in prices  # not in this catalog
    assert Decimal("450000") in prices
    assert Decimal("675000") not in prices
