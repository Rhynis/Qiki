"""Effective (sale) price helpers — the single source of truth for what a product
actually costs. Every charge and quote must route through ``effective_price`` so a
manually-entered sale price is honoured consistently (order, cart, re-order, Qiki).
"""

from decimal import ROUND_HALF_UP, Decimal


def effective_price(price: Decimal, sale_price: Decimal | None) -> Decimal:
    """Return the price actually charged.

    The sale price wins only when it is a valid discount (``0 < sale_price < price``);
    otherwise the regular list price applies.
    """
    if sale_price is not None and Decimal(0) < sale_price < price:
        return sale_price
    return price


def discount_percent(price: Decimal, sale_price: Decimal | None) -> int | None:
    """Return the integer discount percentage when a valid sale price exists, else None."""
    if sale_price is None or not (Decimal(0) < sale_price < price):
        return None
    return int(((price - sale_price) / price * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
