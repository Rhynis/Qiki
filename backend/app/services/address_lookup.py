"""Lookup helpers for HCMC ward names and delivery zone references."""

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

WARD_PREFIX_PATTERN = re.compile(r"\b(?:phường|p\.?|p)\s+", re.IGNORECASE)


@dataclass(frozen=True)
class WardDeliveryZoneMatch:
    """Resolved ward and its delivery zone reference."""

    ward: str
    delivery_zone: str


def resolve_delivery_zone_from_ward(text: str) -> str | None:
    """Return the delivery zone for a known ward mention, or None when unknown."""
    match = resolve_ward_delivery_zone(text)
    return match.delivery_zone if match else None


def resolve_ward_delivery_zone(text: str) -> WardDeliveryZoneMatch | None:
    """Return the matched ward and delivery zone for a known ward mention."""
    normalized_text = _normalize_text(text)
    if not normalized_text:
        return None

    wards = _load_ward_delivery_zone_map()
    direct = wards.get(normalized_text)
    if direct:
        return WardDeliveryZoneMatch(ward=normalized_text, delivery_zone=direct)

    text_without_prefixes = _strip_ward_prefixes(normalized_text)
    direct_without_prefix = wards.get(text_without_prefixes)
    if direct_without_prefix:
        return WardDeliveryZoneMatch(
            ward=text_without_prefixes,
            delivery_zone=direct_without_prefix,
        )

    for ward, delivery_zone in sorted(
        wards.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if ward.isdigit():
            if _contains_numbered_ward(normalized_text, ward):
                return WardDeliveryZoneMatch(ward=ward, delivery_zone=delivery_zone)
            continue
        if _contains_phrase(text_without_prefixes, ward):
            return WardDeliveryZoneMatch(ward=ward, delivery_zone=delivery_zone)
    return None


@lru_cache(maxsize=1)
def _load_ward_delivery_zone_map() -> dict[str, str]:
    path = Path(__file__).resolve().parents[1] / "data" / "hcmc_ward_district.json"
    raw_data = json.loads(path.read_text(encoding="utf-8"))
    return {_normalize_text(key): str(value) for key, value in raw_data.items()}


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text).lower().strip()
    return re.sub(r"\s+", " ", normalized)


def _strip_ward_prefixes(text: str) -> str:
    return re.sub(r"\s+", " ", WARD_PREFIX_PATTERN.sub(" ", text)).strip()


def _contains_phrase(text: str, phrase: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) is not None


def _contains_numbered_ward(text: str, ward_number: str) -> bool:
    return (
        re.search(rf"\bphường\s+{re.escape(ward_number)}\b", text) is not None
        or re.search(rf"\bp\.?\s*{re.escape(ward_number)}\b", text) is not None
    )
