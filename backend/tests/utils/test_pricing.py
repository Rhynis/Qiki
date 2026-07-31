"""Tests for the effective (sale) price helpers."""

from decimal import Decimal

from app.utils.pricing import discount_percent, effective_price


def test_effective_price_uses_sale_when_valid_discount() -> None:
    assert effective_price(Decimal("710000"), Decimal("600000")) == Decimal("600000")


def test_effective_price_ignores_non_discount_sale_prices() -> None:
    # No sale, sale >= price, or sale <= 0 all fall back to the list price.
    assert effective_price(Decimal("710000"), None) == Decimal("710000")
    assert effective_price(Decimal("710000"), Decimal("710000")) == Decimal("710000")
    assert effective_price(Decimal("710000"), Decimal("800000")) == Decimal("710000")
    assert effective_price(Decimal("710000"), Decimal("0")) == Decimal("710000")


def test_discount_percent_rounds_to_integer() -> None:
    assert discount_percent(Decimal("710000"), Decimal("600000")) == 15
    assert discount_percent(Decimal("100000"), Decimal("75000")) == 25


def test_discount_percent_is_none_without_a_valid_sale() -> None:
    assert discount_percent(Decimal("710000"), None) is None
    assert discount_percent(Decimal("710000"), Decimal("710000")) is None
    assert discount_percent(Decimal("710000"), Decimal("0")) is None
