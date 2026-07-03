"""Parse a Vietnamese chat message into a structured product/price query.

Pure helpers (no I/O) so both the conversation service and the product service
can resolve product/price questions deterministically instead of relying on the
LLM to scan a long catalog.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

PriceKind = Literal["cheapest", "most_expensive", "around", "under", "over"]
ProductCategory = Literal["gas", "nuoc_uong"]

# Colour / variant keywords that appear inside a product name (accent-stripped).
_COLOUR_KEYWORDS = ("do", "xam", "vang", "bien", "xanh", "nau", "bo", "trang")

_SIZE_KG_RE = re.compile(r"\b([1-9][0-9]?)\s*kg\b")
_SIZE_LITRE_RE = re.compile(r"\b([1-9][0-9]?)\s*(?:lit|l)\b")


def strip_accents(text: str) -> str:
    """Lowercase and remove Vietnamese diacritics for tolerant keyword matching."""
    lowered = text.lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


@dataclass(frozen=True)
class ProductQuery:
    """A product/price question extracted from a chat message."""

    brand: str | None = None
    size_kg: Decimal | None = None
    category: ProductCategory | None = None
    colour: str | None = None
    price_kind: PriceKind | None = None
    price_value: Decimal | None = None

    def is_specific(self) -> bool:
        """True when the message targets a concrete product subset.

        Only a brand or a cylinder/bottle size makes a message specific enough
        to narrow the catalog. A bare category ("gas" / "nước") is too broad and
        can be mis-resolved on mixed questions, so it does not narrow on its own.
        """
        return self.brand is not None or self.size_kg is not None


def parse_price_value(text: str) -> Decimal | None:
    """Parse a VND amount like '450k', '450.000', '450000', '1tr', '1 triệu'."""
    normalized = strip_accents(text)
    million = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:tr|trieu)\b", normalized)
    if million:
        return Decimal(million.group(1).replace(",", ".")) * Decimal(1_000_000)
    thousand = re.search(r"(\d+)\s*(?:k|nghin|ngan)\b", normalized)
    if thousand:
        return Decimal(thousand.group(1)) * Decimal(1000)
    grouped = re.search(r"\b(\d{1,3}(?:[.\s]\d{3})+)\b", normalized)
    if grouped:
        return Decimal(re.sub(r"[.\s]", "", grouped.group(1)))
    bare = re.search(r"\b(\d{4,7})\b", normalized)
    if bare:
        return Decimal(bare.group(1))
    return None


def _price_kind(normalized: str) -> PriceKind | None:
    # Match whole words only: accent-stripped tokens like "hon" (hơn) are
    # substrings of unrelated words ("khong" ⊃ "hon"), so substring checks
    # misfire. "around" is checked last so an explicit "dưới/trên X" wins over a
    # stray "tầm"/"tâm" elsewhere in the message.
    if any(_has_word(normalized, word) for word in ("re nhat", "thap nhat")):
        return "cheapest"
    if any(_has_word(normalized, word) for word in ("dat nhat", "mac nhat", "cao nhat")):
        return "most_expensive"
    if any(_has_word(normalized, word) for word in ("duoi", "toi da", "khong qua", "re hon")):
        return "under"
    if any(_has_word(normalized, word) for word in ("tren", "toi thieu", "hon")):
        return "over"
    if any(_has_word(normalized, word) for word in ("tam", "khoang")):
        return "around"
    return None


def _category(normalized: str, has_size_kg: bool, has_size_litre: bool) -> ProductCategory | None:
    if has_size_litre or "nuoc" in normalized:
        return "nuoc_uong"
    if has_size_kg or "gas" in normalized:
        return "gas"
    return None


def parse_product_query(text: str, brands: Sequence[str]) -> ProductQuery:
    """Extract brand/size/category/colour and any price intent from a message."""
    normalized = strip_accents(text)

    size_kg: Decimal | None = None
    kg_match = _SIZE_KG_RE.search(normalized)
    litre_match = _SIZE_LITRE_RE.search(normalized)
    if kg_match:
        size_kg = Decimal(kg_match.group(1))
    elif litre_match:
        size_kg = Decimal(litre_match.group(1))

    brand = _match_brand(normalized, brands)
    colour = next((colour for colour in _COLOUR_KEYWORDS if _has_word(normalized, colour)), None)
    category = _category(normalized, kg_match is not None, litre_match is not None)

    price_kind = _price_kind(normalized)
    price_value = parse_price_value(text) if price_kind in ("around", "under", "over") else None
    # A range/around intent without a parseable amount is not actionable.
    if price_kind in ("around", "under", "over") and price_value is None:
        price_kind = None

    return ProductQuery(
        brand=brand,
        size_kg=size_kg,
        category=category,
        colour=colour,
        price_kind=price_kind,
        price_value=price_value,
    )


def _match_brand(normalized: str, brands: Sequence[str]) -> str | None:
    """Return the catalog brand whose distinctive tokens appear in the message."""
    best: str | None = None
    best_len = 0
    for brand in brands:
        normalized_brand = strip_accents(brand)
        distinctive = normalized_brand.replace("gas", "").strip()
        if not distinctive:
            continue
        if distinctive in normalized and len(distinctive) > best_len:
            best = brand
            best_len = len(distinctive)
    return best


def _has_word(normalized: str, word: str) -> bool:
    return re.search(rf"\b{re.escape(word)}\b", normalized) is not None


def price_bounds(query: ProductQuery) -> tuple[Decimal | None, Decimal | None]:
    """Return (min_price, max_price) for a range/around/under/over query."""
    value = query.price_value
    if value is None:
        return None, None
    if query.price_kind == "around":
        window = value * Decimal("0.06")
        return value - window, value + window
    if query.price_kind == "under":
        return None, value
    if query.price_kind == "over":
        return value, None
    return None, None


def filter_products(products: Sequence[object], query: ProductQuery) -> list[object]:
    """Filter/sort an in-memory product list by the query, price ascending.

    Products must expose ``brand``, ``size_kg``, ``category``, ``name`` and
    ``price`` attributes (``ProductResponse`` or the ORM model).
    """
    min_price, max_price = price_bounds(query)
    # A colour keyword ("đỏ", "biển", ...) only disambiguates a variant of a
    # named product; on its own it collides with common Vietnamese words, so it
    # filters only alongside a brand or size.
    apply_colour = query.colour is not None and (
        query.brand is not None or query.size_kg is not None
    )
    matched: list[object] = []
    for product in products:
        if query.brand is not None and strip_accents(query.brand) not in strip_accents(
            _attr_str(product, "brand")
        ):
            continue
        if query.size_kg is not None and _attr(product, "size_kg") != query.size_kg:
            continue
        if query.category is not None and _attr_str(product, "category") != query.category:
            continue
        if apply_colour and not _has_word(
            strip_accents(_attr_str(product, "name")), query.colour or ""
        ):
            continue
        price = _attr(product, "price")
        if min_price is not None and price < min_price:
            continue
        if max_price is not None and price > max_price:
            continue
        matched.append(product)
    matched.sort(key=lambda item: _attr(item, "price"))
    return matched


def _attr(product: object, name: str) -> Any:
    return getattr(product, name)


def _attr_str(product: object, name: str) -> str:
    return str(getattr(product, name))
